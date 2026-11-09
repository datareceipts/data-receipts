"""Price one fixed website spec. Every AWS line comes from the Price List API.

The spec in spec.json is fixed before any price is looked up. That ordering is
the method: choosing the spec after seeing prices is how a comparison gets
quietly tuned to the answer you wanted.

AWS is priced line by line -- compute, database, both storage volumes, egress --
because the headline of this comparison turns out to be a line item, and a single
blended "AWS costs X" would hide it. Providers without a price API are in
vendors.json with URLs and the date read.
"""
import json, pathlib, sys, urllib.parse, urllib.request
from datetime import date

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
H = SPEC["compute"]["hours"]

EC2_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/"
           "current/us-east-1/index.json")
RDS_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/"
           "current/us-east-1/index.json")
# Internet egress is NOT in the EC2 index — it has its own offer code.
DT_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/"
          "current/index.json")
ECB_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
           "?lastNObservations=1&format=jsondata")
AZ_URL = "https://prices.azure.com/api/retail/prices"

AWS_INSTANCE, AWS_DB = "t3.medium", "db.t4g.small"
AWS_FREE_EGRESS_GB = 100      # AWS's free internet egress allowance per month


def fetch(url, timeout=900):
    req = urllib.request.Request(url, headers={"User-Agent": "data-receipts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _ondemand(terms, sku):
    for t in terms.get(sku, {}).values():
        for dim in t["priceDimensions"].values():
            usd = float(dim["pricePerUnit"]["USD"])
            if usd:
                return usd, dim.get("unit")
    return None, None


def ec2_lines():
    print("fetching AWS EC2 price index (~1 GB, slow)…", file=sys.stderr)
    d = fetch(EC2_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    out = {}
    for sku, p in prods.items():
        a = p.get("attributes", {})
        f = a.get("productFamily") or p.get("productFamily")
        if ("compute" not in out and a.get("instanceType") == AWS_INSTANCE
                and a.get("operatingSystem") == "Linux" and a.get("tenancy") == "Shared"
                and a.get("preInstalledSw") == "NA" and a.get("capacitystatus") == "Used"):
            usd, _ = _ondemand(terms, sku)
            if usd:
                out["compute"] = {"item": AWS_INSTANCE, "usd_per_hour": usd,
                                  "monthly": round(usd * H, 2),
                                  "detail": f"{a.get('vcpu')} vCPU / {a.get('memory')}"}
        if ("storage" not in out and p.get("productFamily") == "Storage"
                and a.get("volumeApiName") == "gp3"):
            usd, unit = _ondemand(terms, sku)
            if usd:
                gb = SPEC["storage_gb"]
                out["storage"] = {"item": f"EBS gp3 {gb} GB", "usd_per_gb_month": usd,
                                  "monthly": round(usd * gb, 2), "unit": unit}
    return out


def egress_line():
    """Egress is tiered, so take the tier the spec's volume actually falls in."""
    print("fetching AWS data transfer price list…", file=sys.stderr)
    d = fetch(DT_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    billable = max(0, SPEC["egress_gb"] - AWS_FREE_EGRESS_GB)
    for sku, p in prods.items():
        a = p.get("attributes", {})
        if not (a.get("fromLocation") == "US East (N. Virginia)"
                and a.get("transferType") == "AWS Outbound"
                and a.get("toLocation") == "External"):
            continue
        for t in terms.get(sku, {}).values():
            for dim in t["priceDimensions"].values():
                lo = int(dim.get("beginRange") or 0)
                hi = dim.get("endRange") or "Inf"
                hi = float("inf") if hi == "Inf" else int(hi)
                if lo <= billable < hi:
                    usd = float(dim["pricePerUnit"]["USD"])
                    return {"egress": {
                        "item": f"{SPEC['egress_gb']} GB out",
                        "usd_per_gb": usd, "free_gb": AWS_FREE_EGRESS_GB,
                        "billable_gb": billable, "tier": f"{lo}-{dim.get('endRange')} GB",
                        "monthly": round(usd * billable, 2)}}
    return {}


def rds_lines():
    print("fetching AWS RDS price index…", file=sys.stderr)
    d = fetch(RDS_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    out = {}
    for sku, p in prods.items():
        a = p.get("attributes", {})
        if ("db" not in out and a.get("instanceType") == AWS_DB
                and a.get("databaseEngine") == "PostgreSQL"
                and a.get("deploymentOption") == "Single-AZ"):
            usd, _ = _ondemand(terms, sku)
            if usd:
                out["db"] = {"item": AWS_DB, "usd_per_hour": usd,
                             "monthly": round(usd * H, 2),
                             "detail": f"{a.get('vcpu')} vCPU / {a.get('memory')}"}
        if ("db_storage" not in out and p.get("productFamily") == "Database Storage"
                and a.get("deploymentOption") == "Single-AZ"
                and "General Purpose" in (a.get("volumeType") or "")
                and "gp3" in (a.get("volumeName") or a.get("usagetype") or "").lower()):
            usd, _ = _ondemand(terms, sku)
            if usd:
                gb = SPEC["database"]["storage_gb"]
                out["db_storage"] = {"item": f"RDS gp3 {gb} GB",
                                     "usd_per_gb_month": usd,
                                     "monthly": round(usd * gb, 2)}
    return out


def ecb_eur_usd():
    d = fetch(ECB_URL, 60)
    s = d["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]
    dates = d["structure"]["dimensions"]["observation"][0]["values"]
    k = list(s)[0]
    return {"rate": s[k][0], "date": dates[int(k)]["id"],
            "source": "ECB daily euro foreign exchange reference rate"}


def main():
    aws = {**ec2_lines(), **rds_lines(), **egress_line()}
    missing = [k for k in ("compute", "storage", "egress", "db", "db_storage")
               if k not in aws]
    if missing:
        sys.exit(f"AWS line items not found, refusing to publish a partial bill: {missing}")
    out = {"retrieved": date.today().isoformat(), "spec": SPEC,
           "aws": aws, "aws_total": round(sum(v["monthly"] for v in aws.values()), 2),
           "fx": ecb_eur_usd(),
           "sources": {"aws_ec2": EC2_URL, "aws_rds": RDS_URL,
                       "fx": "ECB daily reference rate, data-api.ecb.europa.eu"}}
    (HERE / "hyperscalers.json").write_text(json.dumps(out, indent=1))
    for k, v in aws.items():
        print(f"  {k:12} {v['item']:22} ${v['monthly']:>8,.2f}")
    print(f"  {'TOTAL':12} {'':22} ${out['aws_total']:>8,.2f}")
    print(f"  EUR/USD {out['fx']['rate']} ({out['fx']['date']})")


if __name__ == "__main__":
    main()
