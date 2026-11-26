# Post-Trade Compliance — RM-204 Investment Controlling

Independent application for post-trade investment restriction checks and trade-by-trade reconciliation.

## Reporting streams

1. **Trade Reconciliation**: original trader instructions plus corresponding bank execution evidence, matched per individual order and account. A single timestamped hybrid PDF is generated per account/submission, and an internal Excel reconciliation remains available.
2. **Investment Restrictions**: evaluate actual post-trade portfolio exposures against the applicable mandate ranges and archive a separate timestamped PDF.

## Data sources

- **Original orders**: the *same Excel workbook* the trader submitted to the existing pre-trade application. The current pre-trade GitHub Pages code reads this file in the browser, but only archives a generated PDF to SharePoint; it does **not** currently archive the workbook. The new app must not silently assume this input is available.
- **Bank executions**: the production V13 `COMBINED_Trades_History.xlsx` built from HSBC, UBS and JPM reports, corrected for UBS cancellations.
- **Post-trade positions**: actual combined allocation/positions dataset, not pre-trade simulated orders.

## Constraints

- The original `kkspeedlab/allocation_range_checks` repository is read-only and must remain operational and unchanged.
- No account/order/transaction data should be committed to GitHub.
- Never infer settlement confirmation from a trade execution alone; reflect bank-reported fields only.
- Match executions by bank/account/ISIN/side and dates with explicit ambiguity detection; retain bank transaction references. Do not use portfolio-level aggregate fills.
- Track fully executed, partially executed and not executed; carry outstanding quantities forward until filled or manually closed with an audit record.
- Preserve original bank fee signs and presentation conventions.
- Timestamp PDFs as `YYYYMMDD_HHMMSS`; archive separately under `Trade Reconciliation` and `Investment Restrictions`.

## Integration milestone

The pre-trade application currently takes Excel orders through its browser file input and saves only a PDF via Microsoft Graph. **An independent read-only app cannot recover the original workbook from that PDF.** Resolve this by agreeing on a shared archival source for the *actual Excel workbook*, such as an existing trader-created SharePoint location, or an explicit export/archiving handoff. No second trader upload is assumed without verification.

## Planned modules

- `index.html`: interface/dashboard
- `src/engine.js`: pure order/execution matching and outstanding order calculations
- `src/app.js`: browser orchestration, file sources and reporting
- `src/style.css`: visual styles
- `tests/engine.test.mjs`: deterministic engine tests
- `docs/integration.md`: confirmed OneDrive/SharePoint integration and archive rules

## Status

**Bootstrap**. Source analysis complete; real source acquisition and persistence not yet connected. No production automation enabled.
