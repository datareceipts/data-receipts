# 105 — What actually sets a software salary

Employer-attested base wages for US software roles, from Department of Labor
Labor Condition Application (LCA) disclosure filings.

## Why this source

Every row is an employer's **legal attestation** of the wage it will pay for a
named role at a named worksite. It is not a survey, nobody self-selected into
it, and filing a false wage carries penalties. That makes it the largest public
dataset of employer-committed software salaries.

## What it is not

- **Base wage only.** Equity and bonus are not part of an LCA attestation. A
  company whose offer is half equity looks underpaid here.
- **H-1B filings only.** Skewed toward larger employers, tech-dense metros, and
  roles companies choose to sponsor. Not a sample of all US software jobs.
- **A floor, not a midpoint.** `WAGE_RATE_OF_PAY_FROM` is the bottom of the
  attested range — the number the employer is legally bound to meet.

## Finding

Across an identical set of 11,431 filings, share of wage variance explained
(omega-squared, which penalises factors that have more categories):

| Factor | Variance explained |
| --- | --- |
| Seniority in job title | 2.4% |
| Worksite city | 32.3% |
| Employer | 41.0% |

Holding the title constant — 1,451 filings whose title contains
"senior software engineer" — the range runs $115,000 (p10) to $214,000 (p90).

## Reproduce

```
pip install openpyxl
curl -O https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2026_Q1.xlsx
python3 collect_salaries.py LCA_Disclosure_Data_FY2026_Q1.xlsx salaries.json
python3 variance.py        LCA_Disclosure_Data_FY2026_Q1.xlsx variance.json
```

Source file published 2025-12-18 by the Office of Foreign Labor Certification:
<https://www.dol.gov/agencies/eta/foreign-labor/performance>

## Privacy

The source file contains employer and attorney contact details. Those columns
are discarded on read and appear in no output here. Published figures are
aggregates only.
