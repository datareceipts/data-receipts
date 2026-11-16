"""Total the monthly bill for the spec, per provider and per storage tier.

Every rate comes from costs.json (pulled from a price API) or vendors.json
(transcribed from a vendor page with the date read). Nothing is typed in here.

Two modelling choices that change the answer, stated rather than buried:

Object size. The spec fixes 1 TB stored, 100 GB read and 500,000 reads a month,
which implies a 200 KB average object. The sweep varies how much is read, so
something has to give: either the object count stays at 500,000 and objects get
bigger, or objects stay 200 KB and the request count moves with the bytes. This
uses the second, because request charges are the thing the archive tiers turn
on and pretending a 1 TB read is still 500,000 requests would flatter them.

Restore requests. Glacier Flexible Retrieval and Azure Archive are not readable
in place; every object must be restored or rehydrated first, and that is billed
per request. At 200 KB objects this charge is larger than the storage saving
that motivated the tier, which is the whole point of the video.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "spec.json").read_text())
COSTS = json.loads((HERE / "costs.json").read_text())
VEND = json.loads((HERE / "vendors.json").read_text())

STORED = SPEC["stored_gb"]
HEADLINE = SPEC["headline_retrieval_gb"]
WRITES = SPEC["requests"]["writes_per_month"]
READS_AT_HEADLINE = SPEC["requests"]["reads_per_month"]
OBJECT_GB = HEADLINE / READS_AT_HEADLINE          # 200 KB, from the spec

AWS = COSTS["aws"]
AZ = COSTS["azure"]["blob"]
AWS_EG = AWS["egress"]
AZ_EG = COSTS["azure"]["egress"]


def reads_for(gb):
    """Requests scale with bytes read, at the object size the spec implies."""
    return gb / OBJECT_GB


def aws_tier(name, write_grp, read_grp, restore=None):
    r = AWS["retrieval_per_gb"].get(name, {})
    return {
        "provider": "AWS", "tier": name,
        "storage": AWS["storage_gb_mo"][name],
        "retrieval": r.get("standard", 0.0),
        "restore_req": (AWS["restore_requests"].get(name, {}).get(restore, 0.0)
                        if restore else 0.0),
        "write_req": AWS["requests"][write_grp],
        "read_req": AWS["requests"][read_grp],
        "egress": AWS_EG["usd_per_gb"], "free_egress_gb": AWS_EG["free_gb"],
    }


def az_tier(sku, label):
    s = AZ[sku]
    return {
        "provider": "Azure", "tier": label,
        "storage": s["stored"],
        "retrieval": s.get("retrieval", 0.0),
        "restore_req": 0.0,
        "write_req": s["write_10k"] / 10000,
        "read_req": s["read_10k"] / 10000,
        "egress": AZ_EG["usd_per_gb"], "free_egress_gb": AZ_EG["free_gb"],
    }


def vendor(name):
    v = next(x for x in VEND["vendors"] if x["vendor"] == name)
    if name == "Cloudflare R2":
        return {"provider": "Cloudflare", "tier": "R2 Standard",
                "storage": v["storage_gb_mo"], "retrieval": 0.0, "restore_req": 0.0,
                "write_req": v["class_a_per_million"] / 1e6,
                "read_req": v["class_b_per_million"] / 1e6,
                "egress": 0.0, "free_egress_gb": 0,
                "free_storage_gb": v["free"]["storage_gb"]}
    return {"provider": "Backblaze", "tier": "B2",
            "storage": v["storage_gb_mo_derived"], "retrieval": 0.0,
            "restore_req": 0.0, "write_req": 0.0, "read_req": 0.0,
            "egress": v["egress_usd_per_gb"],
            "free_egress_gb": v["free_egress_multiple_of_stored"] * STORED,
            "free_storage_gb": v["free"]["storage_gb"]}


def bill(t, retrieved_gb):
    reads = reads_for(retrieved_gb)
    billable_storage = max(0, STORED - t.get("free_storage_gb", 0))
    storage = billable_storage * t["storage"]
    retrieval = retrieved_gb * t["retrieval"]
    restore = reads * t["restore_req"]
    requests = WRITES * t["write_req"] + reads * t["read_req"]
    egress = max(0, retrieved_gb - t["free_egress_gb"]) * t["egress"]
    return {"storage": storage, "retrieval": retrieval, "restore": restore,
            "requests": requests, "egress": egress,
            "total": storage + retrieval + restore + requests + egress}


TIERS = [
    aws_tier("S3 Standard", "S3-API-Tier1", "S3-API-Tier2"),
    aws_tier("S3 Standard-IA", "S3-API-SIA-Tier1", "S3-API-SIA-Tier2"),
    aws_tier("S3 Glacier Instant Retrieval", "S3-API-GIR-Tier1", "S3-API-GIR-Tier2"),
    aws_tier("S3 Glacier Flexible Retrieval", "S3-API-Tier1", "S3-API-Tier2",
             restore="standard"),
    az_tier("Hot LRS", "Blob Hot"),
    az_tier("Cool LRS", "Blob Cool"),
    az_tier("Cold LRS", "Blob Cold"),
    az_tier("Archive LRS", "Blob Archive"),
    vendor("Cloudflare R2"),
    vendor("Backblaze B2"),
]


def crossover(a, b, lo=0.0, hi=4096.0):
    """Retrieved GB at which tier b stops being cheaper than tier a."""
    f = lambda g: bill(b, g)["total"] - bill(a, g)["total"]
    if f(lo) > 0 or f(hi) < 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    print(f"\n  {STORED} GB stored, {HEADLINE} GB read/month "
          f"({OBJECT_GB*1e6:.0f} KB objects, {READS_AT_HEADLINE:,.0f} reads)\n")
    head = f"  {'tier':<32}{'total':>9}{'storage':>9}{'retr':>8}{'restore':>9}{'req':>8}{'egress':>8}"
    print(head); print("  " + "-" * (len(head) - 2))
    rows = []
    for t in TIERS:
        b = bill(t, HEADLINE)
        rows.append((t, b))
        print(f"  {t['tier']:<32}{b['total']:>9.2f}{b['storage']:>9.2f}"
              f"{b['retrieval']:>8.2f}{b['restore']:>9.2f}{b['requests']:>8.2f}"
              f"{b['egress']:>8.2f}")

    rows.sort(key=lambda r: r[1]["total"])
    cheap, dear = rows[0], rows[-1]
    print(f"\n  cheapest {cheap[0]['tier']} ${cheap[1]['total']:.2f}  "
          f"dearest {dear[0]['tier']} ${dear[1]['total']:.2f}  "
          f"spread {dear[1]['total']/cheap[1]['total']:.2f}x")

    std = TIERS[0]
    print(f"\n  SWEEP — total $/month as read volume rises")
    sweep = SPEC["retrieval_sweep_gb"]
    print(f"  {'tier':<32}" + "".join(f"{g:>9}" for g in sweep))
    for t in TIERS:
        print(f"  {t['tier']:<32}" +
              "".join(f"{bill(t, g)['total']:>9.2f}" for g in sweep))

    print(f"\n  CROSSOVER vs {std['tier']} (GB read/month where it stops winning)")
    for t in TIERS[1:]:
        x = crossover(std, t)
        at0 = bill(t, 0)["total"]
        if x is None:
            verdict = ("never cheaper" if at0 >= bill(std, 0)["total"]
                       else "cheaper across the whole range")
            print(f"    {t['tier']:<32} {verdict}")
        else:
            print(f"    {t['tier']:<32} {x:>8.1f} GB  "
                  f"({x/STORED*100:.1f}% of what is stored)")

    out = {
        "spec": SPEC["name"], "stored_gb": STORED,
        "headline_retrieval_gb": HEADLINE,
        "object_kb": round(OBJECT_GB * 1e6),
        "headline": {t["tier"]: {k: round(v, 4) for k, v in bill(t, HEADLINE).items()}
                     for t in TIERS},
        "sweep": {t["tier"]: {str(g): round(bill(t, g)["total"], 2) for g in sweep}
                  for t in TIERS},
        "crossover_vs_s3_standard_gb": {
            t["tier"]: (round(crossover(std, t), 1) if crossover(std, t) else None)
            for t in TIERS[1:]},
        "sources": COSTS["sources"] | {"vendors": "vendors.json, see read_on dates"},
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
