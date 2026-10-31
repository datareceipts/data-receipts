# AWS reserved instances: discount vs break-even

Every reserved term for one `m6i.xlarge` (4 vCPU / 16 GB, us-east-1, Linux),
pulled from the AWS Price List API.

AWS advertises up to **60.5% off**. That term doesn't break even until **month 14**.

## Standard RIs

| Term | Upfront | $/hr | Saves | Break-even |
|---|---|---|---|---|
| 1yr All Upfront | $1,038 | $0.0000 | 38.3% | 7.4 mo |
| 1yr Partial | $530 | $0.0605 | 37.0% | 5.5 mo |
| 1yr No Upfront | $0 | $0.1270 | 33.8% | **immediate** |
| 3yr All Upfront | $1,992 | $0.0000 | **60.5%** | 14.2 mo |
| 3yr Partial | $1,060 | $0.0403 | 58.0% | 9.6 mo |
| 3yr No Upfront | $0 | $0.0871 | 54.6% | **immediate** |

## Convertible RIs (can change instance family mid-term)

| Term | Upfront | Saves | Break-even |
|---|---|---|---|
| 3yr All Upfront | $2,322 | 54.0% | 16.6 mo |
| 3yr Partial | $1,185 | 53.0% | 11.0 mo |
| 3yr No Upfront | $0 | 49.3% | immediate |

Flexibility costs **$330 more upfront, 6.5 points of discount, and 2.4 extra
months** before break-even.

## The rule

- Certain of the instance type past 14 months → **All Upfront** wins on total cost
- Anything less → **No Upfront** gives 54.6% with zero exposure

`break-even = upfront ÷ (monthly on-demand − monthly reserved)`

## Caveats

- Standard and convertible only. Savings Plans are a separate product, not compared.
- Excludes the opportunity cost of a cheaper instance generation launching mid-term —
  which would make long commitments look worse, not better.
- $1,992 upfront buys 14.2 months of plain on-demand for the same instance.

Raw figures and sources: [`data.json`](data.json)
