import base64
import json
import hashlib
from io import BytesIO
from typing import List, Dict

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Report Generator", layout="centered")
st.title("🛠️ WJS Service Report Generator")
st.caption("Fixed layout + AI polish (details only) + Auto-extract (Place/RDL + WJS Info) + BF (WJS/SST)")
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

def _safe_open_image(img_bytes: bytes):
    try:
        return Image.open(BytesIO(img_bytes))
    except Exception:
        return None

# =====================
# AI VISION: EXTRACT PLACE + RDL
# =====================
def extract_place_rdl_from_screenshot(img_bytes: bytes) -> Dict[str, str]:
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

        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)

        place = (data.get("place_name") or "").strip()
        rdl_digits = (data.get("rdl") or "").strip()

        return {
            "place_name": place,
            "rdl": f"RDL: {rdl_digits}" if rdl_digits else "RDL: ",
        }

    except Exception as e:
        st.error(f"Error extracting Place/RDL: {e}")
        return {"place_name": "", "rdl": "RDL: "}

# =====================
# AI VISION: EXTRACT WJS LABEL INFO (Item / P/N / S/N)
# =====================
def extract_wjs_info_from_label(img_bytes: bytes) -> Dict[str, str]:
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
- item: product name/description
- pn: part number, usually like "400-937"
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

        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)

        return {
            "item": (data.get("item") or "").strip(),
            "pn": (data.get("pn") or "").strip(),
            "sn": (data.get("sn") or "").strip(),
        }

    except Exception as e:
        st.error(f"Error extracting WJS label: {e}")
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
            temperature=0,  # safer: less chance of "inventing"
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
def copy_to_clipboard_button(text: str, button_label: str = "📋 Copy to clipboard"):
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
            {button_label}
        </button>
        <script>
        function copyText() {{
            const el = document.getElementById("clipboard-text");
            navigator.clipboard.writeText(el.value).then(() => {{
                alert("Copied!");
            }}).catch(() => {{
                alert("Could not copy automatically. Please copy manually.");
            }});
        }}
        </script>
        """,
        height=60,
    )

# =====================
# TEMPLATES / FORMATTERS
# =====================
def format_extras(itens_extras: List[str]) -> str:
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

def template_wjs_bf(local: str, reference: str, details: str, extras_block: str) -> str:
    details = details.strip() if details else "No issues reported."
    base = f"""
WJS Carmanah Break/Fix - {local} ({reference}) - Summary

Upon arrival at the site, I spoke with the retailer and was directed to the location of the Carmanah unit.

{details}

I remained on-site for approximately 15 minutes to monitor the equipment and confirm that it was functioning normally.

Retailer was informed that the unit is now operating normally.
""".strip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

# ---------- SST BF (TEXTO 1: REQUEST REF) ----------
def format_sst_bf_request_email(reference: str, items: List[Dict[str, str]]) -> str:
    """
    items: [{"component":"Slip Reader", "old_sn":"...", "new_sn":"..."}, ...]
    """
    reference = (reference or "").strip()

    clean = []
    for it in items or []:
        comp = (it.get("component") or "").strip()
        old_sn = (it.get("old_sn") or "").strip()
        new_sn = (it.get("new_sn") or "").strip()
        if comp and (old_sn or new_sn):
            clean.append({"component": comp, "old_sn": old_sn, "new_sn": new_sn})

    if not clean:
        clean = [{"component": "Component", "old_sn": "", "new_sn": ""}]

    blocks = []
    for it in clean:
        blocks.append(
            f"{it['component'].upper()}:\n\n"
            f"OLD SN:\n{it['old_sn']}\n\n"
            f"NEW SN:\n{it['new_sn']}\n"
        )
    blocks_text = "\n\n".join(blocks).strip()

    email = f"""
Hello,

I'm requesting one ref number for component replacement at {reference}, as comprehensive testing has indicated the necessity of this replacement.

I'm sending in attached the components list that I did now before any changes.

Following the SN of old and new components:

{blocks_text}
""".strip()

    return email

# ---------- SST BF (TEXTO 2: REPLACEMENT REPORT) ----------
def format_replaced_components_block(items: List[Dict[str, str]]) -> str:
    lines = []
    for it in items or []:
        comp = (it.get("component") or "").strip()
        old_sn = (it.get("old_sn") or "").strip()
        new_sn = (it.get("new_sn") or "").strip()
        if not comp:
            continue

        if old_sn and new_sn:
            lines.append(f"- {comp} (OLD SN: {old_sn} → NEW SN: {new_sn})")
        elif old_sn and not new_sn:
            lines.append(f"- {comp} (OLD SN: {old_sn})")
        elif new_sn and not old_sn:
            lines.append(f"- {comp} (NEW SN: {new_sn})")
        else:
            lines.append(f"- {comp}")

    return "\n".join(lines).strip()

def template_sst_bf_replacement_report(items: List[Dict[str, str]]) -> str:
    clean = []
    for it in items or []:
        comp = (it.get("component") or "").strip()
        old_sn = (it.get("old_sn") or "").strip()
        new_sn = (it.get("new_sn") or "").strip()
        if comp and (old_sn or new_sn):
            clean.append({"component": comp, "old_sn": old_sn, "new_sn": new_sn})

    replaced_block = format_replaced_components_block(clean) or "- (No components listed)"

    if len(clean) == 1:
        comp_lower = clean[0]["component"].strip().lower()
        return f"""
