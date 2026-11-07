# 108 — Cost-of-living-adjusted software salaries

Deflates the city salary medians from [`../105-salaries`](../105-salaries) by each
metro's BEA regional price parity, to test the claim that high-paying metros only
look high-paying before cost of living.

## Result

The claim does not survive, but it is not baseless either.

| | |
|---|---|
| Top-to-bottom premium, nominal | **105.5%** |
| Top-to-bottom premium, cost-adjusted (same two cities) | **75.3%** |
| Share of the gap explained by cost of living | **28.6%** |
| Rank correlation, nominal vs adjusted | **0.978** |
| Cities better off after adjusting | **4 of 25** |

The ranking barely reorders. Menlo Park is first either way.

## Why

Rent genuinely does vary across these metros about as much as salaries do
(2.17× vs 2.06×). But rent is only ~17% of the consumption basket, so the
all-items price level varies just 1.19×. A 2× spread in one-sixth of your
spending cannot offset a 2× spread in income.

The 17% is not taken from a secondary source — it is recovered by fitting BEA's
published all-items index against its four components across all 387 metro
areas, in logs (BEA aggregates multiplicatively; a linear fit is off by 12 index
points on San Jose, which is exactly the metro that matters here). Median
residual 0.30 index points.

**That fit is an explanation, not an input.** Every adjusted figure uses BEA's
own published all-items parity, so the fit's error does not propagate into any
reported number.

## Files

| File | What it is |
|---|---|
| `collect.py` | Pulls MARPP price parities from the BEA Data API. Needs `BEA_API_KEY` in the environment; the key is not in this repo. |
| `rpp.json` | What the API returned — 387 metros × 5 components, 2024. |
| `crosswalk.json` | **Hand-built** city → MSA table, with the county used for each assignment. Read it line by line; this is the step most likely to be wrong. |
| `compute.py` | Does the join, the deflation, the ranking comparison and the weight fit. |
| `adjusted.json` | Output. |

```sh
BEA_API_KEY=... python3 collect.py
python3 compute.py
```

`collect.py` retries on `This UserId is not active` — BEA returns that
intermittently for a newly activated key while activation propagates.

## Limitations

- Wages are **attested base wages** on DOL visa filings. No equity. Equity is a
  large share of Bay Area compensation, and excluding it cuts *against* the
  conclusion here.
- Price parities are 2024; the wage filings are not the same vintage.
- An RPP is built for the average household, not for someone on a software
  salary, whose rent share differs.
- Parities are metro-wide, so within-metro variation is flattened by
  construction. Menlo Park and San Francisco share a price level in this data
  while their medians differ by $27,572.
