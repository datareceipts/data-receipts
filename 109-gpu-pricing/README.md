# 109 — What an H100 actually costs per hour

On-demand GPU rental prices across AWS, Azure and the neoclouds, normalised to
**dollars per GPU per hour** and grouped so only identical GPUs are compared.

## Result

| H100 SXM 80GB | $/GPU-hr | A month (730 h) |
|---|---|---|
| RunPod Community | **$2.69** | $1,964 |
| RunPod Secure | $3.99 | $2,913 |
| AWS `p5.48xlarge` | $6.88 | $5,022 |
| Azure `ND96isr_H100_v5` | **$12.29** | $8,972 |

**4.57× between cheapest and dearest, for the same chip.** One GPU running
continuously for a month is $1,964 or $8,972 depending only on where you rent it.

## The comparison is grouped, deliberately

"An H100" is three different products. The SXM 80GB, the PCIe 80GB and the NVL
94GB all get marketed as H100s and they do not cost the same. Putting them in one
chart manufactures a spread that isn't there, so every comparison here is within
a single (model, memory) group.

The same applies within a vendor: Azure lists the same A100 PCIe 80GB at one, two
and four GPUs per VM for $3.67, $4.78 and $4.78 per GPU-hour. The spread uses each
vendor's **cheapest** route to a given GPU, so an Azure-vs-Azure gap never shows up
as a market gap. RunPod Secure and Community are counted as one company.

## What the 4.57× is not

It is not pure margin. Going from Azure's ND series to RunPod Community gives up:

- **InfiniBand.** Azure's ND SKU has 400 Gbps per GPU of Quantum-2 InfiniBand with
  GPU Direct RDMA, which is what makes multi-node training work. That is the
  reason the ND series is priced above Azure's own single-H100 NC SKU ($6.98).
- **A datacentre SLA.** RunPod Community is third-party hosts renting out their
  own hardware.
- Enterprise compliance, committed capacity, and the rest of the hyperscaler
  surface.

If you are fine-tuning on one node, you are paying for an interconnect you will
never use. If you are training across 64 nodes, the cheap row is not an option.

## Files

| File | What it is |
|---|---|
| `collect.py` | Pulls AWS Price List + Azure Retail Prices. No auth required. |
| `hyperscalers.json` | What those APIs returned. |
| `vendors.json` | Neocloud prices, transcribed, with source URL and date read. |
| `compute.py` | Grouping, per-vendor normalisation, spreads. |
| `compare.json` | Output. |

```sh
python3 collect.py   # ~1 GB AWS index, slow
python3 compute.py
```

## Limitations

- **On-demand list prices only.** Reserved, committed-use and spot pricing all cut
  the hyperscaler numbers, and spot in particular would narrow the gap a lot.
- Single region each (AWS `us-east-1`, Azure `eastus`).
- GPU counts come from vendor documentation, not from the price label — AWS
  reports "640 GB HBM3" for a p5 and Azure reports an accelerator-memory total,
  and neither states a per-GPU model. Doc URLs are in `compare.json`.
- **Lambda is excluded from the headline spread.** Its published page states the
  listed rates take effect 2026-11-16; current rates are behind a login. Its rows
  are shown separately and labelled.
- Availability is not priced. A cheap H100 you cannot get is not a price.
