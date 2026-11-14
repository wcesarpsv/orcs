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

## SST PM

The SST PM report type provides separate reference and physical serial fields, guided camera/barcode/photo/manual capture with explicit Save & Next, component tests, mismatch acknowledgements, optional Router absence, key collection observations and report photos. Key serials are optional on both sides and generate neither a label nor a functional test.

Exports: the existing Data / Tag Excel layout, a metadata/test sheet, real Code 128 labels on 4×1-inch pages (print at 100% actual size), and a photo PDF summary. The prepared Excel template was sanitized and exported with Artifact Tool; runtime filling updates OOXML values/formula caches without installing a spreadsheet editor on Vercel. IDs and serials remain text, preserving leading zeros. PDFs do not assert that cleaning was performed unless the technician writes it in notes. Failed tests mark a report NOT COMPLETED and prevent cloud completion.

### Supabase connection pending project selection

No Supabase project was selected or modified during implementation. Exports work without the database. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY on Vercel after choosing the dedicated ORCS project, applying database/sst_pm_setup.sql and creating/approving technician Auth accounts. Never use a service-role key in the browser. The app forwards each technician access token and uses RLS for reads. Writes are append-only through a membership-checked private function and an invoker wrapper, with optimistic revision checks and idempotent request IDs. Prior PM visits are retained. Every new lookup uses the last confirmed physical serials as its reference, leaving the new physical check blank. Photos are exported, not stored in the shared database.

Use Supabase advisors and run member/non-member/anonymous/revision-conflict SQL and API checks after configuring the chosen project. Add known technician user UUIDs to orcs_sst_members as administrator; the public app cannot approve its own users. Sign-in tokens live in sessionStorage until expiry/sign-out; passwords are not stored. All cloud actions show explicit errors when unconfigured; a generated export never claims database persistence.

Camera scanning requires HTTPS and a browser with BarcodeDetector; on unsupported browsers, use label-photo extraction, a handheld scanner or manual input. Physical camera decoding and Honeywell print alignment require device testing.
