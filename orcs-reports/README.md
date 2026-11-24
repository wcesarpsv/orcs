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

### My Inventory

`/inventory` adds an account-owned Supabase inventory alongside Reports and Jackpots OLG. It shares the SST PM technician session and approval list. Registration normalizes barcode guards, whitespace, apostrophes and hyphens, uppercases text, and preserves leading zeros. The ten product patterns and Active CN rule were ported from RouteDeskFlow commit `bd602dfa375ac5fe9c36ef3e75390310c9e7e436`, `app/page.tsx` (`productRules`, `addInventoryItem`, `acceptScannedSerial`). Matching multiple rules always requires model confirmation; Carmanah models and Burster variants cannot be distinguished from their serial alone. Numeric mainboard serials can also overlap another product rule.

Apply `database/inventory_setup.sql` only to the dedicated ORCS Reports Supabase project, after `sst_pm_setup.sql`. RLS restricts each technician to their own inventory and history. The database RPC assigns identity from `auth.uid()`, validates formats, serial uniqueness, status transitions and revisions, and writes an immutable event in the same transaction. Request UUIDs make retries idempotent. Direct client writes are revoked. No service-role key is required.

Available → Installed → Return pending → Returned → Available, with Available → Returned also supported for unused stock. Installation/removal needs a call reference and RDL. Return and restock require explicit physical handover confirmation. A removed component acquired outside this inventory can be registered as Return pending. Current ownership never changes through these actions. Cross-technician transfers and automatic report/SST component-list updates are future integration work.

The RouteDeskFlow inventory was browser-local (`orcs-wagner-inventory`), including demo seed data. This migration ports the functionality and rules; it does not silently copy old browser records or demo parts into production. Add verified real components under the logged-in technician. JSON export includes the technician's full inventory, without credentials. Camera scanning uses BarcodeDetector where supported; manual entry and keyboard-wedge scanners work without it. Physical phone camera behavior requires device verification.

### User management

`/manage-users` is available through the header to active Admin and Owner accounts. Admins invite new Technician/Admin accounts. Only the Owner can block/unblock users or change an existing account's role; the singleton Owner is protected from all such changes. Active membership and roles are read from database rows, never editable Auth metadata. Blocking restricts inventory, shared SST records, kits, templates and authenticated account operations, including requests using an unexpired token. Public report exports remain public as before.

Apply `database/user_management.sql` once to the dedicated ORCS Reports project. It resolves the existing approved owner by the explicitly configured email, extends membership and creates an immutable management audit. The live database permission test is `tests/user_management_rls.sql` (transactional fixtures are rolled back).

Deploy `functions/orcs-user-admin/index.ts` with its `deno.json` as the `orcs-user-admin` Supabase function. It verifies the caller with Auth `/user` and database membership on every request. Gateway JWT verification is disabled because authentication is performed in the function; missing/invalid tokens and non-admins are rejected before invoking any privileged operation. Built-in runtime service credentials are never returned to a client or configured in Vercel. The service-only provisioning RPC rechecks the inviter's current role before approving a new user. It refuses to modify existing memberships, preventing invite retries from unblocking users. Auth email rate limits and SMTP configuration govern email delivery. If invitation succeeds but approval fails, the UI explicitly reports the partial outcome for owner review rather than claiming successful access.

### Inventory Reports

`/inventory-reports` gives active Admin/Owner accounts a read-only consolidated view and CSV exports. Current possession is Available + Return pending; Installed and Returned have separate counts. Technician summaries include accounts with no stock and retain blocked technicians' records. Filters and pagination run in the database, with 200 detail rows per page; CSV downloads traverse every matching page and escape spreadsheet formula prefixes.

`database/inventory_reporting.sql` installs a private definer function with a public invoker wrapper, an active-admin check and no direct cross-technician table grants. The installation history reads immutable inventory `install` events and explicitly identifies `component_used` events from SST kits. It uses event snapshots for product/serial/call/RDL, event actor and event time, and shows current stock status separately. Report generation without inventory confirmation is not counted as an installation. The transactional permission/history check is `tests/inventory_reporting_rls.sql`.
