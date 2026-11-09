"""Total the fixed spec across providers and show where the money goes.

The interesting number here is not the total, it is one line of it, so the AWS
bill is kept itemised all the way through rather than collapsed into a figure.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent


def main():
    h = json.loads((HERE / "hyperscalers.json").read_text())
    v = json.loads((HERE / "vendors.json").read_text())
    fx = h["fx"]["rate"]

    rows = [{"vendor": "AWS", "monthly": h["aws_total"], "region": "us-east-1",
             "lines": [{"item": a["item"], "monthly": a["monthly"]}
                       for a in h["aws"].values()],
             "egress_cost": h["aws"]["egress"]["monthly"], "self_managed_db": False}]
    for ven in v["vendors"]:
        tot = 0.0
        lines = []
        for l in ven["lines"]:
            m = l["monthly"] if "monthly" in l else round(l["monthly_eur"] * fx, 2)
            lines.append({"item": l["item"], "monthly": m})
            tot += m
        rows.append({"vendor": ven["vendor"], "monthly": round(tot, 2),
                     "region": ven["region"], "lines": lines, "egress_cost": 0.0,
                     "self_managed_db": ven.get("self_managed_db", False),
                     "overshoot": ven.get("overshoot")})

    rows.sort(key=lambda r: r["monthly"])
    cheap, dear = rows[0], rows[-1]
    egress = egress_src = h["aws"]["egress"]

    # How the bill moves with traffic. Capped at the smallest included allowance
    # (Hetzner's 2 TB) because past that the other two start charging overage and
    # I have no sourced overage rate for either -- extrapolating there would be
    # inventing numbers. Within the cap, both are genuinely flat.
    cap_gb = min(ven.get("egress_included_gb", 0) for ven in v["vendors"])
    base_aws = round(h["aws_total"] - egress_src["monthly"], 2)
    scale = []
    for gb in (SPEC_EGRESS := [h["spec"]["egress_gb"], 1000, cap_gb]):
        billable = max(0, gb - egress_src["free_gb"])
        a = round(base_aws + billable * egress_src["usd_per_gb"], 2)
        scale.append({"egress_gb": gb, "aws": a,
                      **{r["vendor"]: r["monthly"] for r in rows if r["vendor"] != "AWS"},
                      "spread_vs_cheapest": round(a / cheap["monthly"], 2)})

    out = {
        "retrieved": h["retrieved"],
        "scaling": {"cap_gb": cap_gb, "cap_reason":
                    "smallest included traffic allowance among the non-AWS rows",
                    "rows": scale}, "spec": h["spec"], "fx": h["fx"],
        "rows": rows,
        "cheapest": cheap["vendor"], "cheapest_total": cheap["monthly"],
        "dearest": dear["vendor"], "dearest_total": dear["monthly"],
        "spread": round(dear["monthly"] / cheap["monthly"], 2),
        "gap_month": round(dear["monthly"] - cheap["monthly"], 2),
        "gap_year": round((dear["monthly"] - cheap["monthly"]) * 12, 2),
        # the line the video turns on
        "aws_egress": egress["monthly"],
        "egress_vs_cheapest_total": round(egress["monthly"] / cheap["monthly"] * 100),
        "aws_egress_share_pct": round(egress["monthly"] / dear["monthly"] * 100, 1),
        "aws_without_egress": round(dear["monthly"] - egress["monthly"], 2),
        "sources": dict(h["sources"], **{
            f"{ven['vendor'].lower()}_{i}": f"{l['source']} (read {ven['read_on']})"
            for ven in v["vendors"] for i, l in enumerate(ven["lines"], 1)}),
    }
    (HERE / "costs.json").write_text(json.dumps(out, indent=1))

    for r in rows:
        print(f"\n  {r['vendor']}  ${r['monthly']:,.2f}/mo   [{r['region']}]")
        for l in r["lines"]:
            print(f"      {l['item']:38} ${l['monthly']:>7,.2f}")
    print(f"\n  cheapest {cheap['vendor']} ${cheap['monthly']:,.2f} → "
          f"dearest {dear['vendor']} ${dear['monthly']:,.2f}  = {out['spread']}x")
    print(f"  ${out['gap_month']:,.2f}/mo, ${out['gap_year']:,.2f}/yr")
    print(f"\n  AWS egress alone: ${out['aws_egress']:,.2f} — "
          f"{out['egress_vs_cheapest_total']}% of the entire {cheap['vendor']} bill")
    print(f"  Egress is {out['aws_egress_share_pct']}% of the AWS bill; "
          f"without it AWS is ${out['aws_without_egress']:,.2f}")
    print(f"\n  scaling with traffic (capped at {cap_gb} GB, {out['scaling']['cap_reason']}):")
    for r in scale:
        others = "  ".join(f"{k} ${r[k]:,.2f}" for k in r
                           if k not in ("egress_gb", "aws", "spread_vs_cheapest"))
        print(f"    {r['egress_gb']:>5} GB  AWS ${r['aws']:>8,.2f}   {others}"
              f"   = {r['spread_vs_cheapest']}x")


if __name__ == "__main__":
    main()
