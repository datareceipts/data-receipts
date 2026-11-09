"""Pull on-demand GPU instance prices from the AWS and Azure public price APIs.

Both are unauthenticated. The neocloud prices are not available by API without
an account, so they are transcribed into vendors.json with their source URL and
the date they were read.

Everything is normalised to dollars per GPU per hour, which is the only way to
compare an 8-GPU cluster node against a single-GPU box. GPU counts come from
each vendor's own documentation, recorded in SPECS below rather than parsed out
of a price label -- AWS reports "640 GB HBM3" for a p5 and Azure reports
"Accelerator-Memory 640", and neither states the per-GPU model.
"""
import json, pathlib, sys, urllib.parse, urllib.request
from datetime import date

HERE = pathlib.Path(__file__).parent
AWS_URL = ("https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/"
           "current/us-east-1/index.json")
AZ_URL = "https://prices.azure.com/api/retail/prices"

# GPU model, memory and count per instance, from vendor documentation.
# Doc URLs are recorded in sources() so each row can be checked.
SPECS = {
    "p5.48xlarge":                 ("H100 SXM", 80, 8),
    "p4d.24xlarge":                ("A100 SXM", 40, 8),
    "p4de.24xlarge":               ("A100 SXM", 80, 8),
    "Standard_ND96isr_H100_v5":    ("H100 SXM", 80, 8),
    "Standard_NC40ads_H100_v5":    ("H100 NVL", 94, 1),
    "Standard_NC80adis_H100_v5":   ("H100 NVL", 94, 2),
    "Standard_NC24ads_A100_v4":    ("A100 PCIe", 80, 1),
    "Standard_NC48ads_A100_v4":    ("A100 PCIe", 80, 2),
    "Standard_NC96ads_A100_v4":    ("A100 PCIe", 80, 4),
    "Standard_ND96asr_A100_v4":    ("A100 SXM", 40, 8),
}


def aws():
    print("fetching AWS us-east-1 EC2 price index (~1 GB, slow)…", file=sys.stderr)
    with urllib.request.urlopen(AWS_URL, timeout=900) as r:
        d = json.loads(r.read())
    want = {k for k in SPECS if not k.startswith("Standard_")}
    skus = {}
    for sku, p in d["products"].items():
        a = p.get("attributes", {})
        if (a.get("instanceType") in want and a.get("operatingSystem") == "Linux"
                and a.get("tenancy") == "Shared" and a.get("preInstalledSw") == "NA"
                and a.get("capacitystatus") == "Used"):
            skus[sku] = a["instanceType"]
    out = {}
    for sku, name in skus.items():
        for term in d["terms"]["OnDemand"].get(sku, {}).values():
            for dim in term["priceDimensions"].values():
                usd = float(dim["pricePerUnit"]["USD"])
                if usd:
                    out[name] = usd
    return out


def azure():
    f = ("serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' "
         "and priceType eq 'Consumption'")
    url = AZ_URL + "?" + urllib.parse.urlencode({"$filter": f, "currencyCode": "USD"})
    out = {}
    for _ in range(60):
        with urllib.request.urlopen(url, timeout=120) as r:
            d = json.loads(r.read())
        for i in d["Items"]:
            n = i["armSkuName"]
            # Spot and Low Priority are preemptible, a different product
            if n in SPECS and "Spot" not in i["skuName"] \
                    and "Low Priority" not in i["skuName"]:
                out.setdefault(n, i["retailPrice"])
        url = d.get("NextPageLink")
        if not url:
            break
    return out


def main():
    rows = []
    for vendor, prices in (("AWS", aws()), ("Azure", azure())):
        for name, usd in sorted(prices.items()):
            model, mem, n = SPECS[name]
            rows.append({"vendor": vendor, "instance": name, "gpu": model,
                         "gpu_memory_gb": mem, "gpu_count": n,
                         "usd_per_hour": round(usd, 6),
                         "usd_per_gpu_hour": round(usd / n, 4),
                         "region": "us-east-1" if vendor == "AWS" else "eastus"})
    missing = sorted(set(SPECS) - {r["instance"] for r in rows})
    out = {"retrieved": date.today().isoformat(), "rows": rows, "missing": missing,
           "sources": sources()}
    (HERE / "hyperscalers.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(f"  {r['vendor']:6} {r['instance']:28} {r['gpu']:10} {r['gpu_memory_gb']:>3}GB "
              f"x{r['gpu_count']}  ${r['usd_per_hour']:>9,.2f}/hr  "
              f"${r['usd_per_gpu_hour']:>7,.2f}/GPU-hr")
    if missing:
        print("  NOT FOUND:", ", ".join(missing))


def sources():
    return {
        "aws_prices": f"AWS Price List, {AWS_URL}",
        "azure_prices": f"Azure Retail Prices API, {AZ_URL}",
        "aws_p5_spec": "https://aws.amazon.com/ec2/instance-types/p5/",
        "aws_p4_spec": "https://aws.amazon.com/ec2/instance-types/p4/",
        "azure_nd_h100_spec": ("https://learn.microsoft.com/en-us/azure/virtual-machines/"
                               "sizes/gpu-accelerated/ndh100v5-series"),
        "azure_nc_h100_spec": ("https://learn.microsoft.com/en-us/azure/virtual-machines/"
                               "sizes/gpu-accelerated/ncadsh100v5-series"),
        "azure_nc_a100_spec": ("https://learn.microsoft.com/en-us/azure/virtual-machines/"
                               "sizes/gpu-accelerated/nca100v4-series"),
    }


if __name__ == "__main__":
    main()
