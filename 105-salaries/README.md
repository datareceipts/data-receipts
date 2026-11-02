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
| Seniority in job title | 3.8% |
| Worksite city | 32.3% |
| Employer | 41.0% |

Your employer explains about 11x more of the spread than your job title does.

Holding the title constant — 1,451 filings whose title contains "senior
software engineer" — the range runs $115,000 (p10) to $214,000 (p90), and
$54,621 to $351,900 end to end. Among the 14 employers filing 15+ times for
that exact title, medians run from $116,709 to $200,000.

There is a mechanical reason. Every filing carries a prevailing wage: a legal
floor computed from the occupation code and the worksite location, taking no
account of the job title. Across 45,079 filings the median wage sat just
$1,923 above that floor, and 40.2% were at or below it.

## Reproduce

```
pip install openpyxl
curl -O https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2026_Q1.xlsx
python3 analyse.py LCA_Disclosure_Data_FY2026_Q1.xlsx salaries.json variance.json
```

`common.py` holds the filters, the wage annualisation and the seniority
classifier. It exists because the aggregation and the variance work originally
carried separate copies of that classifier, which drifted — the same filing
landed in different bands depending on which script read it, and the two
outputs disagreed. One classifier, one set of numbers.

Source file published 2025-12-18 by the Office of Foreign Labor Certification:
<https://www.dol.gov/agencies/eta/foreign-labor/performance>

## Privacy

The source file contains employer and attorney contact details. Those columns
are discarded on read and appear in no output here. Published figures are
aggregates only.
