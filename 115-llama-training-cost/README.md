# 115 — The cost to train Llama 3.1 405B: $83M or $379M

Two published numbers, multiplied. Meta's own GPU-hour total for Llama 3.1
405B, and the measured market rate for the exact GPU Meta names.

## The result

30,840,000 GPU-hours on H100 SXM 80GB:

| vendor | $/GPU-hr | total |
|---|---|---|
| RunPod (Community) | $2.69 | **$82,959,600** |
| RunPod (Secure) | $3.99 | $123,051,600 |
| Lambda | $4.59 | $141,555,600 |
| AWS | $6.88 | $212,179,200 |
| Azure | $12.29 | **$379,023,600** |

**4.57x. A $296,064,000 gap for identical compute.**

Per million training tokens, across 15 trillion tokens: **$5.53 to $25.27**.
One H100 running continuously would need **3,521 years**.

The whole Llama 3.1 family — 39.3M GPU-hours across 8B, 70B and 405B — is
$105.7M to $483.0M on the same rates.

## What this is, and what it is not

**This is not Meta's bill.** Meta trained on a cluster it owns. It paid capital
expenditure, power and staff, not an hourly rental rate. Nobody outside Meta
knows what that came to, and this does not claim to.

What it is: what the same compute would cost *you*, which is the only version
of the question an outsider can answer with sourced numbers. And the useful
part is not the absolute figure, it is the spread — the same published workload
is a $83M project or a $379M project depending only on which vendor's list
price you pay.

**Nobody books 30 million GPU-hours on demand.** A reservation that size is
negotiated and cheaper than any number above. The on-demand figure is an upper
bound on each vendor's own list price, and the comparison between vendors is
the point.

Compute only. No storage, no networking, no data acquisition, no salaries, no
failed runs, no research time. The real cost of a frontier model is larger than
its largest line item.

## Two errors in the secondary coverage

Both were caught by reading the model card rather than the write-ups.

**The CO2 figure.** Widely reported as 11,390 tons for the 405B model. The
model card gives **8,930 tons** for the 405B alone; 11,390 is the total across
the whole Llama 3.1 family. The card also states market-based emissions of 0,
attributed to Meta's renewable electricity matching.

**The cluster figure.** "16,384 H100s for 54 days" circulates widely. That is
21.2M GPU-hours, which does not reconcile with the published 30.84M. Neither
cluster size nor wall-clock duration is used here, because the numbers that
circulate for them do not survive multiplication.

## Sources

- GPU-hours, hardware type and emissions: Meta's Llama 3.1 405B model card,
  table *"Training Time (GPU hours) / Training Location-Based Greenhouse Gas
  Emissions (tons CO2eq)"*, read 2026-11-16. The card names
  **H100-80GB (TDP of 700W)**.
- Hourly rates: on-demand list prices collected in
  [109-gpu-pricing](../109-gpu-pricing), refreshed 2026-11-16, restricted to
  the **H100 SXM 80GB** group so the GPU matches what the card names. "An H100"
  is three different products; see that README.

## Files

- `spec.json` — the question, fixed before multiplying
- `sources.json` — the model card figures and the corrections to secondary coverage
- `compute.py` → `result.json`
