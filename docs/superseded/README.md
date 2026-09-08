# Superseded outputs

These files were generated from the **pre-correction** pipeline and state numbers
that this branch shows to be wrong. They are kept rather than deleted so the
record of what was published is preserved, and moved here so nobody cites them
by accident.

| File | Status |
|---|---|
| `findings_report.html` | Superseded. Hand-authored from the old results; no generator exists in the repo, so it cannot be rebuilt automatically. |
| `findings_report.pdf` | Superseded. Rendered from the HTML above by `utils/render_pdf.py`. |

## What they get wrong

Both report that **28 of 42** SMC/ICT concepts beat a random-entry baseline. That
count came from a **two-sided** significance test: 27 of those 28 concepts had a
*negative* effect size and in fact lost to random entry. They also include two
signals (`ict_fvg_bullish_filled`, `ict_fvg_bearish_filled`) computed from up to
60 bars of future data, and count `ict_ndog_formed`, which fired on every bar.

The corrected result is **5 of 44** concepts beating a composition-matched null,
of which **2** survive a sweep of their own parameters.

## Use instead

| Instead of | Read |
|---|---|
| `findings_report.html` / `.pdf` | [`docs/manuscript.md`](../manuscript.md) · [`docs/manuscript.pdf`](../manuscript.pdf) |
| the old headline numbers | [`results/master_summary.md`](../../results/master_summary.md) |
| a summary of what changed | [`CHANGES.md`](../../CHANGES.md) |
| why each number moved | [`results/validation_report.md`](../../results/validation_report.md) §6 |

If you want an HTML findings page again, generate it from
`results/statistics_master.csv` so it cannot drift from the artefacts, as
`utils/master_summary.py` and `utils/validation_report.py` do.
