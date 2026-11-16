# 116 — Training an AI model: $4.6M to $106M in one year

Three Meta model cards, each priced on the GPU its own card names. Rates
measured 2026-11-16.

## The result

| generation | released | GPU | GPU-hours | RunPod floor | AWS |
|---|---|---|---|---|---|
| Llama 2 | Jul 2023 | A100 SXM 80GB | 3,311,616 | **$4.6M** | $11.4M |
| Llama 3 | Apr 2024 | H100 SXM 80GB | 7,700,000 | $20.7M | $53.0M |
| Llama 3.1 | Jul 2024 | H100 SXM 80GB | 39,300,000 | **$105.7M** | $270.4M |

**23.0x in twelve months at the market floor. 23.8x at AWS.**

The multiple barely moves between the cheapest vendor in the market and a
hyperscaler, which is the point of pricing it twice — the curve is a fact
about the models, not about where you shop.

## Where the 23x comes from

Compute grew **11.9x** — 3.3M GPU-hours to 39.3M. That is a little over half
the story in log terms. The rest is that the hardware got more expensive per
hour at the same time: Llama 2 trained on A100s at $1.39, Llama 3.1 on H100s
at $2.69 on the same vendor.

So the bill grew faster than the compute did. Any estimate that scales last
year's cost by this year's GPU-hour count and stops there is low.

Flagship to flagship the jump is steeper still: Llama 2 70B took 1,720,320
GPU-hours, Llama 3.1 405B took 30,840,000 — **17.9x** for the headline model.

Emissions track it, on each card's own figures: **539 → 2,290 → 11,390 tons
CO2eq**, a 21x rise. All three cards state the emissions were offset.

## Two ways this could have been faked, and what was done instead

**Pricing everything on today's H100.** Tidier, and wrong. Llama 2 trained on
A100s, which are cheaper per hour, so flattening the hardware onto one GPU
would have *understated* the real increase. Each generation is priced on the
GPU its card names.

**Switching vendor between generations.** Azure sells an H100 SXM 80GB but its
A100 SXM is a 40GB part — a different product. Quoting Azure for 2024 and
someone else for 2023 would manufacture slope out of nothing. Only vendors that
publish a rate for *both* groups are used, which is why the table has RunPod
and AWS and no one else.

## Caveats

- **Not Meta's costs.** Meta owns its clusters; it paid capex, power and staff,
  not an hourly rate. This prices renting the same compute.
- **On-demand list prices.** A reservation at this scale is negotiated and
  cheaper than every figure here. The shape is the finding, not the absolute.
- **Compute only.** No data acquisition, no salaries, no failed runs, no
  research time. The real cost of a frontier model is larger than its largest
  line item.
- **One company, deliberately.** Labs report training compute differently and
  many do not report it at all. Comparing Meta to Meta is the only version of
  this that is apples to apples.
- Llama 2's card gives A100-80GB at 400W; Llama 3 and 3.1 give H100-80GB at
  700W. The power figures are not used here, only the hours.

## Sources

- Llama 2: https://huggingface.co/meta-llama/Llama-2-70b-hf
- Llama 3: https://huggingface.co/meta-llama/Meta-Llama-3-70B
- Llama 3.1: https://huggingface.co/meta-llama/Llama-3.1-405B
- Rates: [109-gpu-pricing](../109-gpu-pricing), refreshed 2026-11-16

## Files

- `spec.json` — the three generations and the rule for pricing them, fixed first
- `compute.py` → `result.json`
