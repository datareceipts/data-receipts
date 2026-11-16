# 112 — Datadog vs Grafana vs New Relic: $240, $414, $479

One fixed monitoring workload, priced from three vendors' published pages on
2026-11-16.

## The result

10 hosts, 50 containers, 10,000 custom metric series, 100 GB logs, 20 GB
traces, 5 seats:

| vendor | total | hosts | APM | metrics | data | seats |
|---|---|---|---|---|---|---|
| Grafana Cloud | **$239.88** | 50.68 | 126.70 | 0 | 27.50 | 35.00 |
| New Relic | $414.00 | 0 | 0 | 0 | 8.00 | 406.00 |
| Datadog | $479.00 | 150.00 | 310.00 | 9.00 | 10.00 | 0 |

2.0x between cheapest and dearest — and that spread is the least interesting
thing here, because **the ranking is not stable**.

## The finding

The three vendors do not sell the same unit. Datadog bills per host. New Relic
bills per seat and explicitly charges nothing for hosts. Grafana Cloud bills
per unit of data. So "which monitoring vendor is cheapest" has no answer on its
own. It only has an answer for a given shape of system, and the answer changes
three times across ordinary shapes.

**As you add servers** (5 seats fixed):

| hosts | 1 | 5 | 10 | 25 | 50 | 100 |
|---|---|---|---|---|---|---|
| Datadog | 111 | 274 | 479 | 1,168 | 2,315 | 4,610 |
| Grafana Cloud | **62** | **112** | **240** | 623 | 1,262 | 2,539 |
| New Relic | 414 | 414 | 414 | **414** | **414** | **414** |

New Relic's line is flat, because hosts are free. It is the worst option at one
host and the best option at a hundred.

**As you add people** (10 hosts fixed):

| seats | 1 | 3 | 5 | 10 | 25 | 50 |
|---|---|---|---|---|---|---|
| Datadog | 479 | 479 | 479 | 479 | 479 | **479** |
| Grafana Cloud | 224 | 224 | **240** | **280** | **400** | 600 |
| New Relic | **18** | **216** | 414 | 659 | 1,394 | 2,619 |

Datadog's line is flat, because seats are free. The same ten servers cost New
Relic customers **$18 or $2,619** depending only on how many people are allowed
to look at them.

**As cardinality grows**:

| series | 0 | 1k | 10k | 50k | 100k |
|---|---|---|---|---|---|
| Datadog | 470 | 470 | 479 | 519 | 569 |
| Grafana Cloud | **240** | **240** | **240** | 500 | 825 |
| New Relic | 414 | 414 | 414 | **414** | **414** |

The received wisdom is that Datadog is the one that punishes custom metrics.
On published rates it is the opposite: Datadog's rate is $0.10 per 100 series
and Grafana Cloud's is $6.50 per 1,000, which is $0.65 per 100 — 6.5x more.

What decides a monitoring bill is not how big the system is. It is which of
these three units your organisation happens to have a lot of.

## What is excluded, and which way it cuts

**Datadog's log indexing is excluded, and that flatters Datadog.** It is
metered per million log events; the spec fixes logs in GB. Converting needs an
invented bytes-per-event figure. At a typical 500-byte event, 100 GB is roughly
200 million events, which at $1.70 per million would add about $340 a month and
would more than double the Datadog total. Every figure above understates
Datadog, and it is the dearest vendor anyway.

**Datadog does not publish a price for indexed custom metric overage.** The
billing docs say you pay "an amount that is specified in your current
contract." The only published per-unit rate, $0.10 per 100, is for *ingested*
custom metrics under Metrics without Limits, and that is the rate used above.
So the line item most likely to grow without anyone noticing is the one the
market leader will not quote publicly.

**Better Stack is excluded.** It meters metrics per GB rather than per series,
and the spec fixes series. Translating would need an invented datapoint size
and sampling frequency.

**Self-hosted is excluded.** Running your own Prometheus and Grafana has a real
cost that is mostly your own time, and this compares what vendors charge.

## Caveats

- Annual-commit pricing where published, which is the number on the pricing
  page. Datadog on-demand is $18/host rather than $15, and $36 APM rather than
  $31, so the on-demand Datadog total is higher still.
- New Relic Standard caps full platform users at 5; seats past that are priced
  as core users at $49, which is what the sweep does. A real 50-person team
  would be on Pro at $349/user, making New Relic far worse at the right-hand
  end than the table shows.
- Grafana Cloud's free allowances (2,232 host hours, 37,944 container hours,
  50 GB logs, 50 GB traces, 10,000 series, 3 users) are applied. They are
  generous at small scale and are most of why it wins the spec.
- No enterprise tiers, no negotiated discounts. Every vendor on this list
  discounts at volume and none of them publish by how much.

## Method

`spec.json` was committed before any vendor page was opened (`1ac0851`). The
workload is specified in units none of the three vendors use, then translated
into each vendor's meter in `compute.py`, so the translation is visible and
checkable rather than baked into the choice of workload.

## Files

- `spec.json` — the workload, fixed first
- `vendors.json` — every rate with its URL and the date read, plus exclusions
- `compute.py` → `result.json` — totals and the three sweeps
