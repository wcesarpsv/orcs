# Streamlit jackpot feed for ESP32-C6

Human dashboard: https://orcomputer.streamlit.app/JackpotsOLG
Device JSON: https://orcomputer.streamlit.app/app/static/jackpots_current.json

The Streamlit process fetches https://chinese.olg.ca/sc/index.php/lotto_max.php using the Chinese OLG parser, then
atomically publishes one small snapshot every 120 seconds. Valid snapshots expire
after 300 seconds. Failure publishes null values and transmit_allowed=false.
The committed JSON contains only an unavailable startup placeholder.

The publisher starts when streamlit_app.py or pages/JackpotsOLG.py executes.
It runs in one daemon thread per directory/process and uses no Streamlit APIs.
The main app is at the repository root, matching Streamlit's static directory.
Static serving is enabled by .streamlit/config.toml. JSON becomes publicly
accessible when the app is publicly accessible; it contains only public jackpots.

After deployment, open /JackpotsOLG once to start the process and inspect the JSON.
C6 firmware v7 reads this endpoint and checks schema_version, timestamp freshness,
transmit_allowed, and the three integer values before accepting the snapshot.
Firmware installation and physical sign transmission must be tested separately.

Streamlit Community Cloud may sleep/restart the app, and runtime-generated files
are not durable storage. A static-file GET does not execute the Python page.
After sleep/restart it may be necessary to open the dashboard again. Expiration
checks on the C6 prevent an old static response from authorizing stale values.
This feed is not a guarantee of unattended 24/7 service on Community Cloud.

The parser identifies Lotto Max and Gold Ball panels by their game images/classes,
reads machine-readable next-draw dates, and checks the visible dates agree.
It supports full dollar amounts and Chinese units, including 2.5千万元 = CAD25M.
The Gold Ball amount is selected beside its logo, excluding the classic CAD5M.
Repeated banner/card values must agree. Other games and historical results cannot
supply a missing value. Missing, zero, fractional, stale, or conflicting main
jackpots block transmission. Maxmillions remains explicitly fixed at 0.
The normal fetch uses HTML already returned by OLG; Chromium is not needed.
The Lottery Post browser diagnostic is no longer exposed on the dashboard.

Tests: python -m unittest discover -s tests -p 'test_jackpots_publisher.py' -v
