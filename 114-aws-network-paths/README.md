# 114 — AWS networking: the same terabyte, $0 or $162

One terabyte of traffic a month, in us-east-1, on 2026-11-16. The volume never
changes. Only the destination does.

## The result

| destination | total | transfer | fixed |
|---|---|---|---|
| Another instance, same AZ | **$0.00** | 0 | 0 |
| Another instance, another AZ | $20.48 | 20.48 | 0 |
| Another region (US West Oregon) | $20.48 | 20.48 | 0 |
| The internet, public subnet | $83.16 | 83.16 | 0 |
| The internet, via NAT Gateway | **$162.09** | 129.24 | 32.85 |

## Three findings

**1. The NAT Gateway nearly doubles internet egress.** Sending a terabyte out
from a public subnet is $83.16. Sending the identical terabyte from a private
subnet through a NAT Gateway is $162.09 — a **$78.93 surcharge, 95% on top**.
$46.08 of that is per-GB processing at $0.045, and $32.85 is the gateway
simply existing at $0.045 an hour.

This matters because a private subnet behind NAT is the architecture AWS's own
guidance steers you toward. The expensive path is the default one.

And it multiplies: a NAT Gateway is per-AZ, so a conventional three-zone
deployment pays **$98.55 a month in fixed charges before a single byte moves.**

**2. Crossing an availability zone costs the same as crossing the continent.**
Cross-AZ traffic is $0.01/GB and is billed in *both* directions, so a terabyte
between two of your own instances a few miles apart is $20.48. A terabyte from
Virginia to Oregon, 2,500 miles, is $0.02/GB one way — also $20.48. Distance is
not what you are paying for.

**3. Cross-AZ is the easiest line to undercount by half.** It is charged on the
sender and on the receiver, and both land on the same bill. Every estimate that
multiplies volume by $0.01 once is half the real number.

## An ambiguity in AWS's own price list

The AWSDataTransfer price list contains three intra-region SKUs for us-east-1
whose descriptions are word-for-word identical — *"regional data transfer -
in/out/between EC2 AZs or using elastic IPs or ELB"* — at two different prices:

| transferType | usagetype | price |
|---|---|---|
| `IntraRegion` | `DataTransfer-Regional-Bytes` | **$0.01/GB** |
| `IntraRegion-xAZ-Out` | `USE1-DataTransfer-xAZ-Out-Bytes` | **$0.00/GB** |
| `IntraRegion-xAZ-In` | `USE1-DataTransfer-xAZ-In-Bytes` | **$0.00/GB** |

Nothing in the product attributes distinguishes them. This analysis uses the
$0.01 figure, because independent pricing references still quote $0.01/GB in
each direction and AWS's own on-demand pricing page does not render a rate
table that could settle it. If the $0.00 SKUs are the operative ones for
ordinary EC2 cross-AZ traffic, then row 2 of the table above is $0.00 and
finding 2 does not hold. All three are carried in `costs.json` so the
ambiguity is visible rather than hidden behind a single number.

This is recorded as an open question, not a finding. If you know which governs,
the repo issue tracker is the place.

## Caveats

- Where the three offer codes live is itself a trap: internet and inter-region
  transfer are in `AWSDataTransfer`, NAT Gateway is in `AmazonEC2` under
  `productFamily: NAT Gateway`, and NAT is *not* in `AmazonVPC` where you would
  look first.
- The 100 GB/month free internet egress allowance is applied once, to the
  internet paths. At 1 TB it is worth $9.
- One NAT Gateway is modelled in the headline. Three-zone fixed cost is
  reported separately rather than folded in.
- No Transit Gateway ($0.05/hr per attachment plus $0.02/GB), no PrivateLink
  interface endpoints ($0.01/hr plus $0.01/GB), no VPC peering ($0.01/GB each
  way). Each adds another per-GB charge on top of what is here.
- us-east-1 to us-west-2 specifically; inter-region rates vary by pair.
- List prices, on-demand, no committed-use discount.

## Method

`spec.json` was committed before any rate was looked up (`9165ce9`). Volume is
fixed at 1 TB so that destination is the only variable.

## Files

- `spec.json` — the traffic, fixed first
- `collect.py` → `costs.json` — rates from AWSDataTransfer and AmazonEC2
- `compute.py` → `result.json` — the five paths, the NAT surcharge, the ambiguity
