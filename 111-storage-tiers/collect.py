"""Price 1 TB of object storage across providers and across storage tiers.

The spec in spec.json was committed before any price was looked up.

Two traps this collector exists to avoid, both found by reading the raw index
rather than trusting the labels:

1. AWS's S3 price list has TWO SKUs with usagetype 'Standard-Retrieval-Bytes',
   at $0.01 and $0.02. They are different products. Only the `operation` field
   separates them: RestoreObject is Glacier Flexible, DeepArchiveRestoreObject
   is Deep Archive. Matching on usagetype alone silently doubles or halves a
   retrieval bill.

2. The us-east-1 index has no Deep Archive STORAGE rate at all. The two SKUs
   whose volumeType reads 'Glacier Deep Archive' are both GlacierStagingStorage
   at $0.021/GB-Mo, which is ~21x the real figure. The only $0.00099 in the
   file belongs to Intelligent-Tiering Deep Archive Access -- a different
   product that happens to carry the same rate today. Substituting it would be
   quoting one product's price for another, so Deep Archive storage is read
   from AWS's published page and recorded in vendors.json instead.

Azure's East US blob catalogue offers LRS, GRS and RA-GRS but not ZRS. S3
Standard replicates across three or more availability zones, which sits
between LRS (one datacentre) and GRS (two regions), so both Azure figures are
collected and the comparison reports which one it is using.
"""
import json, pathlib, sys, time, urllib.parse, urllib.request
from datetime import date

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())

S3_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/"
          "current/us-east-1/index.json")
DT_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/"
          "current/index.json")
AZ_URL = "https://prices.azure.com/api/retail/prices"
AWS_FREE_EGRESS_GB = 100

# volumeType in the S3 index -> the name AWS sells the tier under.
S3_TIERS = {
    "Standard": "S3 Standard",
    "Standard - Infrequent Access": "S3 Standard-IA",
    "Glacier Instant Retrieval": "S3 Glacier Instant Retrieval",
    "Amazon Glacier": "S3 Glacier Flexible Retrieval",
}
# (group, operation) -> restore-request rate. S3-API-Tier3 holds THREE SKUs at
# two different prices, separated only by `operation`: RestoreObject is the
# Glacier restore request, the *Transition ones are lifecycle moves. Grouping
# by `group` alone picks whichever happens to come first in the file.
S3_RESTORE_REQ = {
    ("S3-API-Tier3", "RestoreObject"): ("S3 Glacier Flexible Retrieval", "standard"),
    ("S3-API-Tier5", ""): ("S3 Glacier Flexible Retrieval", "bulk"),
}
# (usagetype, operation) -> tier.  The operation field is load-bearing; see above.
S3_RETRIEVAL = {
    ("Retrieval-SIA", None): ("S3 Standard-IA", "standard"),
    ("Retrieval-GIR", None): ("S3 Glacier Instant Retrieval", "standard"),
    ("Standard-Retrieval-Bytes", "RestoreObject"):
        ("S3 Glacier Flexible Retrieval", "standard"),
    ("Bulk-Retrieval-Bytes", "RestoreObject"):
        ("S3 Glacier Flexible Retrieval", "bulk"),
    ("Standard-Retrieval-Bytes", "DeepArchiveRestoreObject"):
        ("S3 Glacier Deep Archive", "standard"),
    ("Bulk-Retrieval-Bytes", "DeepArchiveRestoreObject"):
        ("S3 Glacier Deep Archive", "bulk"),
}


def fetch(url, timeout=900, tries=8):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "data-receipts/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            # Azure's retail API rate-limits hard when the catalogue is paged.
            if any(c in str(e) for c in ("429", "503", "timed out")) and attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def _first_price(terms, sku):
    for t in terms.get(sku, {}).values():
        for dim in t["priceDimensions"].values():
            return float(dim["pricePerUnit"]["USD"])
    return None


