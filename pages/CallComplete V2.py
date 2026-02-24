import base64
import json
import re
from io import BytesIO

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Report Generator", layout="centered")
st.title("🛠️ WJS Service Report Generator")
st.caption("Fixed layout + AI polish (details only) + Screenshot Auto-Fill")
st.divider()

# =====================
# SAFE OPENAI CLIENT
# =====================
def get_openai_client():
    try:
        key = st.secrets.get("OPENAI_API_KEY", None)
        if not key:
            return None
        return OpenAI(api_key=key)
    except Exception:
        return None

client = get_openai_client()

# =====================
# IMAGE -> BASE64
# =====================
def _img_bytes_to_data_url(img_bytes: bytes) -> str:
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"

# =====================
# EXTRACT PLACE + RDL
# =====================
def extract_place_rdl_from_screenshot(img_bytes: bytes) -> dict:
    if not client or not img_bytes:
        return {"place_name": "", "rdl": "RDL: "}

    data_url = _img_bytes_to_data_url(img_bytes)

    system_prompt = """
You are extracting structured data from a field-service mobile app screenshot.

The layout contains:
- Store name in large bold text near the top.
- A section labeled "RDL" with a number to the right.

Return ONLY valid JSON:
{
  "place_name": "...",
  "rdl": "####"
}

Rules:
- Extract exactly what is visible.
- RDL should be digits only.
- If not visible, return empty string.
- Do not invent anything.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract store name and RDL."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )

        data = json.loads(resp.choices[0].message.content)

        place = data.get("place_name", "").strip()
        rdl_digits = data.get("rdl", "").strip()

        if rdl_digits:
            rdl_formatted = f"RDL: {rdl_digits}"
        else:
            rdl_formatted = "RDL: "

        return {
            "place_name": place,
            "rdl": rdl_formatted,
        }

    except Exception:
        return {"place_name": "", "rdl": "RDL: "}

# =====================
# POLISH DETAILS ONLY
# =====================
def polish_details_ai(raw_details: str) -> str:
    if not client:
        return (raw_details or "").strip()

    raw_details = (raw_details or "").strip()
    if not raw_details:
        return ""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite technician notes into a concise professional report section. "
                        "Do not add assumptions. Do not invent facts. Keep all original meaning."
                    ),
                },
                {"role": "user", "content": raw_details},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return raw_details

# =====================
# COPY BUTTON
# =====================
def copy_to_clipboard_button(text: str):
    safe_text = (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    components.html(
        f"""
        <textarea id="clipboard-text" style="position:absolute; left:-9999px;">{safe_text}</textarea>
        <button onclick="copyText()" 
            style="background:#2563eb;color:white;border:none;padding:10px 16px;border-radius:6px;cursor:pointer;">
            📋 Copy to clipboard
        </button>
        <script>
        function copyText() {{
            const el = document.getElementById("clipboard-text");
            navigator.clipboard.writeText(el.value).then(() => {{
                alert("Copied!");
            }});
        }}
        </script>
        """,
        height=60,
    )

# =====================
# TEMPLATES
# =====================
def format_extras(itens_extras: list[str]) -> str:
    if not itens_extras:
        return ""
    lines = "\n".join([f"- {i}" for i in itens_extras])
    return f"Additional materials used:\n{lines}"

def template_pm(local, reference, details, extras):
    base = f"""
PM completed at {local} ({reference}) - Summary

{details}

Burster bins, rollers, and all related peripherals were cleaned.
Serial numbers recorded.
All components tested operational.

Keys returned to retailer.
""".strip()

    if extras:
        base += "\n\n" + extras
    return base

def template_installation(local, reference, details, extras):
    base = f"""
WJS Large Carmanah - {local} ({reference}) - Installation Summary

Upon arrival, retailer indicated installation location.

{details}

Retailer was shown equipment functioning properly.
""".strip()

    if extras:
        base += "\n\n" + extras
    return base

def template_deinstallation(local, reference, details, extras):
    base = f"""
WJS Sign Deinstallation - {local} ({reference}) - Summary

Upon arrival, retailer indicated sign to remove.

{details}

Equipment returned to warehouse.
""".strip()

    if extras:
        base += "\n\n" + extras
    return base

# =====================
# SESSION STATE
# =====================
if "place_name" not in st.session_state:
    st.session_state.place_name = ""
if "rdl" not in st.session_state:
    st.session_state.rdl = "RDL: "

# =====================
# SCREENSHOT SECTION
# =====================
st.subheader("📸 Auto-fill via Screenshot")

screenshot = st.file_uploader("Upload screenshot", type=["png", "jpg", "jpeg"])

if screenshot:
    img = Image.open(screenshot)
    st.image(img, use_container_width=True)

    if st.button("🔍 Extract Place + RDL"):
        if not client:
            st.error("OPENAI_API_KEY not set.")
        else:
            with st.spinner("Extracting..."):
                result = extract_place_rdl_from_screenshot(screenshot.getvalue())
                st.session_state.place_name = result["place_name"]
                st.session_state.rdl = result["rdl"]
            st.success("Fields updated!")

st.divider()

# =====================
# FORM
# =====================
with st.form("report_form"):

    report_type = st.selectbox("Report Type", ["PM", "INSTALLATION", "DEINSTALLATION"])

    use_ai = st.checkbox("Use AI to polish Details", value=True)

    local = st.text_input("Place Name", key="place_name")
    reference = st.text_input("Reference (RDL)", key="rdl")

    descricao = st.text_area("Details")

    st.markdown("### Additional Materials")

    cat5 = st.checkbox("CAT5 Cable")
    extension = st.checkbox("Power Extension")
    power_supply = st.checkbox("Power Supply")

    extras_custom = st.text_area("Other materials (one per line)")

    submitted = st.form_submit_button("Generate Report")

# =====================
# BUILD REPORT
# =====================
if submitted:

    extras_list = []
    if cat5: extras_list.append("CAT5 cable")
    if extension: extras_list.append("Power extension")
    if power_supply: extras_list.append("Power supply")

    if extras_custom.strip():
        extras_list.extend([x.strip() for x in extras_custom.split("\n") if x.strip()])

    extras_block = format_extras(extras_list)

    details_final = descricao.strip()
    if use_ai and details_final:
        with st.spinner("Polishing details..."):
            details_final = polish_details_ai(details_final)

    if report_type == "PM":
        final_text = template_pm(local, reference, details_final, extras_block)
    elif report_type == "INSTALLATION":
        final_text = template_installation(local, reference, details_final, extras_block)
    else:
        final_text = template_deinstallation(local, reference, details_final, extras_block)

    st.divider()
    st.subheader("Generated Report")
    st.code(final_text)

    col1, col2 = st.columns(2)
    with col1:
        copy_to_clipboard_button(final_text)
    with col2:
        st.download_button("Download .txt", final_text, "report.txt")
