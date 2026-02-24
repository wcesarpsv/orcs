import base64
import json
import hashlib

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Report Generator", layout="centered")
st.title("🛠️ WJS Service Report Generator")
st.caption("Fixed layout + AI polish (details only) + Auto-extract (Place/RDL + WJS Info)")
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
# HELPERS
# =====================
def _img_bytes_to_data_url(img_bytes: bytes) -> str:
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest() if b else ""

# =====================
# AI VISION: EXTRACT PLACE + RDL
# =====================
def extract_place_rdl_from_screenshot(img_bytes: bytes) -> dict:
    """
    Returns: {"place_name": "...", "rdl": "RDL: 12345"}
    """
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
- rdl must be digits only (no words).
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

        data = json.loads(resp.choices[0].message.content or "{}")
        place = (data.get("place_name") or "").strip()
        rdl_digits = (data.get("rdl") or "").strip()

        return {
            "place_name": place,
            "rdl": f"RDL: {rdl_digits}" if rdl_digits else "RDL: ",
        }

    except Exception:
        return {"place_name": "", "rdl": "RDL: "}

# =====================
# AI VISION: EXTRACT WJS LABEL INFO (Item / P/N / S/N)
# =====================
def extract_wjs_info_from_label(img_bytes: bytes) -> dict:
    """
    Returns:
    {
      "item": "Carmanah Wireless Jkpt Sign (30\")",
      "pn": "400-937",
      "sn": "EMONJC220032"
    }
    """
    if not client or not img_bytes:
        return {"item": "", "pn": "", "sn": ""}

    data_url = _img_bytes_to_data_url(img_bytes)

    system_prompt = """
You are extracting hardware label information from a photo of a sticker.

Return ONLY valid JSON:
{
  "item": "string",
  "pn": "string",
  "sn": "string"
}

Rules:
- item: product name/description (e.g., "Carmanah Wireless Jkpt Sign (30\")")
- pn: part number, usually formatted like "400-937"
- sn: serial number / ID (alphanumeric)
- If a field is not visible, return empty string for it.
- Do not invent.
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
                        {"type": "text", "text": "Extract item name, part number (P/N), and serial number (S/N)."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )

        data = json.loads(resp.choices[0].message.content or "{}")
        return {
            "item": (data.get("item") or "").strip(),
            "pn": (data.get("pn") or "").strip(),
            "sn": (data.get("sn") or "").strip(),
        }

    except Exception:
        return {"item": "", "pn": "", "sn": ""}

# =====================
# AI: POLISH ONLY DETAILS
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
                        "Rewrite technician notes into a concise, professional service report details section. "
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
        <textarea id="clipboard-text" style="position:absolute; left:-9999px; top:-9999px;">{safe_text}</textarea>
        <button onclick="copyText()"
            style="background-color:#2563eb;color:white;border:none;padding:10px 16px;border-radius:6px;font-size:14px;cursor:pointer;">
            📋 Copy to clipboard
        </button>
        <script>
        function copyText() {{
            const el = document.getElementById("clipboard-text");
            navigator.clipboard.writeText(el.value).then(() => {{
                alert("Report copied to clipboard!");
            }}).catch(() => {{
                alert("Could not copy automatically. Please copy manually.");
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

def format_wjs_info(item: str, pn: str, sn: str) -> str:
    item = (item or "").strip()
    pn = (pn or "").strip()
    sn = (sn or "").strip()
    if not (item or pn or sn):
        return ""
    lines = ["WJS Info:"]
    if item: lines.append(f"- Item: {item}")
    if pn:   lines.append(f"- P/N: {pn}")
    if sn:   lines.append(f"- S/N: {sn}")
    return "\n".join(lines)

def template_pm(local: str, reference: str, details: str, extras_block: str) -> str:
    base = f"""
PM completed at {local} ({reference}) - Summary

{details}

