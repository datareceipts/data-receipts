# 111 — Cloud storage pricing: the same 1 TB, $7 or $253

One terabyte of files, priced across four providers and eight storage tiers,
at list prices, in one region, on 2026-11-16.

## The result

At the spec's 1 TB stored and 100 GB read per month:

| tier | total | storage | retrieval | restore req | requests | egress |
|---|---|---|---|---|---|---|
| Backblaze B2 | **$7.05** | 7.05 | 0 | 0 | 0 | 0 |
| Azure Blob Cold | $11.87 | 3.69 | 3.00 | 0 | 5.18 | 0 |
| S3 Glacier Instant Retrieval | $12.30 | 4.10 | 3.00 | 0 | 5.20 | 0 |
| S3 Standard-IA | $14.40 | 12.80 | 1.00 | 0 | 0.60 | 0 |
| Cloudflare R2 | $15.43 | 15.21 | 0 | 0 | 0.22 | 0 |
| Azure Blob Cool | $17.16 | 15.56 | 1.00 | 0 | 0.60 | 0 |
| Azure Blob Hot | $21.55 | 21.30 | 0 | 0 | 0.25 | 0 |
| S3 Standard | $23.80 | 23.55 | 0 | 0 | 0.25 | 0 |
| S3 Glacier Flexible Retrieval | $29.94 | 3.69 | 1.00 | 25.00 | 0.25 | 0 |
| Azure Blob Archive | **$253.11** | 1.01 | 2.00 | 0 | 250.10 | 0 |

35.9x between cheapest and dearest, for the same terabyte.

## The finding

The archive tiers are the cheapest and the most expensive thing on the list,
and which one they are depends entirely on whether you read the data.

Azure Blob Archive holds a terabyte for **$1.11 a month**. Read 100 GB of it and
the bill is **$253.11** — and $250.10 of that is neither storage nor bandwidth,
it is the per-request charge for 500,000 archive reads at $5.00 per 10,000.
S3 Glacier Flexible Retrieval does the same thing more gently: $3.74 to hold,
$29.94 once you read, of which $25.00 is restore requests.

The crossover — how much of your terabyte you can read each month before the
tier stops beating S3 Standard:

| tier | crossover | as % of stored |
|---|---|---|
| Azure Blob Archive | 8.9 GB | 0.9% |
| S3 Glacier Flexible Retrieval | 76.4 GB | 7.5% |
| S3 Glacier Instant Retrieval | 247.5 GB | 24.2% |
| Azure Blob Cold | 259.1 GB | 25.3% |
| Azure Blob Cool | 763.7 GB | 74.6% |
| S3 Standard-IA | 823.2 GB | 80.4% |
| Cloudflare R2, Backblaze B2 | — | cheaper at every read volume tested |

Archive pricing is not a storage discount. It is a bet that you will not read
the data, and the bet is priced per object, not per byte.

Egress, which was the whole story in video 110, barely appears here: at these
volumes AWS's and Azure's first 100 GB are free, B2 includes 3x stored data,
and R2 charges nothing. The line item that decides this comparison is requests.

## Method

`spec.json` was committed before any price was looked up
(`650f6c0`). It fixes 1 TB stored, 100 GB read, 10,000 writes and 500,000 reads
a month, and declares the sweep range up front so the access rate could not be
chosen afterwards to land on a conclusion.

`collect.py` pulls AWS from the S3 and AWSDataTransfer price lists and Azure
from the Retail Prices API. `compute.py` totals storage + retrieval + restore
requests + requests + egress, and bisects for each crossover.

### Object size

The spec's 100 GB across 500,000 reads implies a 200 KB average object. The
sweep varies how much is read, so either the object count is fixed and objects
grow, or objects are fixed and the request count moves with the bytes. This
uses the second. The first would flatter the archive tiers, because their
charge is per request.

### Two traps in the AWS price list

**`operation` is load-bearing.** Two SKUs share usagetype
`Standard-Retrieval-Bytes` at $0.01 and $0.02; only `operation` separates
Glacier Flexible (`RestoreObject`) from Deep Archive (`DeepArchiveRestoreObject`).
Group `S3-API-Tier3` likewise holds three SKUs at two prices, where
`RestoreObject` is the Glacier restore charge and the `*Transition` ones are
lifecycle moves. Matching on usagetype or group alone silently picks whichever
SKU happens to come first in the file.

**AWS does not publish a Deep Archive storage rate.** There is no
`TimedStorage-GDA-ByteHrs` SKU in the S3 price list for us-east-1, us-west-2 or
eu-west-1, nor in the static feed behind AWS's own S3 pricing page, nor in the
separate Glacier feed. The two SKUs whose volumeType reads `Glacier Deep
Archive` are both GlacierStagingStorage at $0.021/GB-Mo, roughly 21x the real
figure. The only $0.00099 in those files belongs to Intelligent-Tiering Deep
Archive Access — a different product carrying the same rate today. S3 Glacier
Deep Archive is therefore left out of the totals rather than priced from a
look-alike SKU. Its retrieval rates are published and are quoted where
retrieval alone is discussed. Azure Archive, which is fully priced through the
API, carries the archive tier in the comparison.

## Caveats

- **Redundancy is not matched.** S3 Standard replicates across three or more
  availability zones. Azure's East US blob catalogue offers LRS (one
  datacentre), GRS and RA-GRS but no ZRS, so S3 Standard sits between the LRS
  figures used here and GRS. Azure Hot GRS is $0.0458/GB-Mo against LRS's
  $0.0208, which would move Blob Hot from $21.55 to roughly $46. B2 and R2
  publish durability targets but not a comparable zone model.
- Minimum storage durations are quoted, not charged: the spec assumes data
  older than every early-delete window (Standard-IA 30 days, both Glacier
  instant and flexible tiers 90, Deep Archive 180).
- List prices only. No committed-use, reserved or negotiated discounts.
- No CDN. A CDN in front of any of these changes the answer, and R2's free
  egress applies only when the object is served through R2 itself.
- Backblaze publishes $6.95/TB/month and no per-GB rate; $0.00695 is that
  divided by 1000, recorded in vendors.json as derived rather than quoted.
- Google Cloud Storage is excluded: its catalogue API returns 403 without a
  key and the legacy public price list is gone.

## Files

- `spec.json` — the job, fixed before pricing
- `collect.py` → `costs.json` — raw rates from the two price APIs
- `vendors.json` — R2 and B2 from their pages, plus what was excluded and why
- `compute.py` → `result.json` — bills, sweep, crossovers
