"""Total one terabyte of traffic along five paths, changing only the destination.

Cross-AZ is billed in both directions and both sides land on the same account's
bill, so it is counted twice. That is the single easiest thing to undercount by
half in an AWS networking estimate.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
C = json.loads((HERE / "costs.json").read_text())

GB = SPEC["volume_gb"]
HOURS = SPEC["fixed_resources"]["nat_gateway_hours"]
FREE = C["free_egress_gb"]
XAZ = C["intra_region_variants"]["IntraRegion"]["usd_per_gb"]
BILLABLE_EGRESS = max(0, GB - FREE)


def paths():
    internet = BILLABLE_EGRESS * C["internet_per_gb"]
    nat_data = GB * C["nat_per_gb"]
    nat_fixed = HOURS * C["nat_per_hour"]
    return [
        {"id": "same_az", "label": "Another instance, same AZ",
         "transfer": 0.0, "fixed": 0.0, "note": "private IP, in-zone"},
        {"id": "cross_az", "label": "Another instance, another AZ",
         "transfer": GB * XAZ * 2, "fixed": 0.0,
         "note": f"${XAZ}/GB each way, both sides billed"},
        {"id": "cross_region", "label": f"Another region ({C['cross_region_to']})",
         "transfer": GB * C["cross_region_per_gb"], "fixed": 0.0,
         "note": "outbound only"},
        {"id": "internet", "label": "The internet, public subnet",
         "transfer": internet, "fixed": 0.0,
         "note": f"first {FREE} GB free"},
        {"id": "internet_nat", "label": "The internet, via NAT Gateway",
         "transfer": internet + nat_data, "fixed": nat_fixed,
         "note": "egress + NAT processing + NAT hours"},
    ]


def main():
    rows = paths()
    for r in rows:
        r["total"] = r["transfer"] + r["fixed"]
    print(f"\n  {GB} GB a month. Only the destination changes.\n")
    head = f"  {'destination':<34}{'total':>9}{'transfer':>10}{'fixed':>8}"
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['label']:<34}{r['total']:>9.2f}{r['transfer']:>10.2f}{r['fixed']:>8.2f}")
        print(f"  {'':<34}{r['note']}")
    paid = [r for r in rows if r["total"] > 0]
    cheap, dear = min(paid, key=lambda r: r["total"]), max(rows, key=lambda r: r["total"])
    print(f"\n  free: {rows[0]['label']}")
    print(f"  dearest: {dear['label']} ${dear['total']:.2f}")
    print(f"  cheapest paid: {cheap['label']} ${cheap['total']:.2f}  "
          f"→ {dear['total']/cheap['total']:.1f}x")

    nat = next(r for r in rows if r["id"] == "internet_nat")
    plain = next(r for r in rows if r["id"] == "internet")
    surcharge = nat["total"] - plain["total"]
    print(f"\n  NAT surcharge over a public subnet: ${surcharge:.2f} "
          f"({surcharge/plain['total']*100:.0f}% on top)")
    print(f"    of which fixed (the gateway existing): ${nat['fixed']:.2f}")
    print(f"    per-GB processing:                     ${GB*C['nat_per_gb']:.2f}")
    print(f"  Multi-AZ needs one NAT per zone: 3 zones = "
          f"${nat['fixed']*3:.2f} fixed before a byte moves")

    v = C["intra_region_variants"]
    print(f"\n  AMBIGUITY — identical descriptions, different prices:")
    for k, d in sorted(v.items()):
        print(f"    {k:<22} {d['usagetype']:<34} ${d['usd_per_gb']}")

    out = {"generated": C["generated"], "volume_gb": GB,
           "rows": [{k: (round(x, 2) if isinstance(x, float) else x)
                     for k, x in r.items()} for r in rows],
           "dearest": dear["label"], "dearest_total": round(dear["total"], 2),
           "cheapest_paid": cheap["label"], "cheapest_paid_total": round(cheap["total"], 2),
           "nat_surcharge": round(surcharge, 2),
           "nat_surcharge_pct": round(surcharge / plain["total"] * 100),
           "nat_fixed": round(nat["fixed"], 2),
           "nat_fixed_3az": round(nat["fixed"] * 3, 2),
           "internet_total": round(plain["total"], 2),
           "cross_az_total": round(rows[1]["total"], 2),
           "intra_region_variants": v,
           "sources": C["sources"]}
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