Hello,

Following communication with the retailer, it was identified that the {comp_lower} was experiencing operational issues. Subsequent diagnostic testing confirmed the necessity of replacing the unit.

Replaced component:
{replaced_block}

The {comp_lower} has since been replaced, and post-replacement testing indicates that the SST system has returned to full operational capacity, with no further errors related to the {comp_lower}.

The updated and previous component lists are attached for your review.
""".strip()

    return f"""
Hello,

Following communication with the retailer, it was identified that multiple SST components were experiencing operational issues. Subsequent diagnostic testing confirmed the necessity of replacing the affected units.

Replaced component(s):
{replaced_block}

The components have since been replaced, and post-replacement testing indicates that the SST system has returned to full operational capacity, with no further related errors.

The updated and previous component lists are attached for your review.
""".strip()

# =====================
# SESSION STATE DEFAULTS
# =====================
for k, v in {
    "place_name": "",
    "rdl": "RDL: ",
    "wjs_item": "",
    "wjs_pn": "",
    "wjs_sn": "",
    "last_screenshot_hash": "",
    "last_label_hash": "",
    "report_type_preview": "PM",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "sst_replacements" not in st.session_state:
    st.session_state.sst_replacements = [{"component": "Slip Reader", "old_sn": "", "new_sn": ""}]

# =====================
# AUTO-FILL INPUTS
# =====================
st.subheader("📸 Auto-fill (Place Name + RDL) via Screenshot")
screenshot = st.file_uploader("Upload screenshot (PNG/JPG)", type=["png", "jpg", "jpeg"], key="uploader_screenshot")

if screenshot is not None:
    img_bytes = screenshot.getvalue()
    h = _hash_bytes(img_bytes)

    img = _safe_open_image(img_bytes)
    if img:
        st.image(img, caption="Screenshot preview", use_container_width=True)
    else:
        st.warning("Could not preview screenshot image.")

    if not client:
        st.warning("OPENAI_API_KEY not set in secrets — auto-extract disabled.")
    else:
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

    img = _safe_open_image(img_bytes)
    if img:
        st.image(img, caption="Label preview", use_container_width=True)
    else:
        st.warning("Could not preview label image.")

    if not client:
        st.warning("OPENAI_API_KEY not set in secrets — auto-extract disabled.")
    else:
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
# SST BF DYNAMIC CONTROLS (outside form, to avoid submit conflicts)
# =====================
if st.session_state.get("report_type_preview", "PM") == "SST BF":
    st.subheader("🔁 SST BF - Components to Replace")
    st.caption("Add/remove components. Fill component name + old/new SN for each replacement.")

    colx, coly = st.columns(2)
    with colx:
        if st.button("➕ Add component", key="btn_add_comp"):
            st.session_state.sst_replacements.append({"component": "", "old_sn": "", "new_sn": ""})
    with coly:
        if st.button("➖ Remove last", key="btn_remove_comp"):
            if len(st.session_state.sst_replacements) > 1:
                st.session_state.sst_replacements.pop()

    st.divider()

# =====================
# UI FORM
# =====================
with st.form("report_form"):
    report_type = st.selectbox(
        "📄 Report Type",
        ["PM", "INSTALLATION", "DEINSTALLATION", "WJS BF", "SST BF"],
    )
    st.session_state.report_type_preview = report_type

    use_ai = st.checkbox(
        "🤖 Use AI to polish ONLY the 'Details' section (keeps layout fixed)",
        value=True
    )

    if use_ai and not client:
        st.warning("AI is ON, but OPENAI_API_KEY is not set in secrets. Using your text as-is.")

    local = st.text_input("📍 Place Name", key="place_name")
    reference = st.text_input("🔢 Reference Number (RDL)", key="rdl")

    if report_type in ["INSTALLATION", "DEINSTALLATION"]:
        st.markdown("### 🏷️ WJS Info (auto-filled from label photo — you can edit)")
        st.text_input("Item", key="wjs_item")
        st.text_input("P/N", key="wjs_pn")
        st.text_input("S/N (Serial)", key="wjs_sn")

    # SST BF - replacement list inputs
    sst_items: List[Dict[str, str]] = []
    if report_type == "SST BF":
        st.markdown("### 🔁 SST BF - Replacement Items (Old SN / New SN)")
        for idx, row in enumerate(st.session_state.sst_replacements):
            st.markdown(f"**Component #{idx+1}**")
            comp = st.text_input(
                f"Component name #{idx+1}",
                value=row.get("component", ""),
                key=f"sst_comp_{idx}",
            )
            old_sn = st.text_input(
                f"OLD SN #{idx+1}",
                value=row.get("old_sn", ""),
                key=f"sst_old_{idx}",
            )
            new_sn = st.text_input(
                f"NEW SN #{idx+1}",
                value=row.get("new_sn", ""),
                key=f"sst_new_{idx}",
            )
            sst_items.append({"component": comp, "old_sn": old_sn, "new_sn": new_sn})
            st.divider()

    descricao = st.text_area(
        "📝 Details (facts only — what happened / issues / time / actions taken)",
        placeholder="Example:\nPower supply failure in ceiling. Power supply replaced + extension added. Tested OK."
    )

    st.markdown("### 🔧 Additional Materials Used")

    col1, col2 = st.columns(2)
    with col1:
        cat5 = st.checkbox("CAT5 Network Cable: L63")
        extension = st.checkbox("Power Extension: L38A")
        power_supply = st.checkbox("Power Supply: L64")
        power_cord = st.checkbox("Power Cord: L1")
        transceiver = st.checkbox("Transceiver: L61")

    with col2:
        transpower = st.checkbox("Transceiver Power: L62")
        powerbar = st.checkbox("Power Bar: L38")
        steel = st.checkbox("Steel Cable: L48")
        chain = st.checkbox("Hanging Chain: L46")

    extras_custom = st.text_area(
        "➕ Other materials (one per line)",
        placeholder="Cable ties\nVelcro straps\nEthernet coupler"
    )

    submitted = st.form_submit_button("✅ Generate Report")

# =====================
# BUILD REPORT
# =====================
if submitted:
    itens_extras: List[str] = []
    if cat5: itens_extras.append("CAT5 Network Cable: L63")
    if extension: itens_extras.append("Power Extension: L38A")
    if power_supply: itens_extras.append("Power Supply: L64")
    if power_cord: itens_extras.append("Power Cord: L1")
    if transceiver: itens_extras.append("Transceiver: L61")
    if transpower: itens_extras.append("Transceiver Power: L62")
    if powerbar: itens_extras.append("Power Bar: L38")
    if steel: itens_extras.append("Steel Cable: L48")
    if chain: itens_extras.append("Hanging Chain: L46")

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

    # -----------------
    # Generate outputs
    # -----------------
    if report_type == "PM":
        texto_final = template_pm(local_clean, reference_clean, details_final, extras_block)

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
                file_name="pm_report.txt",
                mime="text/plain",
            )

    elif report_type == "INSTALLATION":
        texto_final = template_installation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)

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
                file_name="installation_report.txt",
                mime="text/plain",
            )

    elif report_type == "DEINSTALLATION":
        texto_final = template_deinstallation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)

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
                file_name="deinstallation_report.txt",
                mime="text/plain",
            )

    elif report_type == "WJS BF":
        texto_final = template_wjs_bf(local_clean, reference_clean, details_final, extras_block)

        st.divider()
        st.subheader("📄 WJS BF - Service Report Summary")
        st.code(texto_final, language="text")

        colA, colB = st.columns(2)
        with colA:
            copy_to_clipboard_button(texto_final)
        with colB:
            st.download_button(
                "⬇️ Download WJS BF Report (.txt)",
                data=texto_final,
                file_name="wjs_bf_report.txt",
                mime="text/plain",
            )

    else:  # SST BF
        # Texto 1: email request
        email_text = format_sst_bf_request_email(reference_clean, sst_items)

        # Texto 2: replacement report (no formato que você pediu)
        sst_report_text = template_sst_bf_replacement_report(sst_items)

        st.divider()
        st.subheader("📧 SST BF - Ref Number Request Email")
        st.code(email_text, language="text")
        col1, col2 = st.columns(2)
        with col1:
            copy_to_clipboard_button(email_text, button_label="📋 Copy Email")
        with col2:
            st.download_button(
                "⬇️ Download Email Request (.txt)",
                data=email_text,
                file_name="sst_bf_email_request.txt",
                mime="text/plain",
            )

        st.divider()
        st.subheader("📄 SST BF - Replacement Report")
        st.code(sst_report_text, language="text")
        col3, col4 = st.columns(2)
        with col3:
            copy_to_clipboard_button(sst_report_text, button_label="📋 Copy Report")
        with col4:
            st.download_button(
                "⬇️ Download Replacement Report (.txt)",
                data=sst_report_text,
                file_name="sst_bf_replacement_report.txt",
                mime="text/plain",
            )
