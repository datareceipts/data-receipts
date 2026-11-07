"""Normalise every vendor to the same spec and compare.

The spec is >= 8 GB RAM, >= 100 GB storage, one node, running all month. Where
a vendor's nearest plan over-delivers, that is noted rather than discounted —
you cannot buy half a plan.

  python3 compute.py prices.json costs.json
"""
import json, sys

HOURS = 730


def main(pricefile, out):
    d = json.load(open(pricefile))
    spec, fx = d["spec"], d["fx"]["rate"]
    need_gb = spec["storage_gb"]
    rows = []

    r = d["aws_rds"]
    storage = need_gb * r["storage"]["usd_gb_month"]
    rows.append({
        "vendor": "AWS RDS", "plan": r["instance"], "managed": True,
        "vcpu": int(r["vcpu"]), "ram_gb": 8, "storage_gb": need_gb,
        "compute_usd": round(r["usd_hour"] * HOURS, 2),
        "storage_usd": round(storage, 2),
        "total_usd": round(r["usd_hour"] * HOURS + storage, 2)})

    for v in d["vendors"]["rows"]:
        name, plan = v["vendor"], v["plan"]
        inc = v.get("storage_included_gb", 0)
        extra_gb = max(0, need_gb - inc)
        like_for_like = inc >= need_gb or v.get("storage_extra_usd_gb") is not None

        if "monthly_eur" in v:
            compute = v["monthly_eur"] * fx
            storage = 0.0
        elif "compute_usd_cu_hour" in v:
            compute = v["compute_usd_cu_hour"] * v["compute_units"] * HOURS
            storage = extra_gb * v["storage_extra_usd_gb"]
        elif "base_monthly_usd" in v:
            compute = (v["base_monthly_usd"] + v["compute_monthly_usd"]
                       - v.get("compute_credit_usd", 0))
            storage = extra_gb * v["storage_extra_usd_gb"]
        else:
            compute = v["monthly_usd"]
            storage = extra_gb * v.get("storage_extra_usd_gb", 0)

        rows.append({
            "vendor": name, "plan": plan,
            "managed": "self-managed" not in name,
            "vcpu": v["vcpu"], "ram_gb": v["ram_gb"],
            # A plan whose storage is fixed and below spec reports what it
            # actually has, not what was asked for.
            "storage_gb": (max(inc, need_gb) if inc >= need_gb
                           else (need_gb if v.get("storage_extra_usd_gb") else inc)),
            "meets_spec": inc >= need_gb or extra_gb == 0 or
                          v.get("storage_extra_usd_gb") is not None,
            "compute_usd": round(compute, 2), "storage_usd": round(storage, 2),
            "total_usd": round(compute + storage, 2), "note": v.get("note", "")})

    # CCX13 is the one row that cannot reach 100 GB, so it is reported but kept
    # out of the like-for-like set.
    for row in rows:
        if row["plan"] == "CCX13":
            row["meets_spec"] = False
    lfl = [r for r in rows if r.get("meets_spec", True)]
    lfl.sort(key=lambda x: x["total_usd"])
    managed = [r for r in lfl if r["managed"]]
    selfm = [r for r in lfl if not r["managed"]]
    undersized = [r for r in rows if not r.get("meets_spec", True)]

    cheapest_managed = min(managed, key=lambda x: x["total_usd"])
    dearest_managed = max(managed, key=lambda x: x["total_usd"])
    cheapest_self = min(selfm, key=lambda x: x["total_usd"])

    summary = {
        "managed_spread": round(dearest_managed["total_usd"] / cheapest_managed["total_usd"], 2),
        "cheapest_managed": cheapest_managed, "dearest_managed": dearest_managed,
        "cheapest_self": cheapest_self,
        "self_vs_cheapest_managed": round(
            cheapest_managed["total_usd"] / cheapest_self["total_usd"], 2),
        "self_vs_dearest_managed": round(
            dearest_managed["total_usd"] / cheapest_self["total_usd"], 2),
        "annual_saving_vs_cheapest": round(
            (cheapest_managed["total_usd"] - cheapest_self["total_usd"]) * 12, 2),
        "annual_saving_vs_dearest": round(
            (dearest_managed["total_usd"] - cheapest_self["total_usd"]) * 12, 2),
    }

    json.dump({"retrieved": d["retrieved"], "spec": spec, "fx": d["fx"],
               "rows": lfl, "undersized": undersized, "summary": summary,
               "excluded": [
                   "Your own time. Self-managing means backups, failover, "
                   "patching, monitoring and restores are yours.",
                   "High availability. Every row is a single node.",
                   "Egress. Hetzner includes TB-scale traffic; the managed "
                   "providers meter it separately.",
                   "Reserved and committed-use discounts.",
                   "VAT on the Hetzner price.",
               ]}, open(out, "w"), indent=2)

    print(f"\n  SPEC: >= {spec['ram_gb']} GB RAM, >= {spec['storage_gb']} GB storage, "
          f"1 node, {HOURS} h/month\n")
    for r in lfl:
        tag = "managed" if r["managed"] else "SELF"
        print(f"  {r['vendor']:<24} {r['plan']:<22} {tag:<8} "
              f"{r['vcpu']} vCPU / {r['ram_gb']:>2} GB   ${r['total_usd']:>8,.2f}/mo")
    for r in undersized:
        print(f"  {r['vendor']:<24} {r['plan']:<22} {'(under)':<8} "
              f"{r['vcpu']} vCPU / {r['ram_gb']:>2} GB   ${r['total_usd']:>8,.2f}/mo"
              f"   — only {r['storage_gb']} GB")
    s = summary
    print(f"\n  managed spread:            {s['managed_spread']}x "
          f"(${s['cheapest_managed']['total_usd']:,.2f} to ${s['dearest_managed']['total_usd']:,.2f})")
    print(f"  self vs cheapest managed:  {s['self_vs_cheapest_managed']}x  "
          f"(${s['annual_saving_vs_cheapest']:,.0f}/yr)")
    print(f"  self vs dearest managed:   {s['self_vs_dearest_managed']}x  "
          f"(${s['annual_saving_vs_dearest']:,.0f}/yr)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
