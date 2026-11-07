"""Deflate city software-salary medians by their metro's regional price parity.

Nominal medians come from 105-salaries (DOL LCA attested wages). Price levels come
from BEA MARPP. The join is the explicit table in crosswalk.json.

City medians are deflated individually rather than pooled into one figure per MSA.
Pooling would mean averaging medians, which is not a median of anything — and the
city-level view is what makes the within-metro point visible: Redmond and Seattle
share a price level by construction, so any gap between them is pay, not cost.
"""
import json, math, pathlib

HERE = pathlib.Path(__file__).parent
NAT = 100.0  # RPP is indexed to the national average = 100


def load():
    rpp = json.loads((HERE / "rpp.json").read_text())
    cw = json.loads((HERE / "crosswalk.json").read_text())["map"]
    sal = json.loads((HERE.parent / "105-salaries" / "salaries.json").read_text())
    return rpp, cw, sal


def spearman(a, b):
    """Rank correlation between two orderings of the same cities."""
    n = len(a)
    ra = {k: i for i, k in enumerate(a)}
    rb = {k: i for i, k in enumerate(b)}
    d2 = sum((ra[k] - rb[k]) ** 2 for k in a)
    return 1 - 6 * d2 / (n * (n * n - 1))


def implied_weights(rpp):
    """Solve for the expenditure shares implicit in BEA's own published numbers.

    The point the video turns on is that rent varies far more across metros than
    the all-items price level does, which is only possible if rent is a minority
    of the basket. Rather than assert a housing share, recover it: all-items is a
    multiplicative aggregate of the components, so the fit is in logs. A linear
    fit looks fine on the median metro and is off by 12 RPP points on San Jose —
    exactly the metro this video cares most about — so linear is not usable here.
    """
    comp = ("goods", "rents", "utilities", "other_services")
    d = rpp["rpp"]
    rows, y = [], []
    for f in d["all_items"]:
        try:
            rows.append([math.log(float(d[c][f]["value"])) for c in comp])
            y.append(math.log(float(d["all_items"][f]["value"])))
        except (TypeError, ValueError, KeyError):
            continue  # BEA suppresses some component cells
    n = len(rows)
    # shares are constrained to sum to 1, so solve for the first three and subtract
    X = [[r[i] - r[3] for i in range(3)] for r in rows]
    t = [y[k] - rows[k][3] for k in range(n)]
    A = [[sum(X[k][i] * X[k][j] for k in range(n)) for j in range(3)] for i in range(3)]
    b = [sum(X[k][i] * t[k] for k in range(n)) for i in range(3)]
    for i in range(3):
        piv = A[i][i]
        A[i] = [v / piv for v in A[i]]
        b[i] /= piv
        for r2 in range(3):
            if r2 != i:
                f2 = A[r2][i]
                A[r2] = [A[r2][j] - f2 * A[i][j] for j in range(3)]
                b[r2] -= f2 * b[i]
    w = b + [1 - sum(b)]
    resid = sorted(abs(math.exp(y[k]) - math.exp(sum(w[i] * rows[k][i] for i in range(4))))
                   for k in range(n))
    return {
        "shares": {c: round(wt * 100, 1) for c, wt in zip(comp, w)},
        "n_metros": n,
        "median_resid_rpp_points": round(resid[n // 2], 2),
        "p90_resid_rpp_points": round(resid[int(0.9 * n)], 2),
        "max_resid_rpp_points": round(resid[-1], 2),
    }


def spreads(rpp, msas, rows):
    """Max/min ratio of each price component, against the same ratio for salaries."""
    d = rpp["rpp"]
    out = {}
    for lab in ("all_items", "goods", "rents", "utilities", "other_services"):
        v = [float(d[lab][m]["value"]) for m in msas]
        out[lab] = {"min": round(min(v), 1), "max": round(max(v), 1),
                    "spread": round(max(v) / min(v), 2)}
    med = [x["nominal"] for x in rows]
    out["salary_median"] = {"min": min(med), "max": max(med),
                            "spread": round(max(med) / min(med), 2)}
    return out


def main():
    rpp, cw, sal = load()
    allitems = rpp["rpp"]["all_items"]
    rents = rpp["rpp"]["rents"]

    rows = []
    for m in sal["top_metros"]:
        city = m["key"]
        msa = cw[city]["msa"]
        r = float(allitems[msa]["value"])
        rows.append({
            "city": city,
            "msa_fips": msa,
            "msa_name": allitems[msa]["name"].split(" (Metropolitan")[0],
            "n": m["n"],
            "rpp": round(r, 1),
            "rpp_rents": round(float(rents[msa]["value"]), 1),
            "nominal": m["median"],
            "adjusted": round(m["median"] / (r / NAT)),
            "p25_adjusted": round(m["p25"] / (r / NAT)),
            "p75_adjusted": round(m["p75"] / (r / NAT)),
        })

    nom = [x["city"] for x in sorted(rows, key=lambda x: -x["nominal"])]
    adj = [x["city"] for x in sorted(rows, key=lambda x: -x["adjusted"])]
    for x in rows:
        x["rank_nominal"] = nom.index(x["city"]) + 1
        x["rank_adjusted"] = adj.index(x["city"]) + 1
        x["rank_move"] = x["rank_nominal"] - x["rank_adjusted"]  # positive = moved up
        x["pct_change"] = round((x["adjusted"] / x["nominal"] - 1) * 100, 1)

    hi_n = max(rows, key=lambda x: x["nominal"])
    lo_n = min(rows, key=lambda x: x["nominal"])
    hi_a = max(rows, key=lambda x: x["adjusted"])
    lo_a = min(rows, key=lambda x: x["adjusted"])
    # Both premiums hold the SAME two cities — the nominal extremes — because the
    # question is what the adjustment does to one gap. Measuring the nominal gap
    # between the nominal extremes and the adjusted gap between the *adjusted*
    # extremes compares two different pairs and silently overstates what survives.
    prem_nom = (hi_n["nominal"] / lo_n["nominal"] - 1) * 100
    prem_adj = (hi_n["adjusted"] / lo_n["adjusted"] - 1) * 100
    prem_pair = [hi_n["city"], lo_n["city"]]

    # Cities sharing an MSA share a price level by construction, so any gap
    # between them is pay and not cost. Seattle vs Redmond is the cleanest pair.
    same = {}
    for x in rows:
        same.setdefault(x["msa_fips"], []).append(x)
    within = []
    for f, g in same.items():
        if len(g) < 2:
            continue
        a, b2 = max(g, key=lambda x: x["nominal"]), min(g, key=lambda x: x["nominal"])
        within.append({"msa_name": a["msa_name"], "rpp": a["rpp"],
                       "high_city": a["city"], "high": a["nominal"],
                       "low_city": b2["city"], "low": b2["nominal"],
                       "gap": a["nominal"] - b2["nominal"]})
    within.sort(key=lambda x: -x["gap"])

    gained = [x["city"] for x in rows if x["pct_change"] > 0]

    out = {
        "rpp_year": rpp["year"],
        "wage_source": sal["source"],
        "rpp_source": rpp["source"],
        "cities": sorted(rows, key=lambda x: -x["adjusted"]),
        "spearman_nominal_vs_adjusted": round(spearman(nom, adj), 3),
        "top_nominal": nom[0],
        "top_adjusted": adj[0],
        "bottom_nominal": nom[-1],
        "bottom_adjusted": adj[-1],
        "ranking_inverted": nom[0] != adj[0],
        "biggest_riser": max(rows, key=lambda x: x["rank_move"])["city"],
        "biggest_faller": min(rows, key=lambda x: x["rank_move"])["city"],
        "premium_pair": prem_pair,
        "premium_nominal_pct": round(prem_nom, 1),
        "premium_adjusted_pct": round(prem_adj, 1),
        "share_of_gap_explained_by_cost_pct": round((prem_nom - prem_adj) / prem_nom * 100, 1),
        "cities_better_off_adjusted": gained,
        "n_cities_better_off": len(gained),
        "n_cities": len(rows),
        "within_msa_pay_gaps": within,
        "spreads": spreads(rpp, {v["msa"] for v in cw.values()}, rows),
        "implied_weights": implied_weights(rpp),
        "sources": {
            "wages": sal["source"],
            "price_parities": rpp["source"],
            "crosswalk": ("Hand-built city→MSA table in crosswalk.json; "
                          "county-to-MSA assignment per Census 2023 delineation"),
        },
    }
    (HERE / "adjusted.json").write_text(json.dumps(out, indent=1))

    w = max(len(x["city"]) for x in rows)
    print(f"  {'city':<{w}}  {'RPP':>6} {'nominal':>9} {'adjusted':>9} {'chg':>7} {'rank':>9}")
    for x in out["cities"]:
        mv = f"{x['rank_nominal']}->{x['rank_adjusted']}"
        print(f"  {x['city']:<{w}}  {x['rpp']:>6} {x['nominal']:>9,} "
              f"{x['adjusted']:>9,} {x['pct_change']:>6}% {mv:>9}")
    print(f"\n  nominal top: {out['top_nominal']}   adjusted top: {out['top_adjusted']}")
    print(f"  nominal bottom: {out['bottom_nominal']}   adjusted bottom: {out['bottom_adjusted']}")
    print(f"  Spearman nominal vs adjusted: {out['spearman_nominal_vs_adjusted']}")
    print(f"  biggest riser: {out['biggest_riser']}  biggest faller: {out['biggest_faller']}")
    print(f"\n  premium top-vs-bottom: {out['premium_nominal_pct']}% nominal "
          f"-> {out['premium_adjusted_pct']}% adjusted "
          f"({out['share_of_gap_explained_by_cost_pct']}% of the gap is cost)")
    print(f"  better off after adjusting: {out['n_cities_better_off']} of {out['n_cities']} "
          f"— {', '.join(out['cities_better_off_adjusted'])}")
    sp = out["spreads"]
    print(f"  spread  rents {sp['rents']['spread']}x  all-items {sp['all_items']['spread']}x  "
          f"salaries {sp['salary_median']['spread']}x")
    iw = out["implied_weights"]
    print(f"  implied rent share {iw['shares']['rents']}%  "
          f"(median resid {iw['median_resid_rpp_points']} pts, n={iw['n_metros']})")
    w0 = out["within_msa_pay_gaps"][0]
    print(f"  widest same-price-level gap: {w0['high_city']} {w0['high']:,} vs "
          f"{w0['low_city']} {w0['low']:,} = {w0['gap']:,}")


if __name__ == "__main__":
    main()
