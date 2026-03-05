import base64
import json
import hashlib
from io import BytesIO
from typing import List, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Report Generator (Advanced)", layout="centered")
st.title("🛠️ WJS Service Report Generator (Advanced)")
st.caption("Auto-extract (Place/RDL + WJS Label) • BF presets • SST replacement email+report • fast copy/download")
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

def _strip(s: Optional[str]) -> str:
    return (s or "").strip()

def _ensure_rdl_prefix(reference: str) -> str:
    ref = _strip(reference)
    if not ref:
        return "RDL: "
    # if user already typed "RDL:" keep
    if ref.lower().startswith("rdl"):
        return ref
    # if user typed just digits, prefix it
    return f"RDL: {ref}"

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

        place = _strip(data.get("place_name"))
        rdl_digits = _strip(data.get("rdl"))

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
            "item": _strip(data.get("item")),
            "pn": _strip(data.get("pn")),
            "sn": _strip(data.get("sn")),
        }

    except Exception as e:
        st.error(f"Error extracting WJS label: {e}")
        return {"item": "", "pn": "", "sn": ""}

# =====================
# AI: POLISH ONLY DETAILS
# =====================
def polish_details_ai(raw_details: str) -> str:
    raw_details = _strip(raw_details)
    if not raw_details:
        return ""
    if not client:
        return raw_details

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,  # safest
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
# COPY BUTTON (unique per key)
# =====================
def copy_to_clipboard_button(text: str, key: str, button_label: str = "📋 Copy"):
    safe_text = (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    uid = hashlib.md5(key.encode("utf-8")).hexdigest()[:10]
    ta_id = f"clipboard-text-{uid}"
    fn_id = f"copyText{uid}"

    components.html(
        f"""
        <textarea id="{ta_id}" style="position:absolute; left:-9999px; top:-9999px;">{safe_text}</textarea>
        <button onclick="{fn_id}()"
            style="background-color:#2563eb;color:white;border:none;padding:10px 16px;border-radius:6px;font-size:14px;cursor:pointer;">
            {button_label}
        </button>
        <script>
        function {fn_id}() {{
            const el = document.getElementById("{ta_id}");
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
# FORMATTERS / TEMPLATES
# =====================
def format_extras(itens_extras: List[str]) -> str:
    if not itens_extras:
        return ""
    lines = "\n".join([f"- {i}" for i in itens_extras])
    return f"Additional materials used:\n{lines}"

def format_wjs_info(item: str, pn: str, sn: str) -> str:
    item = _strip(item)
    pn = _strip(pn)
    sn = _strip(sn)
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

# ---------------------
# WJS BF: problem presets
# ---------------------
WJS_BF_PROBLEMS = {
    "— Select a common issue —": "",
    "Power supply failure (ceiling PSU)": (
        "After performing the necessary troubleshooting procedures, it was identified that the power supply located in the ceiling was malfunctioning.\n\n"
        "The faulty power supply was replaced, along with a cable extension, to restore proper operation of the Carmanah unit."
    ),
    "Transceiver / signal issue": (
        "After performing the necessary troubleshooting procedures, intermittent communication was observed between the Carmanah unit and its transceiver.\n\n"
        "Connections were reseated and verified, and the transceiver was replaced to restore stable operation."
    ),
    "Network / Ethernet issue": (
        "After performing the necessary troubleshooting procedures, a network connectivity issue was identified.\n\n"
        "The network cable and connections were inspected and corrected, and connectivity was restored. The unit was tested and confirmed operational."
    ),
    "Mounting / alignment / physical adjustment": (
        "After inspection, adjustments were required to ensure proper mounting and alignment.\n\n"
        "The unit was repositioned and secured, and functionality was verified after the adjustment."
    ),
    "Other (use Details below)": "",
}

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

# ---------------------
# SST BF: replacements + 2 texts
# ---------------------
SST_COMPONENT_CHOICES = [
    "Slip Reader",
    "Printer",
    "Scanner",
    "Pin Pad",
    "LCD",
    "Router",
    "Transceiver",
    "Burster",
    "Power Supply",
    "Other (type manually)",
]

def format_sst_bf_request_email(reference: str, items: List[Dict[str, str]]) -> str:
    reference = _strip(reference)

    clean = []
    for it in items or []:
        comp = _strip(it.get("component"))
        old_sn = _strip(it.get("old_sn"))
        new_sn = _strip(it.get("new_sn"))
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

def format_replaced_components_block(items: List[Dict[str, str]]) -> str:
    lines = []
    for it in items or []:
        comp = _strip(it.get("component"))
        old_sn = _strip(it.get("old_sn"))
        new_sn = _strip(it.get("new_sn"))
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
        comp = _strip(it.get("component"))
        old_sn = _strip(it.get("old_sn"))
        new_sn = _strip(it.get("new_sn"))
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
defaults = {
    "place_name": "",
    "rdl": "RDL: ",
    "wjs_item": "",
    "wjs_pn": "",
    "wjs_sn": "",
    "last_screenshot_hash": "",
    "last_label_hash": "",
    "report_type_preview": "PM",
    "wjs_bf_problem": "— Select a common issue —",
    "use_ai": True,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "sst_replacements" not in st.session_state:
    st.session_state.sst_replacements = [
        {"choice": "Slip Reader", "component": "Slip Reader", "old_sn": "", "new_sn": ""}
    ]

# =====================
# AUTO-FILL INPUTS (images)
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
st.caption("Use this for INSTALLATION / DEINSTALLATION (optional).")
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
# MAIN FORM (single submit)
# =====================
with st.form("report_form"):
    report_type = st.selectbox(
        "📄 Report Type",
        ["PM", "INSTALLATION", "DEINSTALLATION", "WJS BF", "SST BF"],
    )
    st.session_state.report_type_preview = report_type

    use_ai = st.checkbox(
        "🤖 Use AI to polish ONLY the 'Details' section (keeps layout fixed)",
        value=bool(st.session_state.get("use_ai", True)),
    )
    st.session_state.use_ai = use_ai

    if use_ai and not client:
        st.warning("AI is ON, but OPENAI_API_KEY is not set in secrets. Using your text as-is.")

    local = st.text_input("📍 Place Name", key="place_name")
    reference = st.text_input("🔢 Reference Number (RDL)", key="rdl")

    # WJS label block only for install/deinstall (like before)
    if report_type in ["INSTALLATION", "DEINSTALLATION"]:
        st.markdown("### 🏷️ WJS Info (optional)")
        st.text_input("Item", key="wjs_item")
        st.text_input("P/N", key="wjs_pn")
        st.text_input("S/N (Serial)", key="wjs_sn")

    # WJS BF: problem preset picker (advanced)
    if report_type == "WJS BF":
        st.markdown("### 🧠 WJS BF - Common Issue Presets (optional)")
        st.session_state.wjs_bf_problem = st.selectbox(
            "Select a common issue to auto-fill the Details text",
            list(WJS_BF_PROBLEMS.keys()),
            index=list(WJS_BF_PROBLEMS.keys()).index(st.session_state.get("wjs_bf_problem", "— Select a common issue —")),
        )
        st.caption("You can still edit Details below. The preset just helps you write faster.")

    # SST BF: replacement inputs (advanced)
    sst_items: List[Dict[str, str]] = []
    if report_type == "SST BF":
        st.markdown("### 🔁 SST BF - Components to Replace (Old SN / New SN)")
        st.caption("Tip: choose a component from the dropdown; use 'Other' to type.")

        for idx, row in enumerate(st.session_state.sst_replacements):
            st.markdown(f"**Component #{idx+1}**")

            choice = st.selectbox(
                f"Component type #{idx+1}",
                SST_COMPONENT_CHOICES,
                index=SST_COMPONENT_CHOICES.index(row.get("choice", "Slip Reader")) if row.get("choice") in SST_COMPONENT_CHOICES else 0,
                key=f"sst_choice_{idx}",
            )

            comp_value = row.get("component", "")
            if choice == "Other (type manually)":
                comp = st.text_input(
                    f"Component name #{idx+1}",
                    value=comp_value if comp_value and comp_value not in SST_COMPONENT_CHOICES else "",
                    key=f"sst_comp_{idx}",
                )
            else:
                comp = choice
                # show readonly-ish preview
                st.text_input(
                    f"Component name #{idx+1}",
                    value=comp,
                    key=f"sst_comp_preview_{idx}",
                    disabled=True,
                )

            old_sn = st.text_input(f"OLD SN #{idx+1}", value=row.get("old_sn", ""), key=f"sst_old_{idx}")
            new_sn = st.text_input(f"NEW SN #{idx+1}", value=row.get("new_sn", ""), key=f"sst_new_{idx}")

            sst_items.append({"component": comp, "old_sn": old_sn, "new_sn": new_sn})

            st.divider()

    # Details box (always present)
    details_placeholder = "Example:\nPower supply failure in ceiling. Power supply replaced + extension added. Tested OK."
    if report_type == "WJS BF":
        details_placeholder = "Example:\nPower supply failure. Replaced ceiling PSU + extension. Verified normal operation."
    if report_type == "SST BF":
        details_placeholder = "Optional notes (facts only). Example:\nSlip reader error observed. Replacement performed. SST tested OK."

    descricao = st.text_area(
        "📝 Details (facts only — what happened / issues / time / actions taken)",
        placeholder=details_placeholder
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

    submitted = st.form_submit_button("✅ Generate")

# =====================
# SST BF add/remove controls (OUTSIDE form)
# =====================
if st.session_state.get("report_type_preview") == "SST BF":
    st.subheader("➕➖ Manage SST BF Components")
    cA, cB, cC = st.columns([1, 1, 2])
    with cA:
        if st.button("➕ Add component", key="btn_add_comp"):
            st.session_state.sst_replacements.append({"choice": "Slip Reader", "component": "Slip Reader", "old_sn": "", "new_sn": ""})
            st.rerun()
    with cB:
        if st.button("➖ Remove last", key="btn_remove_comp"):
            if len(st.session_state.sst_replacements) > 1:
                st.session_state.sst_replacements.pop()
                st.rerun()
    with cC:
        st.caption("Add/remove here, then fill the fields inside the form above.")
    st.divider()

# =====================
# BUILD OUTPUTS
# =====================
if submitted:
    # Extras
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
    if _strip(extras_custom):
        itens_extras.extend([i.strip() for i in extras_custom.split("\n") if i.strip()])
    extras_block = format_extras(itens_extras)

    local_clean = _strip(local)
    reference_clean = _ensure_rdl_prefix(reference)

    # WJS info block (install/deinstall only)
    wjs_info_block = ""
    if report_type in ["INSTALLATION", "DEINSTALLATION"]:
        wjs_info_block = format_wjs_info(
            st.session_state.wjs_item,
            st.session_state.wjs_pn,
            st.session_state.wjs_sn,
        )

    # Details: apply presets + optional user notes
    details_raw = _strip(descricao)

    if report_type == "WJS BF":
        preset = WJS_BF_PROBLEMS.get(st.session_state.get("wjs_bf_problem", ""), "")
        # If user did not type details, auto-fill with preset.
        # If user typed, append preset only if preset exists and user didn't already paste a long paragraph.
        if not details_raw and preset:
            details_raw = preset
        elif details_raw and preset and preset not in details_raw:
            # keep user notes first, then preset
            details_raw = f"{details_raw}\n\n{preset}"

    # AI polish (optional)
    details_final = details_raw
    if use_ai and details_final:
        with st.spinner("Polishing details with AI..."):
            details_final = polish_details_ai(details_final)

    # ========== Generate per type ==========
    if report_type == "PM":
        texto_final = template_pm(local_clean, reference_clean, details_final, extras_block)

        st.subheader("📄 Generated Report")
        st.code(texto_final, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_to_clipboard_button(texto_final, key="copy_pm", button_label="📋 Copy Report")
        with c2:
            st.download_button("⬇️ Download (.txt)", data=texto_final, file_name="pm_report.txt", mime="text/plain")

    elif report_type == "INSTALLATION":
        texto_final = template_installation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)

        st.subheader("📄 Generated Report")
        st.code(texto_final, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_to_clipboard_button(texto_final, key="copy_install", button_label="📋 Copy Report")
        with c2:
            st.download_button("⬇️ Download (.txt)", data=texto_final, file_name="installation_report.txt", mime="text/plain")

    elif report_type == "DEINSTALLATION":
        texto_final = template_deinstallation(local_clean, reference_clean, details_final, extras_block, wjs_info_block)

        st.subheader("📄 Generated Report")
        st.code(texto_final, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_to_clipboard_button(texto_final, key="copy_deinstall", button_label="📋 Copy Report")
        with c2:
            st.download_button("⬇️ Download (.txt)", data=texto_final, file_name="deinstallation_report.txt", mime="text/plain")

    elif report_type == "WJS BF":
        texto_final = template_wjs_bf(local_clean, reference_clean, details_final, extras_block)

        st.subheader("📄 WJS BF - Service Report Summary")
        st.code(texto_final, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_to_clipboard_button(texto_final, key="copy_wjs_bf", button_label="📋 Copy Report")
        with c2:
            st.download_button("⬇️ Download (.txt)", data=texto_final, file_name="wjs_bf_report.txt", mime="text/plain")

    else:  # SST BF
        # Normalize sst_items from form inputs; also persist selections back into session_state
        normalized_items: List[Dict[str, str]] = []
        for idx, it in enumerate(sst_items):
            comp = _strip(it.get("component"))
            old_sn = _strip(it.get("old_sn"))
            new_sn = _strip(it.get("new_sn"))
            if comp or old_sn or new_sn:
                normalized_items.append({"component": comp, "old_sn": old_sn, "new_sn": new_sn})

            # persist into session state list for next run
            if idx < len(st.session_state.sst_replacements):
                st.session_state.sst_replacements[idx]["component"] = comp
                st.session_state.sst_replacements[idx]["old_sn"] = old_sn
                st.session_state.sst_replacements[idx]["new_sn"] = new_sn
                # choice is stored by selectbox key; keep existing
                st.session_state.sst_replacements[idx]["choice"] = st.session_state.get(f"sst_choice_{idx}", st.session_state.sst_replacements[idx].get("choice", "Slip Reader"))

        email_text = format_sst_bf_request_email(reference_clean, normalized_items)
        report_text = template_sst_bf_replacement_report(normalized_items)

        # Super-fast combined copy (both texts)
        combined = f"{email_text}\n\n" + ("=" * 60) + "\n\n" + report_text

        st.subheader("📧 SST BF - Ref Number Request Email")
        st.code(email_text, language="text")

        c1, c2 = st.columns(2)
        with c1:
            copy_to_clipboard_button(email_text, key="copy_sst_email", button_label="📋 Copy Email")
        with c2:
            st.download_button("⬇️ Download Email (.txt)", data=email_text, file_name="sst_bf_email_request.txt", mime="text/plain")

        st.subheader("📄 SST BF - Replacement Report")
        st.code(report_text, language="text")

        c3, c4 = st.columns(2)
        with c3:
            copy_to_clipboard_button(report_text, key="copy_sst_report", button_label="📋 Copy Report")
        with c4:
            st.download_button("⬇️ Download Report (.txt)", data=report_text, file_name="sst_bf_replacement_report.txt", mime="text/plain")

        st.subheader("⚡ One-click Copy (Email + Report)")
        copy_to_clipboard_button(combined, key="copy_sst_both", button_label="📋 Copy Both (Email + Report)")
        st.download_button("⬇️ Download Both (.txt)", data=combined, file_name="sst_bf_email_and_report.txt", mime="text/plain")
