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
