# Data Receipts

Every number from the [Data Receipts](https://youtube.com/@datareceipts) channel,
with the script that produced it.

Don't trust the video. Run the script.

## Why this repo exists

The channel has no host and no narrator you can vouch for. So the claim isn't
"trust me" — it's "here is the method, here is the raw output, re-run it yourself
and see if you get the same number."

Every video links the exact script and dataset behind it.

## Structure

```
<video-slug>/
  collect.py      pulls the raw data from the authoritative source
  data.json       what it returned, with source URLs and retrieval date
  README.md       the method, the caveats, and what the numbers do NOT show
```

## Methodology rules

1. Every number comes from a vendor's own API or published source. Nothing estimated.
2. Every figure is stamped with its source URL and the date it was retrieved.
3. Prices change. A number here is true as of its retrieval date and no later.
4. Where a comparison required a judgement call, the judgement is written down.
5. If a number here is wrong, open an issue. Corrections get published on the channel.

## Corrections

Found a mistake? Open an issue with your numbers and how you got them. Confirmed
errors are corrected on screen in the next video, not quietly edited.
