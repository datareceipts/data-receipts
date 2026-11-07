# 107 — Self-hosting Postgres saves 21%, not 10x

What managed Postgres costs against running it yourself, at one fixed spec.

## The spec

Every option has to meet or beat: **≥8 GB RAM, ≥100 GB storage, one node,
730 hours a month**. Postgres runs out of memory before it runs out of CPU, so
memory is the binding requirement and surplus vCPU is noted, not paid for.

## Where the numbers come from

| Input | How |
| --- | --- |
| AWS RDS compute + storage | AWS Price List API, `AmazonRDS` us-east-1 — pulled |
| Instance vCPU and memory | the same API record, not from memory |
| EUR → USD | ECB daily reference rate — pulled |
| DigitalOcean, Supabase, Neon, Hetzner | transcribed from each vendor's pricing page; URLs and date in `vendors.json` |

Only AWS and the ECB publish machine-readable prices. The other four are
transcribed by hand and every figure is checkable at the URL recorded.

## Result

| Option | | Monthly |
| --- | --- | --- |
| Hetzner CCX23 | self-managed | $96.57 |
| DigitalOcean | managed | $122.10 |
| AWS RDS db.m6g.large | managed | $127.57 |
| Supabase Pro + Large | managed | $136.50 |
| Neon Launch, 2 CU always-on | managed | $189.76 |

**Self-managing saves 21%** against the cheapest managed option — $306 a year —
and 49% against the most expensive. Not the order of magnitude the advice
usually claims.

Two other things fall out of it:

- **The managed providers barely differ.** Cheapest to dearest is 1.55x.
- **Right-sizing changes the answer.** Hetzner CCX13 matches the 8 GB exactly
  at $48.56, which is 2.51x cheaper than managed — but it carries only 80 GB
  of storage, under the spec, so it is reported separately rather than counted
  as like-for-like.

## What this does not price

- **Your own hours.** Backups, failover, patching, monitoring and a tested
  restore path are yours when you self-manage. This is the real cost and the
  one that can't be sourced.
- **High availability.** Every row is a single node.
- **Egress.** Hetzner bundles TB-scale traffic; the managed providers meter it.
- **Reserved and committed-use discounts**, which would pull AWS down.
- **VAT** on the Hetzner price.

Two of those cut toward managed and two toward self-hosting, so the measured
gap isn't systematically flattering to either side.

Neon is priced always-on, which is its worst case — its model is to suspend
compute, and a bursty workload would cost materially less.

## Reproduce

```
python3 collect.py prices.json
python3 compute.py prices.json costs.json
```

Standard library only. Change `SPEC` in `collect.py` to your own requirement.
