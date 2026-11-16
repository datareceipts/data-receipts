"""Price one terabyte of AWS traffic by destination, from the price APIs.

Three offer codes are needed, which is most of why this is hard to look up:
internet and inter-region transfer live in AWSDataTransfer, NAT Gateway lives
in AmazonEC2 under productFamily 'NAT Gateway', and neither of those is where
you would look first.

AMBIGUITY, recorded rather than resolved: the AWSDataTransfer list contains
three intra-region SKUs for us-east-1 whose descriptions are word-for-word
identical -- "regional data transfer - in/out/between EC2 AZs or using elastic
IPs or ELB" -- at two different prices. transferType 'IntraRegion'
(DataTransfer-Regional-Bytes) is $0.01/GB; 'IntraRegion-xAZ-Out' and
'IntraRegion-xAZ-In' are $0.00/GB. Nothing in the attributes says which
governs a given byte. This collects all three and compute.py uses the $0.01
figure, which is what independent pricing references still quote; the $0.00
SKUs are carried into costs.json so the ambiguity is visible.
"""
import json, pathlib, sys, urllib.request
from datetime import date

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())

DT_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/"
          "current/index.json")
EC2_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/"
           "current/us-east-1/index.json")
FROM = "US East (N. Virginia)"
PEER_REGION = "US West (Oregon)"
FREE_EGRESS_GB = 100


def fetch(url, timeout=1200):
    req = urllib.request.Request(url, headers={"User-Agent": "data-receipts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def transfer_rates(volume_gb):
    print("fetching AWSDataTransfer…", file=sys.stderr)
    d = fetch(DT_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    out = {"intra_region_variants": {}}
    billable = max(0, volume_gb - FREE_EGRESS_GB)
    for sku, p in prods.items():
        a = p.get("attributes", {})
        tt = a.get("transferType")
        if a.get("fromLocation") != FROM:
            continue
        for t in terms.get(sku, {}).values():
            for dim in t["priceDimensions"].values():
                usd = float(dim["pricePerUnit"]["USD"])
                lo = int(dim.get("beginRange") or 0)
                hi = dim.get("endRange") or "Inf"
                hi = float("inf") if hi == "Inf" else int(hi)
                if (tt == "AWS Outbound" and a.get("toLocation") == "External"
                        and lo <= billable < hi):
                    out["internet_per_gb"] = usd
                    out["internet_tier"] = f"{lo}-{dim.get('endRange')} GB"
                if tt == "InterRegion Outbound" and a.get("toLocation") == PEER_REGION:
                    out["cross_region_per_gb"] = usd
                    out["cross_region_to"] = PEER_REGION
                if tt in ("IntraRegion", "IntraRegion-xAZ-Out", "IntraRegion-xAZ-In"):
                    out["intra_region_variants"][tt] = {
                        "usd_per_gb": usd, "usagetype": a.get("usagetype"),
                        "description": dim.get("description")}
    return out


def nat_rates():
    print("fetching AmazonEC2 (large, slow)…", file=sys.stderr)
    d = fetch(EC2_URL)
    prods, terms = d["products"], d["terms"]["OnDemand"]
    out = {}
    for sku, p in prods.items():
        a = p.get("attributes", {})
        if p.get("productFamily") != "NAT Gateway":
            continue
        ut = a.get("usagetype")
        if ut not in ("NatGateway-Hours", "NatGateway-Bytes"):
            continue           # the Regional/CloudWAN variants are other products
        for t in terms.get(sku, {}).values():
            for dim in t["priceDimensions"].values():
                key = "nat_per_hour" if ut.endswith("Hours") else "nat_per_gb"
                out[key] = float(dim["pricePerUnit"]["USD"])
    return out


def main():
    t = transfer_rates(SPEC["volume_gb"])
    n = nat_rates()
    need_t = ["internet_per_gb", "cross_region_per_gb"]
    need_n = ["nat_per_hour", "nat_per_gb"]
    missing = ([k for k in need_t if k not in t] + [k for k in need_n if k not in n]
               + (["IntraRegion"] if "IntraRegion" not in t["intra_region_variants"] else []))
    if missing:
        sys.exit(f"rates not found, refusing to publish a partial comparison: {missing}")

    out = {"generated": date.today().isoformat(), "spec": SPEC["name"],
           "free_egress_gb": FREE_EGRESS_GB, **t, **n,
           "sources": {"transfer": DT_URL, "nat": EC2_URL + " (productFamily=NAT Gateway)"}}
    (HERE / "costs.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote costs.json — internet ${t['internet_per_gb']}/GB, "
          f"NAT ${n['nat_per_gb']}/GB + ${n['nat_per_hour']}/hr, "
          f"{len(t['intra_region_variants'])} intra-region variants")


if __name__ == "__main__":
    main()
