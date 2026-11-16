# 113 — Managed Postgres: the same database, $128 or $190

One Postgres workload — 2 vCPU, 8 GB RAM, 100 GB storage, 50 GB egress —
priced across four managed vendors on 2026-11-16.

## The result, always on

| vendor | total | compute | storage | plan | egress |
|---|---|---|---|---|---|
| AWS RDS (db.m6g.large) | **$127.57** | 116.07 | 11.50 | 0 | 0 |
| Supabase (Pro + Large) | $136.50 | 100.00 | 11.50 | 25.00 | 0 |
| Azure Flexible Server | $141.44 | 129.94 | 11.50 | 0 | 0 |
| Neon (Launch) | **$189.76** | 154.76 | 35.00 | 0 | 0 |

1.49x, and the serverless option is the most expensive one.

## The finding

Neon is the dearest way to run a Postgres database that never sleeps, and the
cheapest way to run one that does. It bills compute by the hour and suspends
when idle; the other three are provisioned and bill the full month whether the
database is busy or not.

| active hours/month | 73 (10%) | 182 (25%) | 365 (50%) | 730 (100%) |
|---|---|---|---|---|
| AWS RDS | 127.57 | 127.57 | 127.57 | **127.57** |
| Azure Flexible Server | 141.44 | 141.44 | 141.44 | 141.44 |
| Supabase | 136.50 | 136.50 | 136.50 | 136.50 |
| Neon | **50.48** | **73.58** | **112.38** | 189.76 |

**Neon stops beating AWS RDS at 437 active hours — 60% of the month.**

That number is the point. The usual assumption is that scale-to-zero only pays
for toy projects and dev branches. On list prices it pays until the database is
genuinely busy more than three-fifths of the time. A staging environment, an
internal tool, a B2B app that nobody touches at night or at the weekend — all
of those sit well under 60%.

The flat lines are the other half of the finding. A provisioned database has
exactly one price no matter what you do with it, so every hour you are not
using it is pure waste that never appears as a line item anywhere.

## Caveats

- **The burstable instance is excluded and it is cheaper.** AWS also sells
  db.t4g.large at the same 2 vCPU / 8 GB for $94.17 of compute, which would
  win outright. It is burstable: sustained CPU above a baseline is throttled
  or billed as credits, so it is not the same product as the fixed-performance
  instance the spec asks for. It is collected in `costs.json` and reported,
  not substituted.
- **RDS and Azure can be stopped by hand**, which stops compute charges. Both
  restart themselves after 7 days, so it is not suspend-on-idle and is not
  modelled as such. If you are disciplined about stopping a dev database every
  evening, the flat lines above overstate those two.
- Neon's storage is $0.35/GB-month against roughly $0.115 elsewhere — 3x — so
  a storage-heavy, low-compute database flips the answer back again. At 100 GB
  that is $35 against $11.50.
- Supabase's $136.50 includes a $25 plan fee that buys auth, file storage and
  the rest of the platform. Priced purely as a database it is being charged for
  things this spec does not ask for.
- List prices only: no reserved instances, no committed use, no annual
  discount. AWS reserved pricing in particular would move RDS down
  substantially — see video 104 for how long that takes to pay off.
- Google Cloud SQL is excluded: the Cloud Billing Catalog API returns 403
  without an API key, same as in video 111.

## Method

`spec.json` was committed before any price was looked up (`f22c49b`), including
the active-hours sweep, so the duty cycle could not be chosen afterwards to
favour a vendor.

AWS RDS comes from the RDS price list and Azure from the Retail Prices API.
Neon and Supabase publish no API and are transcribed in `vendors.json` with
URLs and the date read.

### One modelling error worth recording

The first version of `compute.py` scaled AWS and Azure compute by the active
hours as well, which handed them a suspend-on-idle discount neither vendor
offers and made AWS win at every point on the sweep. The sweep only means
anything because three of the four vendors ignore it.

## Files

- `spec.json` — the workload, fixed first
- `collect.py` → `costs.json` — AWS RDS and Azure from their price APIs
- `vendors.json` — Neon and Supabase from their pages, plus exclusions
- `compute.py` → `result.json` — totals, the duty-cycle sweep, the crossover
