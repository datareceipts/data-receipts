"""Price three generations of Llama on the GPU each model card actually names.

The trap this is built to avoid: pricing all three on today's H100 would be
tidier and wrong. Llama 2 trained on A100s, and the A100 is cheaper per hour
than the H100, so a single-GPU comparison would quietly understate how much
the real bill grew. Each generation gets its own hardware and its own rate.

Second trap: a vendor that sells H100s but not A100s (Azure's A100 SXM is a
40GB part, a different product) would make the curve steeper by switching
supplier mid-comparison. Only vendors present in BOTH groups are used.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
CMP = json.loads((HERE.parent / "109-gpu-pricing" / "compare.json").read_text())
VENDORS = SPEC["price_vendors"]


def rate(group, vendor):
    for r in CMP["groups"][group]["rows"]:
        if r["vendor"] == vendor:
            return r["usd"]
    raise SystemExit(f"no {vendor} rate for {group} — refusing to switch vendor "
                     f"mid-comparison")


def main():
    gens = SPEC["generations"]
    for g in gens:
        g["rates"] = {v: rate(g["gpu"], v) for v in VENDORS}
        g["totals"] = {v: g["gpu_hours"] * r for v, r in g["rates"].items()}

    print(f"\n  {SPEC['name']}\n")
    head = f"  {'generation':<12}{'released':>9}{'GPU':>16}{'GPU-hours':>13}"
    head += "".join(f"{v.split(' (')[0]:>14}" for v in VENDORS)
    print(head); print("  " + "-" * (len(head) - 2))
    for g in gens:
        line = (f"  {g['label']:<12}{g['released']:>9}{g['gpu']:>16}"
                f"{g['gpu_hours']:>13,}")
        line += "".join(f"{'$'+format(g['totals'][v]/1e6,',.1f')+'M':>14}"
                        for v in VENDORS)
        print(line)

    first, last = gens[0], gens[-1]
    print()
    for v in VENDORS:
        mult = last["totals"][v] / first["totals"][v]
        print(f"  {v:<22} ${first['totals'][v]/1e6:,.1f}M -> "
              f"${last['totals'][v]/1e6:,.1f}M   {mult:.1f}x in 12 months")

    print(f"\n  GPU-hours alone: {first['gpu_hours']:,} -> {last['gpu_hours']:,}"
          f"  ({last['gpu_hours']/first['gpu_hours']:.1f}x)")
    print(f"  Hourly rate also rose: A100 ${first['rates'][VENDORS[0]]} -> "
          f"H100 ${last['rates'][VENDORS[0]]} on {VENDORS[0]}")
    print(f"  CO2 (each card's own figure): "
          + " -> ".join(f"{g['co2_tons']:,}t" for g in gens))

    fl_first, fl_last = first["flagship_hours"], last["flagship_hours"]
    print(f"\n  flagship only: {first['label']} {first['flagship']} "
          f"{fl_first:,} h -> {last['label']} {last['flagship']} {fl_last:,} h"
          f"  ({fl_last/fl_first:.1f}x)")

    out = {
        "generated": CMP["retrieved"], "vendors": VENDORS,
        "generations": [{k: v for k, v in g.items()} for g in gens],
        "labels": [g["label"] for g in gens],
        "hours": [g["gpu_hours"] for g in gens],
        "totals_m": {v: [round(g["totals"][v] / 1e6, 1) for g in gens]
                     for v in VENDORS},
        "growth": {v: round(last["totals"][v] / first["totals"][v], 1)
                   for v in VENDORS},
        "hours_growth": round(last["gpu_hours"] / first["gpu_hours"], 1),
        "flagship_growth": round(fl_last / fl_first, 1),
        "co2": [g["co2_tons"] for g in gens],
        "sources": {g["label"]: g["card"] for g in gens}
                   | {"rates": "109-gpu-pricing/compare.json"},
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
