# Egress pricing, 8 providers

What 500 GB of internet egress costs per month — the same 500 GB used in the
[cloud pricing comparison](../102-cloud-pricing).

| Provider | $/GB | Free allowance | 500 GB/mo |
|---|---|---|---|
| AWS | $0.09 | 100 GB | **$36.00** |
| Azure | $0.08 | 100 GB | **$32.00** |
| Fly.io | $0.02 | — | **$10.00** |
| DigitalOcean | $0.01 | pooled per-Droplet | **$0.00** |
| Backblaze B2 | $0.01 | 3× stored data | **$0.00** |
| Hetzner | ~$0.001 | 20 TB | **$0.00** |
| Cloudflare R2 | $0.00 | all | **$0.00** |
| Wasabi | $0.00 | all | **$0.00** |

Five of eight charge nothing for the same bytes AWS bills $36 for.

## Markup vs wholesale input

Wholesale IP transit, weighted median for a 100 GigE port in US/EU markets:
**$0.08/Mbps/month** (TeleGeography, Q2 2026).

1 Mbps moves ~328 GB/month at full utilisation. Assuming a
realistic 50% average, the wholesale input is **$0.000487/GB**.

AWS retail is **$0.09/GB** — about **185x**
the input (370x at full port utilisation).

This bounds the input cost. It is **not** a margin calculation — a wholesale port
and a per-GB retail product are different things, with routers, redundancy and
staff in between.

## What it costs at scale

| Monthly egress | AWS | Cloudflare R2 |
|---|---|---|
| 500 GB | $36.00 | $0.00 |
| 5 TB | $441.00 | $0.00 |
| 50 TB | $4,394.20 | $0.00 |
| 500 TB | $29,482.20 | $0.00 |

One-time cost to move 50 TB **out** of S3: **$4,394.20**. That is
data gravity with a price tag.

## The regulatory tell

AWS, Azure and Google have all already waived egress fees — but **only for
customers leaving**, in response to the EU Data Act. If the fee recovered the cost
of bandwidth, that cost would not disappear the moment a customer cancels.

The EU Data Act bans switching charges outright from **2027-01-12**.
Ongoing and multi-cloud traffic remain chargeable.

## Caveats

- **GCP is absent.** Its egress table is JS-rendered and the public pricing
  endpoints are retired; it needs a Cloud Billing API key. Rather than estimate,
  it's omitted. It will be added in the quarterly refresh.
- "Free" is conditional for some: B2 is free to 3× stored data, R2 is free for
  Standard-storage egress to internet.
- Object stores (R2, B2, Wasabi) are not drop-in substitutes for a compute VM's
  egress. They're compared here on egress price alone.
- Hetzner and DigitalOcean include allowances large enough that 500 GB has zero
  *marginal* cost — not merely a low rate.

Raw figures and sources: [`data.json`](data.json)
