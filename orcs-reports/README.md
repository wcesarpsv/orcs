# ORCS Reports

Flask migration of `../streamlit_app.py`, for Vercel. Existing Streamlit files remain unchanged.

Connect GitHub `wcesarpsv/orcs` to Vercel with project name `orcs-reports`, Root Directory `orcs-reports`, and Flask framework auto-detection. Python 3.12 is specified in `.python-version`.

Set `OPENAI_API_KEY` privately in Vercel Environment Variables to enable photo extraction and note polishing. Without it, manual reports, formatted copy, TXT and PDF remain available. Never put credentials in Git or browser code.

Run locally: install requirements.txt, then `flask --app app run` from this directory. Tests: `python -m unittest discover -s tests`.

Photos are optimized in the browser and processed in memory. Reports remain in the current browser tab; no database or cross-device history. The jackpot background publisher remains in the separate Streamlit application.

Report types, SST key statuses and service wording match the existing source. Review extracted values and service statements before use.
