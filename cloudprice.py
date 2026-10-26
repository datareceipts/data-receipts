#!/usr/bin/env python3
"""Collect real cloud prices for a fixed reference workload.

Every number this emits is pulled live from a vendor's own pricing source and
stamped with the URL and date. Nothing is typed by hand.

Why not just read the pricing pages: AWS, GCP and Hetzner all render pricing in
JavaScript, so the published HTML contains no numbers. The APIs below are the
authoritative sources those pages are built from.

  python3 cloudprice.py --provider azure
  python3 cloudprice.py --all --out ../youtube-os/pipeline/data/102-cloud-pricing.json
"""
import argparse, datetime, json, pathlib, sys, urllib.request

UA = {"User-Agent": "run-the-numbers/0.1 (pricing research)"}
TODAY = datetime.date.today().isoformat()

# The reference workload. Fixed, documented, identical across every provider —
# this is the whole point. Vendor calculators all assume different workloads.
WORKLOAD = {
    "app_server": {"vcpu": 4, "ram_gb": 16, "count": 1},
    "database":   {"vcpu": 2, "ram_gb": 8, "storage_gb": 100, "managed": True},
    "egress_gb_month": 500,
    "object_storage_gb": 100,
    "hours_per_month": 730,
}


def get_json(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------------------------------------------------------------- Azure
AZ = "https://prices.azure.com/api/retail/prices"


def azure(region="eastus"):
    """Public retail API, no auth. Returns Linux on-demand only."""
    out, src = {}, []
    q = (f"{AZ}?$filter=serviceName eq 'Virtual Machines' and armRegionName eq "
         f"'{region}' and armSkuName eq 'Standard_D4s_v5'")
    d = get_json(q.replace(" ", "%20"))
    src.append(q)
    # Exclude Windows, Spot, Low Priority, Reservations — we want Linux on-demand.
    cands = [i for i in d.get("Items", [])
             if i.get("type") == "Consumption"
             and "Spot" not in i.get("meterName", "")
             and "Low Priority" not in i.get("meterName", "")
             and "Windows" not in i.get("productName", "")]
    if not cands:
        raise RuntimeError("no Azure on-demand Linux SKU matched")
    # the cheapest remaining Consumption row is the Linux on-demand rate
    vm = min(cands, key=lambda i: i["retailPrice"])
    out["vm_hourly_usd"] = vm["retailPrice"]
    out["vm_sku"] = vm["armSkuName"]
    out["vm_product"] = vm["productName"]
    out["vm_monthly_usd"] = round(vm["retailPrice"] * WORKLOAD["hours_per_month"], 2)

    q2 = (f"{AZ}?$filter=serviceName eq 'Bandwidth' and armRegionName eq '{region}'")
    try:
        b = get_json(q2.replace(" ", "%20"))
        src.append(q2)
        # Egress is TIERED and the API returns many unrelated meters. Taking the
        # minimum picks "Inter-Availability Zone" at $0.01 — not internet egress,
        # and ~9x too cheap. Filter to internet routing, then walk the tiers.
        eg = [i for i in b.get("Items", [])
              if i.get("type") == "Consumption"
              and i.get("meterName", "").strip() == "Standard Data Transfer Out"
              and "Routing Preference: Internet" in i.get("productName", "")
              and "China" not in i.get("meterName", "")]
        if eg:
            tiers = sorted({(i.get("tierMinimumUnits", 0), i["retailPrice"])
                            for i in eg})
            out["egress_tiers_usd_per_gb"] = [
                {"from_gb": t, "usd_per_gb": p} for t, p in tiers]
            # bill the workload's 500 GB across the tiers
            gb, cost = WORKLOAD["egress_gb_month"], 0.0
            for idx, (start, price) in enumerate(tiers):
                nxt = tiers[idx + 1][0] if idx + 1 < len(tiers) else float("inf")
                billable = max(0.0, min(gb, nxt) - start)
                cost += billable * price
            out["egress_monthly_usd"] = round(cost, 2)
            out["egress_note"] = ("tiered; first tier is free. "
                                  "Internet routing preference only.")
    except Exception as e:
        out["egress_note"] = f"not retrieved: {e}"
    return out, src


PROVIDERS = {"azure": azure}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    names = list(PROVIDERS) if a.all else ([a.provider] if a.provider else [])
    if not names:
        sys.exit("pick --provider or --all")

    values, sources = {}, {}
    for n in names:
        try:
            v, src = PROVIDERS[n]()
            values[n] = v
            sources[n] = f"{'; '.join(src)} (retrieved {TODAY})"
            print(f"  {n}: ok")
            for k, val in v.items():
                print(f"      {k} = {val}")
        except Exception as e:
            print(f"  {n}: FAILED — {e}")

    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"workload": WORKLOAD, "values": values, "sources": sources},
            indent=2))
        print(f"\n  -> {p}")


if __name__ == "__main__":
    main()
