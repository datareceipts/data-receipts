"""Total the fixed Postgres workload per vendor, then sweep the duty cycle.

Three of the four vendors sell a month of a machine. Neon sells compute-hours.
That difference does nothing at all to the headline figure and everything to
the answer, which is why the spec declared the active-hours sweep before any
price was looked up.

Egress is included everywhere at this volume and is carried as a line anyway,
so that it is visibly zero rather than quietly dropped.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
C = json.loads((HERE / "costs.json").read_text())
V = {v["vendor"]: v for v in json.loads((HERE / "vendors.json").read_text())["vendors"]}

GB = SPEC["storage_gb"]
EG = SPEC["egress_gb"]
FULL = SPEC["hours"]
AWS_INST = "db.m6g.large"


def aws(active_h):
    # A provisioned RDS instance bills every hour it exists, busy or idle.
    # It can be stopped by hand, but it restarts itself after 7 days, so it
    # does not suspend on idle and active_h does not reduce the bill.
    comp = C["aws"][AWS_INST]["usd_per_hour"] * FULL
    st = C["aws"]["storage"]["usd_per_gb_month"] * GB
    eg = max(0, EG - C["egress"]["free_gb"]) * C["egress"]["usd_per_gb"]
    return {"compute": comp, "storage": st, "egress": eg, "plan": 0.0,
            "total": comp + st + eg}


def azure(active_h):
    # Same as RDS: provisioned, billed for the whole month. Azure Flexible
    # Server can also be stopped manually for up to 7 days; that is an
    # operational choice, not suspend-on-idle, so it is not modelled here.
    comp = C["azure"]["compute"]["usd_per_hour"] * FULL
    st = C["azure"]["storage"]["usd_per_gb_month"] * GB
    return {"compute": comp, "storage": st, "egress": 0.0, "plan": 0.0,
            "total": comp + st}


def neon(active_h):
    v = V["Neon"]
    comp = active_h * 2 * v["cu_per_hour"]          # 2 CU for 2 vCPU / 8 GB
    st = GB * v["storage_gb_month"]
    eg = max(0, EG - v["egress_included_gb"]) * v["egress_per_gb"]
    return {"compute": comp, "storage": st, "egress": eg, "plan": 0.0,
            "total": comp + st + eg}


def supabase(active_h):
    v = V["Supabase"]
    # Flat: the add-on is billed by the month whether or not the database is busy.
    comp = v["compute_addon_month"] - v["compute_credit_month"]
    plan = v["plan_fee_month"]
    st = max(0, GB - v["storage_included_gb"]) * v["storage_gb_month"]
    eg = max(0, EG - v["egress_included_gb"]) * v["egress_per_gb"]
    return {"compute": comp, "storage": st, "egress": eg, "plan": plan,
            "total": comp + plan + st + eg}


VENDORS = {"AWS RDS": aws, "Azure Flexible Server": azure,
           "Neon": neon, "Supabase": supabase}


def main():
    print(f"\n  {SPEC['vcpu']} vCPU · {SPEC['ram_gb']} GB · {GB} GB storage · "
          f"{EG} GB egress · always on ({FULL} h)\n")
    head = f"  {'vendor':<22}{'total':>9}{'compute':>10}{'storage':>9}{'plan':>8}{'egress':>8}"
    print(head); print("  " + "-" * (len(head) - 2))
    rows = {}
    for n, fn in VENDORS.items():
        b = fn(FULL); rows[n] = b
        print(f"  {n:<22}{b['total']:>9.2f}{b['compute']:>10.2f}{b['storage']:>9.2f}"
              f"{b['plan']:>8.2f}{b['egress']:>8.2f}")
    order = sorted(rows.items(), key=lambda kv: kv[1]["total"])
    print(f"\n  cheapest {order[0][0]} ${order[0][1]['total']:.2f}   "
          f"dearest {order[-1][0]} ${order[-1][1]['total']:.2f}   "
          f"spread {order[-1][1]['total']/order[0][1]['total']:.2f}x")
    print(f"  (AWS burstable db.t4g.large would be "
          f"${C['aws']['db.t4g.large']['monthly']:.2f} compute, "
          f"a different product — see vendors.json)")

    hrs = SPEC["sweep_active_hours"]
    print(f"\n  SWEEP — as the database idles ({FULL} h is always on)")
    print("  Only Neon suspends on idle. The other three are provisioned and")
    print("  bill the full month regardless, which is the entire point.")
    print(f"  {'':<22}" + "".join(f"{h:>10}" for h in hrs))
    sw = {}
    for n, fn in VENDORS.items():
        tot = [fn(h)["total"] for h in hrs]
        sw[n] = tot
        print(f"  {n:<22}" + "".join(f"{t:>10.2f}" for t in tot))
    win = [min(sw, key=lambda n: sw[n][i]) for i in range(len(hrs))]
    print(f"  {'cheapest':<22}" + "".join(f"{w[:10]:>10}" for w in win))

    # where Neon stops winning
    cross = None
    best_flat = min((n for n in VENDORS if n != "Neon"),
                    key=lambda n: VENDORS[n](FULL)["total"])
    lo, hi = 0.0, float(FULL)
    f = lambda h: neon(h)["total"] - VENDORS[best_flat](h)["total"]
    if f(lo) < 0 < f(hi):
        for _ in range(80):
            mid = (lo + hi) / 2
            if f(mid) < 0:
                lo = mid
            else:
                hi = mid
        cross = (lo + hi) / 2
        print(f"\n  Neon stops beating {best_flat} at {cross:.0f} active hours "
              f"({cross/FULL*100:.0f}% of the month)")

    out = {
        "generated": C["generated"], "spec": SPEC["name"],
        "headline": {k: {kk: round(vv, 2) for kk, vv in b.items()}
                     for k, b in rows.items()},
        "cheapest": order[0][0], "dearest": order[-1][0],
        "spread": round(order[-1][1]["total"] / order[0][1]["total"], 2),
        "burstable_note": C["aws"]["db.t4g.large"]["monthly"],
        "sweep": {"hours": hrs,
                  "totals": {k: [round(t, 2) for t in v] for k, v in sw.items()},
                  "winner": win},
        "neon_crossover_hours": round(cross) if cross else None,
        "neon_crossover_pct": round(cross / FULL * 100) if cross else None,
        "crossover_against": best_flat,
        "sources": C["sources"] | {"vendors": "vendors.json, see read_on"},
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
