"""Multiply Meta's published GPU-hours by the measured market rate for that GPU.

Both inputs are published numbers from primary sources: the GPU-hour total and
the hardware type come from Meta's own model card, and the hourly rates are the
on-demand list prices measured in video 109 for the H100 SXM 80GB -- the exact
product the model card names.

What this is not: Meta's bill. Meta trained on a cluster it owns, so it paid
capex and power, not an hourly rate. This is what the same compute would cost
to rent, which is the only version of the question an outsider can answer with
sourced numbers.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
SRC = json.loads((HERE / "sources.json").read_text())
CMP = json.loads((HERE.parent / "109-gpu-pricing" / "compare.json").read_text())

HOURS = SPEC["gpu_hours"]
GROUP = SPEC["gpu"]


def offers():
    g = CMP["groups"][GROUP]
    seen, out = set(), []
    for o in sorted(g["rows"], key=lambda o: o["usd"]):
        if o["vendor"] in seen:
            continue
        seen.add(o["vendor"])
        out.append({"vendor": o["vendor"], "company": o["vendor"].split(" (")[0],
                    "rate": o["usd"], "total": o["usd"] * HOURS})
    return out


def main():
    rows = offers()
    print(f"\n  {SPEC['model']} — {HOURS:,} GPU-hours on {GROUP}")
    print(f"  (Meta's model card; this prices RENTING, not what Meta spent)\n")
    head = f"  {'vendor':<22}{'$/GPU-hr':>10}{'total':>18}"
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['vendor']:<22}{r['rate']:>10.2f}{'$'+format(r['total'],',.0f'):>18}")

    lo, hi = rows[0], rows[-1]
    gap = hi["total"] - lo["total"]
    spread = hi["total"] / lo["total"]
    print(f"\n  cheapest ${lo['total']:,.0f} ({lo['vendor']})")
    print(f"  dearest  ${hi['total']:,.0f} ({hi['vendor']})")
    print(f"  gap      ${gap:,.0f}   spread {spread:.2f}x")

    tok_m = SPEC["tokens_trained_t"] * 1_000_000      # millions of tokens
    print(f"\n  per million training tokens: "
          f"${lo['total']/tok_m:.2f} to ${hi['total']/tok_m:.2f}")

    one_gpu_years = HOURS / 8760
    print(f"  one GPU running continuously: {one_gpu_years:,.0f} years")

    fam = SPEC["gpu_hours_family"]
    print(f"\n  whole Llama 3.1 family ({fam:,} GPU-hours): "
          f"${lo['rate']*fam:,.0f} to ${hi['rate']*fam:,.0f}")

    out = {
        "generated": SRC["read_on"], "model": SPEC["model"],
        "gpu_hours": HOURS, "gpu": GROUP,
        "rows": [{**r, "total": round(r["total"], 2)} for r in rows],
        "cheap_vendor": lo["vendor"], "cheap_total": round(lo["total"], 2),
        "dear_vendor": hi["vendor"], "dear_total": round(hi["total"], 2),
        "gap": round(gap, 2), "spread": round(spread, 2),
        "per_m_tokens_cheap": round(lo["total"] / tok_m, 2),
        "per_m_tokens_dear": round(hi["total"] / tok_m, 2),
        "one_gpu_years": round(one_gpu_years),
        "family_cheap": round(lo["rate"] * fam, 2),
        "family_dear": round(hi["rate"] * fam, 2),
        "co2_tons": SPEC["co2_tons_405b"],
        "sources": {"gpu_hours": SRC["meta_model_card"]["source"],
                    "rates": CMP["sources"] if "sources" in CMP else
                             "109-gpu-pricing/compare.json"},
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
