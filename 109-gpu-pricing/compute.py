"""Compare GPU rental prices like-for-like, normalised to dollars per GPU-hour.

The comparison is grouped by (GPU model, GPU memory). That grouping is the whole
point: an H100 NVL with 94 GB and an H100 SXM with 80 GB are both "an H100" in
marketing copy and are not the same product, and putting them in one bar chart
would manufacture a spread that isn't there.

Lambda is kept out of the headline spread because its published rates do not
take effect until 2026-11-16; its current rates need an account.
"""
import json, pathlib
from collections import defaultdict

HERE = pathlib.Path(__file__).parent


def load():
    h = json.loads((HERE / "hyperscalers.json").read_text())
    v = json.loads((HERE / "vendors.json").read_text())
    rows = []
    for r in h["rows"]:
        rows.append({"vendor": r["vendor"], "label": r["instance"], "gpu": r["gpu"],
                     "mem": r["gpu_memory_gb"], "n": r["gpu_count"],
                     "usd": r["usd_per_gpu_hour"], "effective": "current",
                     "kind": "hyperscaler"})
    for ven in v["vendors"]:
        for r in ven["rows"]:
            rows.append({"vendor": ven["vendor"], "label": ven["vendor"],
                         "gpu": r["gpu"], "mem": r["gpu_memory_gb"], "n": 1,
                         "usd": r["usd_per_gpu_hour"],
                         "effective": ven["effective"], "kind": "neocloud"})
    return h, v, rows


def company(vendor):
    """RunPod (Secure) and RunPod (Community) are one company, two products."""
    return vendor.split(" (")[0]


def main():
    h, v, rows = load()
    groups = defaultdict(list)
    for r in rows:
        groups[(r["gpu"], r["mem"])].append(r)

    out_groups = {}
    for (gpu, mem), rs in groups.items():
        rs = sorted(rs, key=lambda x: x["usd"])
        cur = [x for x in rs if x["effective"] == "current"]
        # One row per vendor, their cheapest way to rent this GPU. Azure lists the
        # same A100 at three sizes; comparing those against each other would be an
        # Azure-vs-Azure spread dressed up as a market spread.
        best = {}
        for r in cur:
            if r["vendor"] not in best or r["usd"] < best[r["vendor"]]["usd"]:
                best[r["vendor"]] = r
        per_vendor = sorted(best.values(), key=lambda x: x["usd"])
        g = {"gpu": gpu, "memory_gb": mem, "n_offers": len(rs), "rows": rs,
             "n_current": len(cur), "per_vendor": per_vendor,
             "companies": sorted({company(r["vendor"]) for r in per_vendor})}
        if len(per_vendor) >= 2:
            g.update(cheapest=per_vendor[0], dearest=per_vendor[-1],
                     spread=round(per_vendor[-1]["usd"] / per_vendor[0]["usd"], 2),
                     gap_per_hour=round(per_vendor[-1]["usd"] - per_vendor[0]["usd"], 2))
        out_groups[f"{gpu} {mem}GB"] = g

    # Headline: the GPU sold by the most distinct COMPANIES at currently-effective
    # prices — a spread across four SKUs from two companies is not a market.
    # RunPod Secure and Community are one company selling two products.
    headline_key = max((k for k, g in out_groups.items() if "spread" in g),
                       key=lambda k: (len(out_groups[k]["companies"]),
                                      out_groups[k]["spread"]))
    hl = out_groups[headline_key]

    # a month of one GPU, running continuously
    HOURS = 730
    hl_month_cheap = round(hl["cheapest"]["usd"] * HOURS)
    hl_month_dear = round(hl["dearest"]["usd"] * HOURS)

    out = {
        "retrieved": h["retrieved"],
        "hours_per_month": HOURS,
        "headline_group": headline_key,
        "headline": {
            "gpu": hl["gpu"], "memory_gb": hl["memory_gb"],
            "cheapest_vendor": hl["cheapest"]["vendor"], "cheapest": hl["cheapest"]["usd"],
            "dearest_vendor": hl["dearest"]["vendor"], "dearest": hl["dearest"]["usd"],
            "spread": hl["spread"], "gap_per_hour": hl["gap_per_hour"],
            "companies": hl["companies"], "n_companies": len(hl["companies"]),
            "month_cheap": hl_month_cheap, "month_dear": hl_month_dear,
            "month_gap": hl_month_dear - hl_month_cheap,
            "n_offers": hl["n_current"],
        },
        "groups": out_groups,
        "sources": dict(h["sources"], **{
            f"vendor_{i}": f"{ven['vendor']}: {ven['source']} (read {ven['read_on']}"
                           + (f", effective {ven['effective']}" if ven["effective"] != "current" else "")
                           + ")"
            for i, ven in enumerate(v["vendors"], 1)}),
    }
    (HERE / "compare.json").write_text(json.dumps(out, indent=1))

    for k, g in sorted(out_groups.items(), key=lambda kv: -kv[1]["n_offers"]):
        sp = f"{g['spread']}x" if "spread" in g else "—"
        print(f"\n  {k}   ({g['n_offers']} offers, {len(g['companies'])} companies, "
              f"vendor-best spread {sp})")
        for r in g["rows"]:
            eff = "" if r["effective"] == "current" else f"  [from {r['effective']}]"
            print(f"    ${r['usd']:>6,.2f}/GPU-hr  {r['vendor']:<20} {r['label']}{eff}")
    H = out["headline"]
    print(f"\n  HEADLINE — {headline_key}: ${H['cheapest']} ({H['cheapest_vendor']}) "
          f"to ${H['dearest']} ({H['dearest_vendor']}) = {H['spread']}x")
    print(f"  One GPU for a month ({HOURS} h): ${H['month_cheap']:,} vs ${H['month_dear']:,} "
          f"— ${H['month_gap']:,} apart")


if __name__ == "__main__":
    main()
