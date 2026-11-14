# ORCS Reports

Flask migration of `../streamlit_app.py`, for Vercel. Existing Streamlit files remain unchanged.

Connect GitHub `wcesarpsv/orcs` to Vercel with project name `orcs-reports`, Root Directory `orcs-reports`, and Flask framework auto-detection. Python 3.12 is specified in `.python-version`.

Set `OPENAI_API_KEY` privately in Vercel Environment Variables to enable photo extraction and note polishing. Without it, manual reports, formatted copy, TXT and PDF remain available. Never put credentials in Git or browser code.

Run locally: install requirements.txt, then `flask --app app run` from this directory. Tests: `python -m unittest discover -s tests`.

Photos are optimized in the browser and processed in memory. Reports remain in the current browser tab; no database or cross-device history. The jackpot background publisher remains in the separate Streamlit application.

Report types, SST key statuses and service wording match the existing source. Review extracted values and service statements before use.

## Jackpots OLG

Reports and Jackpots OLG are separate navigation tabs. `/jackpots` opens the monitor directly. Changing tabs preserves the current form and generated report in the browser.

The device feed is `https://orcs-reports.vercel.app/api/jackpots/current.json` (aliases: `/api/jackpots` and `/static/jackpots_current.json`). Each GET fetches the current Loto-Quebec HTML, parses identified Lotto Max and Lotto 6/49 cards and validates all three values and both next-draw dates against Toronto time. It uses the existing schema_version 1 contract, a 300-second validity, and fail-closed null values with transmit_allowed=false on errors. No background thread, disk snapshot or browser visit is needed for device requests. The dashboard polls every 120 seconds while visible and clears expired values.

The upstream remains Loto-Quebec as in the current Streamlit page; equivalence to OLG remains under validation. Physical C6/Carmanah transmission and firmware endpoint changes are separate from this web deployment. Update the firmware URL explicitly when migrating a device; keep its schema/freshness/transmit_allowed checks. The old Streamlit feed is not redirected or modified.

Read-only HTML diagnostics are available in the monitor. No cron or persistent cache is required. No credentials or lottery purchasing features are used.
