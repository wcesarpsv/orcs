# Streamlit jackpot feed for ESP32-C6

Human dashboard: https://orcomputer.streamlit.app/JackpotsOLG
Device JSON: https://orcomputer.streamlit.app/app/static/jackpots_current.json

The Streamlit process fetches https://www.lotterypost.com/results/zz using the Lottery Post parser, then
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

The parser reads only the Lotto Max and Canada Lotto 6/49 next-draw panels,
using CA$ amounts in millions and each game's next drawing date. US$ conversions,
historical results, and changes from the previous jackpot are ignored.
Maxmillions is temporarily fixed at 0 by explicit request, even when historical
MaxMillions/MaxPlus links exist. The snapshot reports maxmillions_mode=fixed_zero.
Automatic upcoming Maxmillions extraction is not yet enabled; validate a real
upcoming-count example before changing this policy. Missing games, malformed
amounts/dates, and conflicting panels block the feed rather than fabricate values.

Tests: python -m unittest discover -s tests -p 'test_jackpots_publisher.py' -v
