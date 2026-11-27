# Integration investigation — 26 November 2026

Existing source read-only: `kkspeedlab/allocation_range_checks` (main), specifically `index.html` and `app.payload.txt`.

Verified:
- The application asks the trader to upload a Proposed Orders file through `<input id="orders" type="file">`.
- The browser converts that uploaded workbook into SheetJS rows during `runCheck()`.
- The application saves a **PDF only** to SharePoint using `archivePdfToSharePoint()`; it does not upload the original Excel workbook in that function.
- Existing PDF destination is an account/month folder accessed via a SharePoint sharing link.
- Pre-trade uses Microsoft MSAL and Microsoft Graph and reads the latest Combined Daily Allocation.

Not verified:
- Any separate trader-owned archive of the Excel file used for bank orders.
- An automatic backend or scheduled process able to access the Excel workbook.
- Whether the existing compliance folder already stores Excel orders via another workflow.
- A current browser app consent/redirect configuration for the independent app.

Required before enabling automated import:
1. Identify an existing authoritative shared original Excel order archive or agree on a non-invasive export process.
2. Confirm file naming/account/sheet/date and immutable versioning of orders.
3. Confirm V13 history location and exact bank column mappings.
4. Validate matches on real sample files and reject ambiguous attribution.
5. Confirm archival folders for separate RM-204 Trade Reconciliation and Investment Restrictions PDFs.

No changes are made to the pre-trade code or trader workflow.

## Confirmed subsequent decisions

- Trader archives the original workbooks directly in monthly RM-889 folders, not account subfolders. Both SharePoint source links were supplied privately; do not commit them.
- EQ_Upload (YYYYMMDD) is UBS; MultiStexTemplate (YYMMDD) is HSBC. Workbooks may contain multiple accounts; exclude TOTALS.
- One hybrid PDF per account across banks: original order instructions followed by individual execution evidence and reconciliation results. Compliance approved the sample content.
- Filename: ACCOUNT_Trade_Reconciliation_YYYY_MM_DD_HH.MM.SS.pdf.
- Python prototype now lives in backend/post_trade_reconcile.py. Local regression on the two 25 November order files and 26 November history produced 18 fully executed orders across three PDFs. Live Graph access, browser-to-backend connection, persistent order register and production validation remain pending.
- GitHub Pages is static and cannot execute Python. A separate Python runtime is required to use the approved PDF generator. Do not enable unattended production runs until matching, duplicates, future contracts and historical coverage are validated.