Burster bins, rollers, and all related peripherals were cleaned.
Serial numbers for all components were recorded for database entry.
All hardware components, including the pin pad, were tested and verified as operational.

Keys were returned to the retailer upon completion.
""".strip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

def template_installation(local: str, reference: str, details: str, extras_block: str, wjs_info_block: str) -> str:
    details = details.strip() if details else "No issues reported."
    base = f"""
WJS Large Carmanah - {local} ({reference}) - Installation Summary

Upon arrival at the site, the retailer indicated the preferred installation location and desired height for the sign.

{details}
""".strip()

    if wjs_info_block:
        base += "\n\n" + wjs_info_block

    base += """

After completion, I explained the work performed to the retailer and demonstrated that the equipment was operating correctly.
""".rstrip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

def template_deinstallation(local: str, reference: str, details: str, extras_block: str, wjs_info_block: str) -> str:
    details = details.strip() if details else "No issues reported."
    base = f"""
WJS Sign Deinstallation - {local} ({reference}) - Summary

Upon arrival at the site, the retailer indicated the sign to be removed.

{details}
""".strip()

    if wjs_info_block:
        base += "\n\n" + wjs_info_block

    base += """

The equipment is being returned to the warehouse.
""".rstrip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

# =====================
# SESSION STATE DEFAULTS
# =====================
if "place_name" not in st.session_state:
    st.session_state.place_name = ""
if "rdl" not in st.session_state:
    st.session_state.rdl = "RDL: "

if "wjs_item" not in st.session_state:
    st.session_state.wjs_item = ""
if "wjs_pn" not in st.session_state:
    st.session_state.wjs_pn = ""
if "wjs_sn" not in st.session_state:
    st.session_state.wjs_sn = ""

# to avoid re-extracting same image every rerun
if "last_screenshot_hash" not in st.session_state:
    st.session_state.last_screenshot_hash = ""
if "last_label_hash" not in st.session_state:
    st.session_state.last_label_hash = ""

# =====================
# AUTO-FILL INPUTS
# =====================
st.subheader("📸 Auto-fill (Place Name + RDL) via Screenshot")
screenshot = st.file_uploader("Upload screenshot (PNG/JPG)", type=["png", "jpg", "jpeg"], key="uploader_screenshot")

if screenshot is not None:
    img_bytes = screenshot.getvalue()
    h = _hash_bytes(img_bytes)

    st.image(Image.open(screenshot), caption="Screenshot preview", use_container_width=True)

    if not client:
        st.warning("OPENAI_API_KEY not set in secrets — auto-extract disabled.")
    else:
        # Auto extract only if new image
        if h and h != st.session_state.last_screenshot_hash:
            with st.spinner("Auto-extracting Place Name + RDL..."):
                extracted = extract_place_rdl_from_screenshot(img_bytes)
                if extracted.get("place_name"):
                    st.session_state.place_name = extracted["place_name"]
                if extracted.get("rdl"):
                    st.session_state.rdl = extracted["rdl"]
                st.session_state.last_screenshot_hash = h
            st.success("Place Name and RDL updated automatically!")

st.divider()

st.subheader("🏷️ Auto-fill (WJS Info) via Serial/Label Photo")
st.caption("Use this for INSTALLATION / DEINSTALLATION to add Item + P/N + Serial to the report.")
label_photo = st.file_uploader("Upload label/serial photo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="uploader_label")

if label_photo is not None:
    img_bytes = label_photo.getvalue()
    h = _hash_bytes(img_bytes)

    st.image(Image.open(label_photo), caption="Label preview", use_container_width=True)

    if not client:
        st.warning("OPENAI_API_KEY not set in secrets — auto-extract disabled.")
    else:
        # Auto extract only if new image
        if h and h != st.session_state.last_label_hash:
            with st.spinner("Auto-extracting WJS label info..."):
                wjs = extract_wjs_info_from_label(img_bytes)
                st.session_state.wjs_item = wjs.get("item", "")
                st.session_state.wjs_pn = wjs.get("pn", "")
                st.session_state.wjs_sn = wjs.get("sn", "")
                st.session_state.last_label_hash = h
            st.success("WJS Info updated automatically!")

st.divider()

# =====================
# UI FORM
# =====================
with st.form("report_form"):
    report_type = st.selectbox("📄 Report Type", ["PM", "INSTALLATION", "DEINSTALLATION"])

    use_ai = st.checkbox(
        "🤖 Use AI to polish ONLY the 'Details' section (keeps layout fixed)",
        value=True
    )

    if use_ai and not client:
        st.warning("AI is ON, but OPENAI_API_KEY is not set in secrets. Using your text as-is.")

    local = st.text_input("📍 Place Name", key="place_name")
    reference = st.text_input("🔢 Reference Number (RDL)", key="rdl")

    # show extracted label fields (editable)
    if report_type in ["INSTALLATION", "DEINSTALLATION"]:
        st.markdown("### 🏷️ WJS Info (auto-filled from label photo — you can edit)")
        st.text_input("Item", key="wjs_item")
        st.text_input("P/N", key="wjs_pn")
        st.text_input("S/N (Serial)", key="wjs_sn")

    descricao = st.text_area(
        "📝 Details (facts only — what happened / issues / time / actions taken)",
        placeholder="Example:\nTransceiver needed reconnection several times; cable issue added ~35 minutes. Equipment tested OK."
    )

    st.markdown("### 🔧 Additional Materials Used")

    col1, col2 = st.columns(2)
    with col1:
        cat5 = st.checkbox("CAT5 Network Cable")
        extension = st.checkbox("Power Extension")
        power_supply = st.checkbox("Power Supply")
        transceiver = st.checkbox("Transceiver")

    with col2:
        router = st.checkbox("Router")
        mounting = st.checkbox("Mounting Hardware")
        adapters = st.checkbox("Adapters")

    extras_custom = st.text_area(
        "➕ Other materials (one per line)",
        placeholder="Cable ties\nVelcro straps\nEthernet coupler"
    )

    submitted = st.form_submit_button("✅ Generate Report")

# =====================
# BUILD REPORT
# =====================
if submitted:
    itens_extras = []
    if cat5: itens_extras.append("CAT5 network cable")
    if extension: itens_extras.append("Power extension")
    if power_supply: itens_extras.append("Power supply")
    if transceiver: itens_extras.append("Transceiver")
    if router: itens_extras.append("Router")
    if mounting: itens_extras.append("Mounting hardware")
    if adapters: itens_extras.append("Adapters")

    if (extras_custom or "").strip():
        itens_extras.extend([i.strip() for i in extras_custom.split("\n") if i.strip()])

    extras_block = format_extras(itens_extras)

    details_final = (descricao or "").strip()
    if use_ai and details_final:
        with st.spinner("Polishing details with AI..."):
            details_final = polish_details_ai(details_final)

    local_clean = (local or "").strip()
    reference_clean = (reference or "").strip()

    wjs_info_block = ""
    if report_type in ["INSTALLATION", "DEINSTALLATION"]:
        wjs_info_block = format_wjs_info(
            st.session_state.wjs_item,
            st.session_state.wjs_pn,
            st.session_state.wjs_sn,
        )

    if report_type == "PM":
        texto_final = template_pm(local_clean, reference_clean, details_final, extras_block)
    elif report_type == "INSTALLATION":
        texto_final = template_installation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)
    else:
        texto_final = template_deinstallation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)

    # =====================
    # OUTPUT
    # =====================
    st.divider()
    st.subheader("📄 Generated Report")
    st.code(texto_final, language="text")

    colA, colB = st.columns(2)
    with colA:
        copy_to_clipboard_button(texto_final)

    with colB:
        st.download_button(
            "⬇️ Download Report (.txt)",
            data=texto_final,
            file_name=f"{report_type.lower()}_report.txt",
            mime="text/plain",
        )
