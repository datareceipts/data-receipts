# 110 — What it costs to run a website

One fixed spec — 2 vCPU / 4 GB, managed Postgres, 50 GB storage, 500 GB egress,
always-on, one US region — priced across three providers.

## Result

| | Monthly | |
|---|---|---|
| Hetzner CPX21 | **$36.37** | egress included |
| DigitalOcean | $54.45 | egress included |
| AWS | **$96.03** | $36.00 of it is egress |

**2.64×, or $716 a year.**

## The line that matters

AWS's bandwidth charge alone is **$36.00**. The entire Hetzner bill is $36.37.
The thing AWS bills you for moving bytes costs as much as the whole server
somewhere else.

Strip egress out and AWS is $60.03 against DigitalOcean's $54.45 — close enough
that the compute and database pricing is broadly competitive. **Egress is 37.5%
of the AWS bill**, and it is the single reason the gap exists at this size.

Both of the other two include far more transfer than the spec uses (Hetzner 2 TB,
DigitalOcean 4 TB), so the 500 GB is free at both.

## Spec first, prices second

`spec.json` is fixed before any price is looked up, and it is in the repo so you
can check it wasn't tuned afterwards. Choosing the spec once you've seen the
prices is how these comparisons get quietly rigged.

Every AWS figure comes from the Price List API, line by line — compute, database,
both storage volumes, egress — rather than one blended number, because the
headline here *is* a line item and a single total would hide it. Egress is not in
the EC2 price list; it has its own offer code (`AWSDataTransfer`) and is tiered,
so the collector picks the tier the spec's volume actually falls into.

`collect.py` refuses to write a partial bill: if any line item can't be found it
exits rather than quietly totalling four of five.

## Where each row overshoots the spec

Nobody sells exactly the spec, so the overshoots are recorded, not hidden:

- **Hetzner** — the smallest US plan with 4 GB RAM is 3 vCPU, one more than asked.
  More importantly it has **no managed Postgres in the US region**, so the database
  runs on the same box. The spec permits that, but self-managed Postgres is not the
  same product as a managed one and this is the row where that matters most.
- **DigitalOcean** — managed DB storage is 30 GiB against the 20 GB asked.
- **AWS** — closest to the spec of the three, and the most expensive.

## Files

| File | What it is |
|---|---|
| `spec.json` | The spec, fixed first. |
| `collect.py` | AWS Price List (EC2, RDS, DataTransfer) + ECB FX. No auth. |
| `hyperscalers.json` | What the APIs returned, itemised. |
| `vendors.json` | Transcribed prices, with URLs and the date read. |
| `compute.py` | Totals and the egress decomposition. |
| `costs.json` | Output. |

```sh
python3 collect.py   # two ~1 GB AWS indexes, slow
python3 compute.py
```

## Limitations

- On-demand list prices. Reserved and committed-use pricing cuts AWS; none of it
  is applied here.
- One region each, single node, no HA, no CDN, no WAF, no support plan.
- **Hetzner's row is self-managed Postgres.** That is a real difference in what
  you get, not just a cheaper price for the same thing.
- Hetzner prices exclude VAT.
- Your own time is not priced, and it is the largest cost in the cheapest row.
- 500 GB egress is an assumption. The AWS figure scales with it; the other two
  don't until you cross their included allowance.
