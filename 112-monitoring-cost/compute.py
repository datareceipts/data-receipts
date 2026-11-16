"""Total one fixed monitoring workload across three vendors, and sweep the shape.

The three vendors do not sell the same unit. Datadog bills per host, New Relic
bills per seat and per GB with hosts explicitly free, Grafana Cloud bills per
unit of data. So the question "which monitoring vendor is cheapest" has no
answer on its own -- it only has an answer for a given shape of system.

This totals the spec as committed, then sweeps the two dimensions the vendors
disagree about (how many hosts, how many people) to find where the ranking
flips.

Honest accounting note, repeated wherever totals are printed: Datadog's log
indexing is metered per million events and the spec fixes logs in GB, so it is
excluded. That exclusion makes Datadog look cheaper than it is.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
V = {v["vendor"]: v for v in json.loads((HERE / "vendors.json").read_text())["vendors"]}

HOURS = 730


def datadog(hosts, seats, series, logs_gb, traces_gb, containers):
    L = V["Datadog"]["lines"]
    infra = hosts * L["infra_per_host_month"]
    apm = hosts * L["apm_per_host_month"]
    inc_c = hosts * L["containers_included_per_host"]
    cont = max(0, containers - inc_c) * L["container_per_month_prepaid"]
    inc_m = hosts * L["custom_metrics_included_per_host"]
    # Uses the published INGESTED rate; the indexed overage has no published
    # price. Labelled as a substitution everywhere it surfaces.
    metrics = max(0, series - inc_m) / 100 * L["custom_metrics_per_100_ingested"]
    logs = logs_gb * L["logs_ingest_per_gb"]
    return {"hosts": infra, "apm": apm, "containers": cont,
            "metrics": metrics, "logs": logs, "seats": 0.0,
            "total": infra + apm + cont + metrics + logs}


def grafana(hosts, seats, series, logs_gb, traces_gb, containers):
    L = V["Grafana Cloud"]["lines"]
    platform = L["platform_fee_month"]
    metrics = max(0, series - L["metrics_series_included"]) / 1000 * L["metrics_per_1k_series"]
    lg = max(0, logs_gb - L["logs_included_gb"])
    logs = lg * (L["logs_processing_per_gb"] + L["logs_write_per_gb"] + L["logs_retain_per_gb"])
    tg = max(0, traces_gb - L["traces_included_gb"])
    traces = tg * (L["traces_processing_per_gb"] + L["traces_write_per_gb"] + L["traces_retain_per_gb"])
    host_hours = max(0, hosts * HOURS - L["k8s_host_hours_included"])
    k8s = host_hours * L["k8s_host_hour"]
    cont_hours = max(0, containers * HOURS - L["k8s_container_hours_included"])
    k8s += cont_hours * L["k8s_container_hour"]
    apm_hours = max(0, hosts * HOURS - L["app_observability_host_hours_included"])
    apm = apm_hours * L["app_observability_host_hour"]
    users = max(0, seats - L["users_included"]) * L["user_per_month"]
    return {"hosts": k8s, "apm": apm, "containers": 0.0,
            "metrics": metrics, "logs": logs + traces, "seats": users + platform,
            "total": k8s + apm + metrics + logs + traces + users + platform}


def newrelic(hosts, seats, series, logs_gb, traces_gb, containers):
    L = V["New Relic"]["lines"]
    # Everything New Relic ingests lands in one per-GB bucket.
    gb = logs_gb + traces_gb
    data = max(0, gb - L["data_included_gb"]) * L["data_per_gb"]
    n = min(seats, int(L["full_users_max_standard"]))
    users = (L["full_user_first"] + max(0, n - 1) * L["full_user_additional"]) if n else 0.0
    # Seats beyond the Standard cap have to be core users.
    users += max(0, seats - n) * L["core_user_month"]
    return {"hosts": 0.0, "apm": 0.0, "containers": 0.0,
            "metrics": 0.0, "logs": data, "seats": users,
            "total": data + users}


VENDORS = {"Datadog": datadog, "Grafana Cloud": grafana, "New Relic": newrelic}


def bill(fn, hosts=None, seats=None, series=None):
    return fn(hosts if hosts is not None else SPEC["hosts"],
              seats if seats is not None else SPEC["seats"],
              series if series is not None else SPEC["custom_metric_series"],
              SPEC["logs_gb_per_month"], SPEC["traces_gb_per_month"],
              SPEC["containers"])


def main():
    print(f"\n  {SPEC['hosts']} hosts · {SPEC['seats']} seats · "
          f"{SPEC['custom_metric_series']:,} series · "
          f"{SPEC['logs_gb_per_month']} GB logs · {SPEC['traces_gb_per_month']} GB traces\n")
    head = f"  {'vendor':<16}{'total':>9}{'hosts':>9}{'apm':>8}{'cont':>7}{'metrics':>9}{'data':>8}{'seats':>8}"
    print(head); print("  " + "-" * (len(head) - 2))
    rows = {}
    for name, fn in VENDORS.items():
        b = bill(fn); rows[name] = b
        print(f"  {name:<16}{b['total']:>9.2f}{b['hosts']:>9.2f}{b['apm']:>8.2f}"
              f"{b['containers']:>7.2f}{b['metrics']:>9.2f}{b['logs']:>8.2f}{b['seats']:>8.2f}")
    order = sorted(rows.items(), key=lambda kv: kv[1]["total"])
    print(f"\n  cheapest {order[0][0]} ${order[0][1]['total']:.2f}   "
          f"dearest {order[-1][0]} ${order[-1][1]['total']:.2f}   "
          f"spread {order[-1][1]['total']/order[0][1]['total']:.2f}x")
    print("  NOTE: Datadog excludes log indexing (per-event meter). "
          "That exclusion flatters Datadog.")

    def sweep(label, key, values):
        print(f"\n  SWEEP — {label}")
        print(f"  {'':<16}" + "".join(f"{v:>11}" for v in values))
        out = {}
        for name, fn in VENDORS.items():
            tot = [bill(fn, **{key: v})["total"] for v in values]
            out[name] = tot
            print(f"  {name:<16}" + "".join(f"{t:>11.0f}" for t in tot))
        winners = []
        for i, v in enumerate(values):
            w = min(out, key=lambda n: out[n][i])
            winners.append((v, w))
        print(f"  {'cheapest':<16}" + "".join(f"{w[:11]:>11}" for _, w in winners))
        return out, winners

    host_vals = [1, 5, 10, 25, 50, 100]
    seat_vals = [1, 3, 5, 10, 25, 50]
    series_vals = SPEC["sweep_custom_metrics"]
    hosts_out, hosts_win = sweep("as host count rises (seats fixed at "
                                 f"{SPEC['seats']})", "hosts", host_vals)
    seats_out, seats_win = sweep("as team size rises (hosts fixed at "
                                 f"{SPEC['hosts']})", "seats", seat_vals)
    series_out, series_win = sweep("as custom metric series rise", "series", series_vals)

    out = {
        "spec": SPEC["name"],
        "headline": {k: {kk: round(vv, 2) for kk, vv in b.items()}
                     for k, b in rows.items()},
        "cheapest": order[0][0], "dearest": order[-1][0],
        "spread": round(order[-1][1]["total"] / order[0][1]["total"], 2),
        "sweeps": {
            "hosts": {"x": host_vals,
                      "totals": {k: [round(t, 2) for t in v] for k, v in hosts_out.items()},
                      "winner": [w for _, w in hosts_win]},
            "seats": {"x": seat_vals,
                      "totals": {k: [round(t, 2) for t in v] for k, v in seats_out.items()},
                      "winner": [w for _, w in seats_win]},
            "series": {"x": series_vals,
                       "totals": {k: [round(t, 2) for t in v] for k, v in series_out.items()},
                       "winner": [w for _, w in series_win]},
        },
        "sources": {v["vendor"]: v["source"] for v in
                    json.loads((HERE / "vendors.json").read_text())["vendors"]},
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
