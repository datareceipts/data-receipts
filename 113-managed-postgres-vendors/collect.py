"""Price one fixed Postgres workload from the two vendors that publish APIs.

AWS RDS comes from the RDS price list, Azure Database for PostgreSQL Flexible
Server from the Retail Prices API. Vendors without an API are in vendors.json
with URLs and the date read.

The instance choice is the load-bearing decision. The spec asks for 2 vCPU and
8 GB, and AWS sells two things that match: db.t4g.large is burstable, meaning
sustained CPU above a baseline is throttled or billed as credits, and
db.m6g.large is not. A burstable instance is not the same product as a fixed
one, so the standard instance is priced and the burstable figure is collected
alongside rather than substituted for it.
"""
import json, pathlib, sys, time, urllib.parse, urllib.request
from datetime import date

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
H = SPEC["hours"]

RDS_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/"
           "current/us-east-1/index.json")
DT_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/"
          "current/index.json")
AZ_URL = "https://prices.azure.com/api/retail/prices"

AWS_STANDARD, AWS_BURSTABLE = "db.m6g.large", "db.t4g.large"
AWS_FREE_EGRESS_GB = 100
AZ_SERIES = "Ddsv5"          # General Purpose; D2ds_v5 is 2 vCore / 8 GiB


def fetch(url, timeout=900, tries=8):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "data-receipts/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            if any(c in str(e) for c in ("429", "503", "timed out")) and attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def _ondemand(terms, sku):
    for t in terms.get(sku, {}).values():
        for dim in t["priceDimensions"].values():
            usd = float(dim["pricePerUnit"]["USD"])
            if usd:
                return usd
    return None


def rds_lines():
    print("fetching AWS RDS price index…", file=sys.stderr)
    d = fetch(RDS_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    out = {}
    for sku, p in prods.items():
        a = p.get("attributes", {})
        inst = a.get("instanceType")
        if (inst in (AWS_STANDARD, AWS_BURSTABLE)
                and a.get("databaseEngine") == "PostgreSQL"
                and a.get("deploymentOption") == "Single-AZ"):
            usd = _ondemand(terms, sku)
            if usd and inst not in out:
                out[inst] = {"usd_per_hour": usd, "monthly": round(usd * H, 2),
                             "detail": f"{a.get('vcpu')} vCPU / {a.get('memory')}"}
        if ("storage" not in out and p.get("productFamily") == "Database Storage"
                and a.get("deploymentOption") == "Single-AZ"
                and "General Purpose" in (a.get("volumeType") or "")
                and "gp3" in (a.get("volumeName") or a.get("usagetype") or "").lower()):
            usd = _ondemand(terms, sku)
            if usd:
                out["storage"] = {"usd_per_gb_month": usd,
                                  "monthly": round(usd * SPEC["storage_gb"], 2)}
    return out


def egress_per_gb(volume_gb):
    print("fetching AWS data transfer price list…", file=sys.stderr)
    d = fetch(DT_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    billable = max(0, volume_gb - AWS_FREE_EGRESS_GB)
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
                    return float(dim["pricePerUnit"]["USD"])
    return None


def azure_lines():
    print("fetching Azure Postgres catalogue…", file=sys.stderr)
    f = ("serviceName eq 'Azure Database for PostgreSQL' and "
         "armRegionName eq 'eastus' and priceType eq 'Consumption'")
    url = f"{AZ_URL}?$filter={urllib.parse.quote(f)}"
    items = []
    while url:
        d = fetch(url, timeout=120)
        items += d["Items"]
        url = d.get("NextPageLink")
        time.sleep(1)
    out = {}
    for i in items:
        if AZ_SERIES in i["productName"] and i["skuName"] == f"{SPEC['vcpu']} vCore":
            out["compute"] = {"usd_per_hour": i["retailPrice"],
                              "monthly": round(i["retailPrice"] * H, 2),
                              "sku": i["productName"]}
        if (i["productName"].endswith("Flex Server Storage")
                and i["skuName"] == "Storage"):
            out["storage"] = {"usd_per_gb_month": i["retailPrice"],
                              "monthly": round(i["retailPrice"] * SPEC["storage_gb"], 2)}
        if "Backup Storage LRS" in i["skuName"] and "Data Stored" in i["meterName"]:
            out["backup_per_gb"] = i["retailPrice"]
    return out


def main():
    aws = rds_lines()
    az = azure_lines()
    eg = egress_per_gb(SPEC["egress_gb"])
    missing = [k for k in (AWS_STANDARD, "storage") if k not in aws]
    if missing:
        sys.exit(f"AWS RDS lines not found, refusing to publish a partial "
                 f"comparison: {missing}")
    if "compute" not in az or "storage" not in az:
        sys.exit(f"Azure Postgres lines not found: {sorted(az)}")
    if eg is None:
        sys.exit("egress rate missing; refusing to publish a bill without it")

    out = {
        "generated": date.today().isoformat(),
        "spec": SPEC["name"],
        "aws": aws, "azure": az,
        "egress": {"usd_per_gb": eg, "free_gb": AWS_FREE_EGRESS_GB},
        "sources": {"aws_rds": RDS_URL, "aws_egress": DT_URL,
                    "azure": AZ_URL + " (serviceName=Azure Database for PostgreSQL, eastus)"},
    }
    (HERE / "costs.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote costs.json — AWS {AWS_STANDARD} ${aws[AWS_STANDARD]['monthly']}, "
          f"Azure ${az['compute']['monthly']}")


if __name__ == "__main__":
    main()
