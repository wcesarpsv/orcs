import base64
import hashlib
import html
import json
from io import BytesIO
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image, ImageOps


# ============================================================
# PAGE
# ============================================================
st.set_page_config(page_title="WJS Report Generator (Advanced)", layout="centered")
st.title("🛠️ WJS Report Generator (Advanced)")
st.caption(
    "Auto-extract (Place/RDL + WJS Label) • WJS BF presets • "
    "SST BF (email + report) • SN auto-fill via photos"
)
st.divider()


# ============================================================
# CONFIG / CLIENT
# ============================================================
AI_MODEL = "gpt-4o-mini"


def get_openai_client():
    try:
        key = st.secrets.get("OPENAI_API_KEY", None)
        if not key:
            return None
        return OpenAI(api_key=key)
    except Exception:
        return None


client = get_openai_client()


# ============================================================
# HELPERS
# ============================================================
def strip_value(value: Optional[str]) -> str:
    return (value or "").strip()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest() if data else ""


def image_to_data_url(data: bytes, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Rotate phone photos correctly and reduce oversized uploads."""
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1800, 1800))
            output = BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue(), "image/jpeg"
    except Exception:
        return data, "image/jpeg"


def preview_image(data: bytes, caption: str) -> None:
    try:
        with Image.open(BytesIO(data)) as image:
            st.image(ImageOps.exif_transpose(image), caption=caption, use_container_width=True)
    except Exception:
        st.warning("Could not preview this image.")


def ensure_rdl_prefix(reference: str) -> str:
    reference = strip_value(reference)
    if not reference:
        return "RDL: "
    digits_or_text = reference[4:].strip() if reference.lower().startswith("rdl:") else reference
    if reference.lower().startswith("rdl") and not reference.lower().startswith("rdl:"):
        digits_or_text = reference[3:].strip()
    return f"RDL: {digits_or_text}"


def parse_json_response(raw: str) -> Dict[str, str]:
    raw = strip_value(raw)
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(raw or "{}")
    return parsed if isinstance(parsed, dict) else {}


def vision_json(data: bytes, system_prompt: str, user_prompt: str) -> Dict[str, str]:
    if not client or not data:
        return {}
    prepared, mime_type = prepare_image(data)
    response = client.chat.completions.create(
        model=AI_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(prepared, mime_type), "detail": "high"},
                    },
                ],
            },
        ],
    )
    return parse_json_response(response.choices[0].message.content or "{}")


def extract_place_rdl(data: bytes) -> Dict[str, str]:
    prompt = """
Extract structured data from a field-service mobile app screenshot.
Return only valid JSON with keys "place_name" and "rdl".
The store name is normally large bold text near the top. RDL is a numeric value
beside a label named RDL. Return RDL as digits only. Use an empty string when a
field is not clearly visible. Never guess.
"""
    result = vision_json(data, prompt, "Extract the store name and RDL number.")
    place = strip_value(result.get("place_name"))
    rdl = "".join(character for character in strip_value(result.get("rdl")) if character.isdigit())
    return {"place_name": place, "rdl": f"RDL: {rdl}" if rdl else ""}


def extract_wjs_label(data: bytes) -> Dict[str, str]:
    prompt = """
Extract a hardware sticker. Return only valid JSON with keys "item", "pn", and
"sn". item is the product name or description, pn is the part number, and sn is
the serial number or ID. Copy visible values exactly. Use an empty string for an
unclear or missing field. Never guess.
"""
    result = vision_json(data, prompt, "Extract item, P/N, and S/N from this label.")
    return {key: strip_value(result.get(key)) for key in ("item", "pn", "sn")}


def extract_component_sn(data: bytes) -> str:
    prompt = """
Extract the primary serial number from this hardware label. Return only valid
JSON with one key named "sn". Prefer a value explicitly labeled SN, S/N, Serial,
or Serial Number. Do not return a model number, part number, MAC address, or IMEI
unless it is explicitly the serial number. Preserve letters, numbers, hyphens,
and leading zeroes exactly. Return an empty string if uncertain. Never guess.
"""
    result = vision_json(data, prompt, "Extract only the component serial number.")
    serial = strip_value(result.get("sn"))
    for prefix in ("S/N:", "SN:", "S/N", "SN"):
        if serial.upper().startswith(prefix):
            serial = serial[len(prefix):].strip()
            break
    return serial


def polish_details(raw_details: str) -> str:
    raw_details = strip_value(raw_details)
    if not raw_details or not client:
        return raw_details
    response = client.chat.completions.create(
        model=AI_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite the technician notes as a concise, professional English service-report "
                    "details section. Preserve every fact and do not add assumptions, names, parts, "
                    "outcomes, or actions that were not stated. Return only the revised details."
                ),
            },
            {"role": "user", "content": raw_details},
        ],
    )
    return strip_value(response.choices[0].message.content) or raw_details


def copy_button(text: str, key: str, label: str) -> None:
    uid = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    js_text = json.dumps(text or "").replace("</", "<\\/")
    safe_label = html.escape(label)
    components.html(
        f"""
        <button id="button-{uid}" style="background:#2563eb;color:white;border:0;
        padding:10px 16px;border-radius:6px;font-size:14px;cursor:pointer;">{safe_label}</button>
        <script>
        const button = document.getElementById("button-{uid}");
        button.addEventListener("click", async () => {{
          try {{
            await navigator.clipboard.writeText({js_text});
            const original = button.textContent;
            button.textContent = "✅ Copied!";
            setTimeout(() => button.textContent = original, 1400);
          }} catch (error) {{
            button.textContent = "Copy unavailable";
          }}
        }});
        </script>
        """,
        height=55,
    )


# ============================================================
# TEMPLATES
# ============================================================
WJS_BF_PROBLEMS = {
    "— Select a common issue —": "",
    "Power supply failure (ceiling PSU)": (
        "After performing the necessary troubleshooting procedures, it was identified that the power "
        "supply located in the ceiling was malfunctioning.\n\nThe faulty power supply was replaced, "
        "along with a cable extension, to restore proper operation of the Carmanah unit."
    ),
    "Transceiver / signal issue": (
        "After performing the necessary troubleshooting procedures, intermittent communication was "
        "observed between the Carmanah unit and its transceiver.\n\nConnections were reseated and "
        "verified, and the transceiver was replaced to restore stable operation."
    ),
    "Network / Ethernet issue": (
        "After performing the necessary troubleshooting procedures, a network connectivity issue was "
        "identified.\n\nThe network cable and connections were inspected and corrected, connectivity "
        "was restored, and the unit was confirmed operational."
    ),
    "Mounting / alignment / physical adjustment": (
        "After inspection, adjustments were required to ensure proper mounting and alignment.\n\n"
        "The unit was repositioned and secured, and functionality was verified after the adjustment."
    ),
    "Other (use Details below)": "",
}

SST_COMPONENT_CHOICES = [
    "Slip Reader", "Printer", "Scanner", "Pin Pad", "LCD", "Router",
    "Transceiver", "Burster", "Power Supply", "Other (type manually)",
]

MATERIALS = {
    "material_cat5": "CAT5 Network Cable: L63",
    "material_extension": "Power Extension: L38A",
    "material_power_supply": "Power Supply: L64",
    "material_power_cord": "Power Cord: L1",
    "material_transceiver": "Transceiver: L61",
    "material_transpower": "Transceiver Power: L62",
    "material_powerbar": "Power Bar: L38",
    "material_steel": "Steel Cable: L48",
    "material_chain": "Hanging Chain: L46",
}


def extras_block(items: List[str]) -> str:
    return "Additional materials used:\n" + "\n".join(f"- {item}" for item in items) if items else ""


def wjs_info_block(item: str, pn: str, sn: str) -> str:
    values = [("Item", strip_value(item)), ("P/N", strip_value(pn)), ("S/N", strip_value(sn))]
    lines = [f"- {name}: {value}" for name, value in values if value]
    return "WJS Info:\n" + "\n".join(lines) if lines else ""


def append_optional(base: str, *blocks: str) -> str:
    return "\n\n".join([strip_value(base), *[strip_value(block) for block in blocks if strip_value(block)]])


def template_pm(place: str, rdl: str, details: str, extras: str) -> str:
    base = f"""PM completed at {place} ({rdl}) - Summary

{details}

Burster bins, rollers, and all related peripherals were cleaned.
Serial numbers for all components were recorded for database entry.
All hardware components, including the pin pad, were tested and verified as operational.

Keys were returned to the retailer upon completion."""
    return append_optional(base, extras)


def template_installation(place: str, rdl: str, details: str, extras: str, info: str) -> str:
    base = f"""WJS Large Carmanah - {place} ({rdl}) - Installation Summary

Upon arrival at the site, the retailer indicated the preferred installation location and desired height for the sign.

{details or 'No issues reported.'}"""
    ending = "After completion, I explained the work performed to the retailer and demonstrated that the equipment was operating correctly."
    return append_optional(base, info, ending, extras)


def template_deinstallation(place: str, rdl: str, details: str, extras: str, info: str) -> str:
    base = f"""WJS Sign Deinstallation - {place} ({rdl}) - Summary

Upon arrival at the site, the retailer indicated the sign to be removed.

{details or 'No issues reported.'}"""
    return append_optional(base, info, "The equipment is being returned to the warehouse.", extras)


def template_wjs_bf(place: str, rdl: str, details: str, extras: str) -> str:
    base = f"""WJS Carmanah Break/Fix - {place} ({rdl}) - Summary

Upon arrival at the site, I spoke with the retailer and was directed to the location of the Carmanah unit.

{details or 'No issues reported.'}

I remained on-site for approximately 15 minutes to monitor the equipment and confirm that it was functioning normally.

The retailer was informed that the unit is now operating normally."""
    return append_optional(base, extras)


def clean_replacements(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    clean = []
    for item in items:
        component = strip_value(item.get("component"))
        old_sn = strip_value(item.get("old_sn"))
        new_sn = strip_value(item.get("new_sn"))
        if component and (old_sn or new_sn):
            clean.append({"component": component, "old_sn": old_sn, "new_sn": new_sn})
    return clean


def sst_email(rdl: str, items: List[Dict[str, str]]) -> str:
    items = clean_replacements(items) or [{"component": "Component", "old_sn": "", "new_sn": ""}]
    blocks = []
    for item in items:
        blocks.append(
            f"{item['component'].upper()}:\n\nOLD SN:\n{item['old_sn']}\n\nNEW SN:\n{item['new_sn']}"
        )
    return f"""Hello,

I'm requesting one reference number for component replacement at {rdl}, as comprehensive testing indicated that this replacement was necessary.

Attached is the component list recorded before any changes were made.

The old and new component serial numbers are listed below:

{chr(10).join(chr(10) + block for block in blocks).strip()}"""


def replacement_lines(items: List[Dict[str, str]]) -> str:
    lines = []
    for item in clean_replacements(items):
        component, old_sn, new_sn = item["component"], item["old_sn"], item["new_sn"]
        if old_sn and new_sn:
            lines.append(f"- {component} (OLD SN: {old_sn} → NEW SN: {new_sn})")
        elif old_sn:
            lines.append(f"- {component} (OLD SN: {old_sn})")
        elif new_sn:
            lines.append(f"- {component} (NEW SN: {new_sn})")
    return "\n".join(lines) or "- (No components listed)"


def sst_report(items: List[Dict[str, str]], notes: str = "") -> str:
    clean = clean_replacements(items)
    listed = replacement_lines(clean)
    if len(clean) == 1:
        component = clean[0]["component"].lower()
        opening = (
            f"Following communication with the retailer, it was identified that the {component} was "
            "experiencing operational issues. Subsequent diagnostic testing confirmed that replacement was necessary."
        )
        result = (
            f"The {component} was replaced. Post-replacement testing confirmed that the SST system "
            f"returned to full operational capacity, with no further errors related to the {component}."
        )
    else:
        opening = (
            "Following communication with the retailer, it was identified that multiple SST components "
            "were experiencing operational issues. Subsequent diagnostic testing confirmed that the affected units required replacement."
        )
        result = (
            "The components were replaced. Post-replacement testing confirmed that the SST system "
            "returned to full operational capacity, with no further related errors."
        )
    notes_block = f"Additional service details:\n{notes}" if strip_value(notes) else ""
    return append_optional(
        f"Hello,\n\n{opening}\n\nReplaced component(s):\n{listed}",
        notes_block,
        result,
        "The updated and previous component lists are attached for review.",
    )


# ============================================================
# SESSION STATE
# ============================================================
DEFAULTS = {
    "report_type": "PM",
    "place_name": "",
    "rdl": "RDL: ",
    "wjs_item": "",
    "wjs_pn": "",
    "wjs_sn": "",
    "wjs_bf_problem": "— Select a common issue —",
    "use_ai": True,
    "details": "",
    "other_materials": "",
    "last_screenshot_hash": "",
    "last_label_hash": "",
    "sst_rows": 1,
    "generated_outputs": None,
}
for state_key, default in DEFAULTS.items():
    st.session_state.setdefault(state_key, default)
for material_key in MATERIALS:
    st.session_state.setdefault(material_key, False)


def initialize_sst_row(index: int) -> None:
    st.session_state.setdefault(f"sst_choice_{index}", "Slip Reader")
    st.session_state.setdefault(f"sst_custom_{index}", "")
    st.session_state.setdefault(f"sst_old_{index}", "")
    st.session_state.setdefault(f"sst_new_{index}", "")
    st.session_state.setdefault(f"sst_old_hash_{index}", "")
    st.session_state.setdefault(f"sst_new_hash_{index}", "")


for row_index in range(st.session_state.sst_rows):
    initialize_sst_row(row_index)


def add_sst_row() -> None:
    new_index = st.session_state.sst_rows
    st.session_state.sst_rows += 1
    initialize_sst_row(new_index)
    st.session_state.generated_outputs = None


def remove_sst_row() -> None:
    if st.session_state.sst_rows <= 1:
        return
    index = st.session_state.sst_rows - 1
    for prefix in ("sst_choice", "sst_custom", "sst_old", "sst_new", "sst_old_hash", "sst_new_hash", "sst_old_photo", "sst_new_photo"):
        st.session_state.pop(f"{prefix}_{index}", None)
    st.session_state.sst_rows -= 1
    st.session_state.generated_outputs = None


# ============================================================
# REACTIVE CONTROLS (intentionally outside st.form)
# ============================================================
report_type = st.selectbox(
    "📄 Report Type",
    ["PM", "INSTALLATION", "DEINSTALLATION", "WJS BF", "SST BF"],
    key="report_type",
)

with st.expander("📸 Auto-fill Place Name + RDL", expanded=False):
    screenshot = st.file_uploader("Upload screenshot", type=["png", "jpg", "jpeg"], key="screenshot_upload")
    if screenshot:
        screenshot_bytes = screenshot.getvalue()
        preview_image(screenshot_bytes, "Screenshot preview")
        current_hash = hash_bytes(screenshot_bytes)
        if not client:
            st.warning("OPENAI_API_KEY is missing from Streamlit secrets.")
        elif current_hash != st.session_state.last_screenshot_hash:
            try:
                with st.spinner("Extracting Place Name and RDL..."):
                    extracted = extract_place_rdl(screenshot_bytes)
                if extracted["place_name"]:
                    st.session_state.place_name = extracted["place_name"]
                if extracted["rdl"]:
                    st.session_state.rdl = extracted["rdl"]
                st.session_state.last_screenshot_hash = current_hash
                st.success("Place Name and RDL updated.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not extract Place/RDL: {error}")

if report_type in ("INSTALLATION", "DEINSTALLATION"):
    with st.expander("🏷️ Auto-fill WJS label", expanded=False):
        label_photo = st.file_uploader("Upload label photo", type=["png", "jpg", "jpeg"], key="label_upload")
        if label_photo:
            label_bytes = label_photo.getvalue()
            preview_image(label_bytes, "WJS label preview")
            current_hash = hash_bytes(label_bytes)
            if not client:
                st.warning("OPENAI_API_KEY is missing from Streamlit secrets.")
            elif current_hash != st.session_state.last_label_hash:
                try:
                    with st.spinner("Extracting WJS label information..."):
                        extracted = extract_wjs_label(label_bytes)
                    for key in ("item", "pn", "sn"):
                        if extracted[key]:
                            st.session_state[f"wjs_{key}"] = extracted[key]
                    st.session_state.last_label_hash = current_hash
                    st.success("WJS information updated.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not extract the WJS label: {error}")


# SST photos appear BEFORE their text widgets. This makes session-state updates legal.
if report_type == "SST BF":
    st.subheader("🔁 SST BF Components")
    add_col, remove_col, _ = st.columns([1, 1, 2])
    add_col.button("➕ Add component", on_click=add_sst_row, use_container_width=True)
    remove_col.button(
        "➖ Remove last",
        on_click=remove_sst_row,
        disabled=st.session_state.sst_rows <= 1,
        use_container_width=True,
    )

    with st.expander("📷 Upload OLD/NEW component photos", expanded=True):
        if not client:
            st.warning("OPENAI_API_KEY is missing. Photo extraction is disabled, but SNs can still be entered manually.")
        for index in range(st.session_state.sst_rows):
            st.markdown(f"**Component #{index + 1}**")
            old_column, new_column = st.columns(2)
            old_photo = old_column.file_uploader(
                f"OLD component photo #{index + 1}",
                type=["png", "jpg", "jpeg"],
                key=f"sst_old_photo_{index}",
            )
            new_photo = new_column.file_uploader(
                f"NEW component photo #{index + 1}",
                type=["png", "jpg", "jpeg"],
                key=f"sst_new_photo_{index}",
            )

            for side, upload in (("old", old_photo), ("new", new_photo)):
                if upload and client:
                    photo_bytes = upload.getvalue()
                    current_hash = hash_bytes(photo_bytes)
                    hash_key = f"sst_{side}_hash_{index}"
                    value_key = f"sst_{side}_{index}"
                    if current_hash != st.session_state[hash_key]:
                        try:
                            with st.spinner(f"Extracting {side.upper()} SN for Component #{index + 1}..."):
                                serial = extract_component_sn(photo_bytes)
                            st.session_state[hash_key] = current_hash
                            if serial:
                                st.session_state[value_key] = serial
                                st.success(f"{side.upper()} SN #{index + 1}: {serial}")
                            else:
                                st.warning(f"No reliable {side.upper()} serial number was found. Enter it manually below.")
                            st.rerun()
                        except Exception as error:
                            st.session_state[hash_key] = current_hash
                            st.error(f"Could not extract {side.upper()} SN #{index + 1}: {error}")
            if index < st.session_state.sst_rows - 1:
                st.divider()

st.divider()


# ============================================================
# INPUTS / GENERATION
# ============================================================
st.checkbox(
    "🤖 Use AI to polish only the Details section",
    key="use_ai",
    disabled=not client,
    help="The fixed report layout is never sent for rewriting.",
)
if not client:
    st.caption("AI polishing and photo extraction require OPENAI_API_KEY in Streamlit secrets.")

st.text_input("📍 Place Name", key="place_name")
st.text_input("🔢 Reference Number (RDL)", key="rdl")

if report_type in ("INSTALLATION", "DEINSTALLATION"):
    st.markdown("### 🏷️ WJS Info")
    st.text_input("Item", key="wjs_item")
    st.text_input("P/N", key="wjs_pn")
    st.text_input("S/N", key="wjs_sn")

if report_type == "WJS BF":
    st.markdown("### 🧠 Common issue preset")
    st.selectbox("Issue preset", list(WJS_BF_PROBLEMS), key="wjs_bf_problem")
    st.caption("The preset is added only when the report is generated. Your Details text remains editable.")

sst_items: List[Dict[str, str]] = []
if report_type == "SST BF":
    st.markdown("### Component information")
    for index in range(st.session_state.sst_rows):
        st.markdown(f"**Component #{index + 1}**")
        st.selectbox(
            f"Component type #{index + 1}",
            SST_COMPONENT_CHOICES,
            key=f"sst_choice_{index}",
        )
        choice = st.session_state[f"sst_choice_{index}"]
        if choice == "Other (type manually)":
            st.text_input(f"Component name #{index + 1}", key=f"sst_custom_{index}")
            component_name = st.session_state[f"sst_custom_{index}"]
        else:
            component_name = choice
        serial_columns = st.columns(2)
        serial_columns[0].text_input(f"OLD SN #{index + 1}", key=f"sst_old_{index}")
        serial_columns[1].text_input(f"NEW SN #{index + 1}", key=f"sst_new_{index}")
        sst_items.append(
            {
                "component": component_name,
                "old_sn": st.session_state[f"sst_old_{index}"],
                "new_sn": st.session_state[f"sst_new_{index}"],
            }
        )

details_placeholder = {
    "WJS BF": "Example: Replaced the ceiling power supply and extension. Tested OK.",
    "SST BF": "Optional factual notes about diagnosis, replacement, and testing.",
}.get(report_type, "Describe what happened, issues found, time spent, and actions taken.")
st.text_area("📝 Details (facts only)", key="details", placeholder=details_placeholder, height=150)

st.markdown("### 🔧 Additional Materials Used")
left, right = st.columns(2)
material_keys = list(MATERIALS)
for position, material_key in enumerate(material_keys):
    target = left if position < 5 else right
    target.checkbox(MATERIALS[material_key], key=material_key)
st.text_area("➕ Other materials (one per line)", key="other_materials", height=100)


def generate_outputs() -> None:
    selected_materials = [label for key, label in MATERIALS.items() if st.session_state[key]]
    selected_materials.extend(
        line.strip() for line in st.session_state.other_materials.splitlines() if line.strip()
    )
    extras = extras_block(selected_materials)
    place = strip_value(st.session_state.place_name)
    rdl = ensure_rdl_prefix(st.session_state.rdl)
    details = strip_value(st.session_state.details)

    if report_type == "WJS BF":
        preset = WJS_BF_PROBLEMS.get(st.session_state.wjs_bf_problem, "")
        details = append_optional(details, preset) if preset and preset not in details else details

    if st.session_state.use_ai and details and client:
        details = polish_details(details)

    if report_type == "PM":
        st.session_state.generated_outputs = {
            "type": report_type,
            "report": template_pm(place, rdl, details, extras),
        }
    elif report_type == "INSTALLATION":
        info = wjs_info_block(st.session_state.wjs_item, st.session_state.wjs_pn, st.session_state.wjs_sn)
        st.session_state.generated_outputs = {
            "type": report_type,
            "report": template_installation(place, rdl, details, extras, info),
        }
    elif report_type == "DEINSTALLATION":
        info = wjs_info_block(st.session_state.wjs_item, st.session_state.wjs_pn, st.session_state.wjs_sn)
        st.session_state.generated_outputs = {
            "type": report_type,
            "report": template_deinstallation(place, rdl, details, extras, info),
        }
    elif report_type == "WJS BF":
        st.session_state.generated_outputs = {
            "type": report_type,
            "report": template_wjs_bf(place, rdl, details, extras),
        }
    else:
        st.session_state.generated_outputs = {
            "type": report_type,
            "email": sst_email(rdl, sst_items),
            "report": sst_report(sst_items, details),
        }


if st.button("✅ Generate", type="primary", use_container_width=True):
    try:
        with st.spinner("Generating report..."):
            generate_outputs()
    except Exception as error:
        st.error(f"Could not generate the report: {error}")


# ============================================================
# PERSISTENT OUTPUT
# ============================================================
outputs = st.session_state.generated_outputs
if outputs and outputs.get("type") == report_type:
    st.divider()
    if report_type == "SST BF":
        email_text = outputs["email"]
        report_text = outputs["report"]
        combined = f"{email_text}\n\n{'=' * 60}\n\n{report_text}"

        st.subheader("📧 SST BF - Reference Number Request Email")
        st.code(email_text, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_button(email_text, "sst_email", "📋 Copy Email")
        with c2:
            st.download_button("⬇️ Download Email", email_text, "sst_bf_email_request.txt", "text/plain")

        st.subheader("📄 SST BF - Replacement Report")
        st.code(report_text, language="text")
        c3, c4 = st.columns(2)
        with c3:
            copy_button(report_text, "sst_report", "📋 Copy Report")
        with c4:
            st.download_button("⬇️ Download Report", report_text, "sst_bf_replacement_report.txt", "text/plain")

        st.subheader("⚡ Email + Report")
        copy_button(combined, "sst_combined", "📋 Copy Both")
        st.download_button("⬇️ Download Both", combined, "sst_bf_email_and_report.txt", "text/plain")
    else:
        report_text = outputs["report"]
        filenames = {
            "PM": "pm_report.txt",
            "INSTALLATION": "installation_report.txt",
            "DEINSTALLATION": "deinstallation_report.txt",
            "WJS BF": "wjs_bf_report.txt",
        }
        st.subheader("📄 Generated Report")
        st.code(report_text, language="text")
        c1, c2 = st.columns(2)
        with c1:
            copy_button(report_text, f"copy_{report_type}", "📋 Copy Report")
        with c2:
            st.download_button("⬇️ Download", report_text, filenames[report_type], "text/plain")
