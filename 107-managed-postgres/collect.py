"""What a managed Postgres actually costs, against running it yourself.

Two of the four inputs are pulled from APIs and two are transcribed by hand,
because only AWS and the ECB publish machine-readable prices:

  AWS RDS   AWS Price List API (bulk, us-east-1)      — pulled
  EUR/USD   ECB daily reference rate                  — pulled
  Others    DigitalOcean, Supabase, Neon, Hetzner     — vendors.json, transcribed
            from each vendor's own pricing page, with URL and date recorded

  python3 collect.py out.json
"""
import json, sys, urllib.request, datetime, pathlib

ROOT = pathlib.Path(__file__).parent
RDS_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"
           "AmazonRDS/current/us-east-1/index.json")
ECB_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
           "?lastNObservations=1&format=jsondata")
HOURS = 730  # a month, the way every one of these vendors bills it

# The spec every row has to meet or beat. Postgres is memory-bound before it is
# CPU-bound, so RAM is the binding requirement and extra vCPU is noted, not paid for.
SPEC = {"ram_gb": 8, "storage_gb": 100, "nodes": 1, "hours": HOURS}


def fetch(url, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": "data-receipts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ecb_eur_usd():
    d = fetch(ECB_URL, 60)
    s = d["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]
    dates = d["structure"]["dimensions"]["observation"][0]["values"]
    k = list(s)[0]
    return {"rate": s[k][0], "date": dates[int(k)]["id"],
            "source": "ECB daily euro foreign exchange reference rate"}


def rds(instance="db.m6g.large", storage_type="General Purpose-GP3"):
    d = fetch(RDS_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    inst = storage = None
    for sku, p in prods.items():
        a = p.get("attributes", {})
        if (a.get("databaseEngine") == "PostgreSQL"
                and a.get("deploymentOption") == "Single-AZ"
                and a.get("instanceType") == instance):
            price = next(iter(next(iter(terms[sku].values()))["priceDimensions"].values()))
            cand = {"sku": sku, "usd_hour": float(price["pricePerUnit"]["USD"]),
                    "vcpu": a.get("vcpu"), "memory": a.get("memory")}
            # Several SKUs share an instance type; keep the one that carries specs.
            if inst is None or (cand["vcpu"] and not inst["vcpu"]):
                inst = cand
        if (p.get("productFamily") == "Database Storage"
                and a.get("deploymentOption") == "Single-AZ"
                and a.get("volumeType") == storage_type):
            price = next(iter(next(iter(terms[sku].values()))["priceDimensions"].values()))
            storage = {"usd_gb_month": float(price["pricePerUnit"]["USD"]),
                       "volume_type": storage_type}
    if not inst or not storage:
        sys.exit(f"RDS: no match for {instance} / {storage_type}")
    return {"instance": instance, **inst, "storage": storage,
            "source": "AWS Price List API, AmazonRDS us-east-1",
            "url": RDS_URL}


def main(out):
    vendors = json.loads((ROOT / "vendors.json").read_text())
    data = {
        "retrieved": datetime.date.today().isoformat(),
        "spec": SPEC,
        "fx": ecb_eur_usd(),
        "aws_rds": rds(),
        "vendors": vendors,
    }
    pathlib.Path(out).write_text(json.dumps(data, indent=2))
    r = data["aws_rds"]
    print(f"  AWS RDS {r['instance']}  {r['vcpu']} vCPU / {r['memory']}  "
          f"${r['usd_hour']:.4f}/hr  -> ${r['usd_hour']*HOURS:,.2f}/mo")
    print(f"  RDS storage ({r['storage']['volume_type']}): "
          f"${r['storage']['usd_gb_month']}/GB-mo")
    print(f"  EUR/USD {data['fx']['rate']} ({data['fx']['date']})")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "prices.json")