def s3_lines():
    print("fetching AWS S3 price index…", file=sys.stderr)
    d = fetch(S3_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    storage, retrieval, requests_, restore_req = {}, {}, {}, {}
    for sku, p in prods.items():
        a = p.get("attributes", {})
        vt, ut, op = a.get("volumeType"), a.get("usagetype"), a.get("operation") or None
        grp = a.get("group")
        if p.get("productFamily") == "Storage" and vt in S3_TIERS:
            for t in terms.get(sku, {}).values():
                for dim in t["priceDimensions"].values():
                    if int(dim.get("beginRange") or 0) == 0:
                        storage[S3_TIERS[vt]] = float(dim["pricePerUnit"]["USD"])
        key = (ut, op if (ut, op) in S3_RETRIEVAL else None)
        if key in S3_RETRIEVAL:
            tier, speed = S3_RETRIEVAL[key]
            retrieval.setdefault(tier, {})[speed] = _first_price(terms, sku)
        rk = (grp, a.get("operation") or "")
        if rk in S3_RESTORE_REQ:
            tier, speed = S3_RESTORE_REQ[rk]
            restore_req.setdefault(tier, {})[speed] = _first_price(terms, sku)
        if grp in ("S3-API-Tier1", "S3-API-Tier2", "S3-API-SIA-Tier1",
                   "S3-API-SIA-Tier2", "S3-API-GIR-Tier1", "S3-API-GIR-Tier2") \
                and "Annotation" not in str(ut):
            requests_[grp] = _first_price(terms, sku)
    return storage, retrieval, requests_, restore_req


def aws_egress_per_gb(volume_gb):
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
                    return float(dim["pricePerUnit"]["USD"]), AWS_FREE_EGRESS_GB
    return None, AWS_FREE_EGRESS_GB


def azure_lines():
    print("fetching Azure blob catalogue…", file=sys.stderr)
    f = ("serviceName eq 'Storage' and armRegionName eq 'eastus' and "
         "priceType eq 'Consumption' and productName eq 'Blob Storage'")
    url = f"{AZ_URL}?$filter={urllib.parse.quote(f)}"
    items = []
    while url:
        d = fetch(url, timeout=120)
        items += d["Items"]
        url = d.get("NextPageLink")
        time.sleep(1)
    out = {}
    for i in items:
        sku, meter, price = i["skuName"], i["meterName"], i["retailPrice"]
        # Hot storage is volume-tiered; 1 TB sits in the first tier.
        if "Data Stored" in meter and (i.get("tierMinimumUnits") or 0) != 0:
            continue
        slot = ("stored" if "Data Stored" in meter else
                "retrieval" if "Data Retrieval" in meter and "Priority" not in meter else
                "read_10k" if "Read Operations" in meter and "Priority" not in meter else
                "write_10k" if "Write Operations" in meter else None)
        if slot:
            out.setdefault(sku, {})[slot] = price
    return out


def azure_egress_per_gb():
    print("fetching Azure bandwidth prices…", file=sys.stderr)
    f = ("serviceName eq 'Bandwidth' and armRegionName eq 'eastus' and "
         "priceType eq 'Consumption'")
    url = f"{AZ_URL}?$filter={urllib.parse.quote(f)}"
    rows = []
    while url:
        d = fetch(url, timeout=120)
        rows += d["Items"]
        url = d.get("NextPageLink")
        time.sleep(1)
    for i in rows:
        if ("Data Transfer Out" in i["meterName"]
                and (i.get("tierMinimumUnits") or 0) in (0, 100.0)
                and i["retailPrice"] > 0):
            return i["retailPrice"], 100
    return None, 100


def main():
    storage, retrieval, requests_, restore_req = s3_lines()
    missing = [t for t in S3_TIERS.values() if t not in storage]
    if missing:
        sys.exit(f"S3 storage rates not found, refusing to publish a partial "
                 f"comparison: {missing}")
    if not retrieval.get("S3 Glacier Deep Archive"):
        sys.exit("Deep Archive retrieval rates not found; see module docstring.")
    if "standard" not in restore_req.get("S3 Glacier Flexible Retrieval", {}):
        sys.exit("Glacier restore-request rate not found; the archive tiers "
                 "cannot be totalled without it.")

    aws_eg, aws_free = aws_egress_per_gb(SPEC["headline_retrieval_gb"])
    az = azure_lines()
    az_eg, az_free = azure_egress_per_gb()
    if aws_eg is None or az_eg is None:
        sys.exit("egress rate missing; refusing to publish a bill without it")

    out = {
        "generated": date.today().isoformat(),
        "spec": SPEC["name"],
        "aws": {"storage_gb_mo": storage, "retrieval_per_gb": retrieval,
                "requests": requests_, "restore_requests": restore_req,
                "egress": {"usd_per_gb": aws_eg, "free_gb": aws_free}},
        "azure": {"blob": az, "egress": {"usd_per_gb": az_eg, "free_gb": az_free}},
        "sources": {
            "aws_s3": S3_URL,
            "aws_egress": DT_URL,
            "azure": AZ_URL + " (serviceName=Storage/Bandwidth, eastus)",
        },
    }
    (HERE / "costs.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote costs.json — {len(storage)} S3 tiers, {len(az)} Azure SKUs")


if __name__ == "__main__":
    main()
