# Streamlit jackpot feed for ESP32-C6

Human dashboard: https://orcomputer.streamlit.app/JackpotsOLG
Device JSON: https://orcomputer.streamlit.app/~/+/app/static/jackpots_current.json

The Streamlit process fetches the OLG source using the existing parser, then
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

The parser retains the existing zero-Maxmillions rule when a next-jackpot section
is recognized but no explicit Maxmillions line exists. Review parser assumptions
if OLG changes its layout or prize categories.

Tests: python -m unittest discover -s tests -p 'test_jackpots_publisher.py' -v

The /~/+/ prefix is the deployed Community Cloud iframe route observed on this app.
The unprefixed URL may load the Cloud wrapper instead of raw JSON. Recheck this
route after hosting changes; it is deployment-specific.
