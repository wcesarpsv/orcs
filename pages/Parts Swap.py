import base64
import hashlib
import json
from io import BytesIO
from typing import Dict

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image


# =====================
# CONFIG
# =====================
st.set_page_config(page_title="SST Component Replacement Request", layout="centered")
st.title("🔄 SST Component Replacement Request")
st.caption("Create a standardized REF request with OLD and NEW component serial numbers.")
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


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest() if data else ""


def _safe_open_image(img_bytes: bytes):
    try:
        return Image.open(BytesIO(img_bytes))
    except Exception:
        return None


def _digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _clean_rdl(value: str) -> str:
    value = (value or "").strip()
    if value.upper().startswith("RDL:"):
        value = value.split(":", 1)[1].strip()
    return value


def _component_display(component: str, other_component: str = "") -> str:
    if component == "Other":
        return (other_component or "Component").strip()
    if component.startswith("Burster "):
        number = component.split()[-1]
        return f"Burster No. {number}"
    return component


def _replacement_reason_sentence(reason: str, other_reason: str = "") -> str:
    custom = (other_reason or "").strip()
    options = {
        "Failed comprehensive testing": "comprehensive testing has indicated the necessity of this replacement",
        "Intermittent operation": "the component demonstrated intermittent operation during testing",
        "Component jammed": "the component was found jammed and could not operate correctly",
        "Component not responding": "the component was not responding during testing",
        "Physical damage": "physical damage was identified on the component",
        "Printing issue": "testing confirmed a printing-related failure",
        "Reading issue": "testing confirmed that the component was unable to read correctly",
        "Other": custom or "testing has indicated the necessity of this replacement",
    }
    return options.get(reason, options["Failed comprehensive testing"])


# =====================
# AI VISION
# =====================
def extract_site_from_screenshot(img_bytes: bytes) -> Dict[str, str]:
    if not client or not img_bytes:
        return {"place_name": "", "address": "", "rl": "", "rdl": ""}

    system_prompt = """
You are extracting structured data from a field-service mobile app screenshot.

Return ONLY valid JSON:
{
  "place_name": "string",
  "address": "string",
  "rl": "digits only",
  "rdl": "digits only"
}

Rules:
- Extract exactly what is visible.
- Store name is normally in large bold text near the top.
- RL and RDL appear as labeled fields.
- Do not invent missing or truncated information.
- Use an empty string when a field cannot be read.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the site information."},
                        {"type": "image_url", "image_url": {"url": _img_bytes_to_data_url(img_bytes)}},
                    ],
                },
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return {
            "place_name": (data.get("place_name") or "").strip(),
            "address": (data.get("address") or "").strip(),
            "rl": _digits_only(data.get("rl") or ""),
            "rdl": _digits_only(data.get("rdl") or ""),
        }
    except Exception as exc:
        st.error(f"Error extracting site information: {exc}")
        return {"place_name": "", "address": "", "rl": "", "rdl": ""}


def extract_component_label(img_bytes: bytes) -> Dict[str, str]:
    if not client or not img_bytes:
        return {"item": "", "pn": "", "sn": ""}

    system_prompt = """
You are reading an SST hardware component label.

Return ONLY valid JSON:
{
  "item": "component name exactly as visible",
  "pn": "part number exactly as visible",
  "sn": "complete serial number exactly as visible"
}

Rules:
- Prefer the number identified by a barcode and used as the component serial number.
- Serial numbers may be long numeric or alphanumeric values.
- Do not return a manufacture date, short asset code, or part number as the serial number.
- Do not add spaces or remove leading zeroes from the serial number.
- Use an empty string if a field cannot be read confidently.
- Do not invent.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the component name, P/N, and complete S/N."},
                        {"type": "image_url", "image_url": {"url": _img_bytes_to_data_url(img_bytes)}},
                    ],
                },
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return {
            "item": (data.get("item") or "").strip(),
            "pn": (data.get("pn") or "").strip(),
            "sn": (data.get("sn") or "").strip().replace(" ", ""),
        }
    except Exception as exc:
        st.error(f"Error extracting component label: {exc}")
        return {"item": "", "pn": "", "sn": ""}


# =====================
# COPY BUTTON
# =====================
def copy_to_clipboard_button(text: str):
    # JSON encoding safely transports newlines and quotes into JavaScript.
    js_text = json.dumps(text or "")
    components.html(
        f"""
        <button onclick="copyRequest()"
            style="width:100%;background-color:#2563eb;color:white;border:none;
                   padding:11px 16px;border-radius:7px;font-size:14px;cursor:pointer;">
            📋 Copy Request
        </button>
        <script>
        function copyRequest() {{
            navigator.clipboard.writeText({js_text}).then(() => {{
                const button = document.querySelector('button');
                button.innerText = '✅ Request copied!';
                setTimeout(() => button.innerText = '📋 Copy Request', 1800);
            }}).catch(() => alert('Could not copy automatically. Please copy manually.'));
        }}
        </script>
        """,
        height=55,
    )


# =====================
# REQUEST TEMPLATE
# =====================
def build_request(
    place_name: str,
    address: str,
    rl: str,
    rdl: str,
    sst_serial: str,
    component_name: str,
    old_sn: str,
    new_sn: str,
    reason_sentence: str,
    details: str,
    component_list_attached: bool,
    old_photo_attached: bool,
    new_photo_attached: bool,
) -> str:
    site_lines = []
    if place_name.strip():
        site_lines.append(place_name.strip())
    if rl.strip():
        site_lines.append(f"RL: {rl.strip()}")
    site_lines.append(f"RDL: {rdl.strip()}")
    if address.strip():
        site_lines.append(f"Address: {address.strip()}")
    if sst_serial.strip():
        site_lines.append(f"SST Serial #: {sst_serial.strip()}")

    component_upper = component_name.upper()
    report = f"""
Hello,

I'm requesting one REF number for the replacement of {component_name} at RDL {rdl.strip()}, as {reason_sentence}.

Site information:

{chr(10).join(site_lines)}

Please find the old and new component serial numbers below:

OLD {component_upper} SN:
{old_sn.strip()}

NEW {component_upper} SN:
{new_sn.strip()}
""".strip()

    if details.strip():
        report += f"\n\nAdditional details:\n{details.strip()}"

    attachment_lines = []
    if component_list_attached:
        attachment_lines.append("The component list completed before the replacement is attached.")
    if old_photo_attached and new_photo_attached:
        attachment_lines.append("Photos of the old and new components are also attached.")
    elif old_photo_attached:
        attachment_lines.append("A photo of the old component is also attached.")
    elif new_photo_attached:
        attachment_lines.append("A photo of the new component is also attached.")

    if attachment_lines:
        report += "\n\n" + "\n".join(attachment_lines)

    return report + "\n\nThank you."


# =====================
# SESSION STATE
# =====================
DEFAULTS = {
    "replacement_place_name": "",
    "replacement_address": "",
    "replacement_rl": "",
    "replacement_rdl": "",
    "replacement_sst_serial": "",
    "replacement_old_sn": "",
    "replacement_new_sn": "",
    "replacement_old_item": "",
    "replacement_new_item": "",
    "replacement_old_pn": "",
    "replacement_new_pn": "",
    "replacement_last_site_hash": "",
    "replacement_last_old_hash": "",
    "replacement_last_new_hash": "",
    "replacement_generated_text": "",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def clear_page():
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    # Reset uploader widgets by changing their keys.
    st.session_state["replacement_uploader_version"] = st.session_state.get("replacement_uploader_version", 0) + 1


def swap_serials():
    old_value = st.session_state.replacement_old_sn
    st.session_state.replacement_old_sn = st.session_state.replacement_new_sn
    st.session_state.replacement_new_sn = old_value


uploader_version = st.session_state.get("replacement_uploader_version", 0)


# =====================
# AUTO-FILL SITE
# =====================
st.subheader("📸 Site Information")
st.caption("Upload the service-call screenshot to auto-fill the retailer, address, RL, and RDL.")

site_screenshot = st.file_uploader(
    "Upload site screenshot (PNG/JPG)",
    type=["png", "jpg", "jpeg"],
    key=f"replacement_site_photo_{uploader_version}",
)

if site_screenshot is not None:
    site_bytes = site_screenshot.getvalue()
    site_hash = _hash_bytes(site_bytes)
    preview = _safe_open_image(site_bytes)
    if preview:
        st.image(preview, caption="Site screenshot preview", use_container_width=True)

    if not client:
        st.warning("OPENAI_API_KEY not set in secrets — auto-extract disabled. Enter the information manually.")
    elif site_hash and site_hash != st.session_state.replacement_last_site_hash:
        with st.spinner("Extracting site information..."):
            extracted = extract_site_from_screenshot(site_bytes)
            if extracted["place_name"]:
                st.session_state.replacement_place_name = extracted["place_name"]
            if extracted["address"]:
                st.session_state.replacement_address = extracted["address"]
            if extracted["rl"]:
                st.session_state.replacement_rl = extracted["rl"]
            if extracted["rdl"]:
                st.session_state.replacement_rdl = extracted["rdl"]
            st.session_state.replacement_last_site_hash = site_hash
        st.success("Site information updated automatically!")

col_site_1, col_site_2 = st.columns(2)
with col_site_1:
    st.text_input("📍 Retailer / Site Name *", key="replacement_place_name")
    st.text_input("🔢 RL", key="replacement_rl")
with col_site_2:
    st.text_input("📫 Address", key="replacement_address")
    st.text_input("🔢 RDL *", key="replacement_rdl")

st.text_input("🖥️ SST Serial # (optional)", key="replacement_sst_serial")
st.divider()


# =====================
# COMPONENT AND LABELS
# =====================
st.subheader("🔧 Component Replacement")

component_options = [
    "Burster 1", "Burster 2", "Burster 3", "Burster 4", "Burster 5", "Burster 6", "Burster 7",
    "Scanner", "Printer", "Slip Reader", "LCD", "Keypad", "Enclosure", "Router", "Pin Pad", "Other",
]

reason_options = [
    "Failed comprehensive testing",
    "Intermittent operation",
    "Component jammed",
    "Component not responding",
    "Physical damage",
    "Printing issue",
    "Reading issue",
    "Other",
]

col_component, col_reason = st.columns(2)
with col_component:
    selected_component = st.selectbox("Component to Replace *", component_options)
with col_reason:
    selected_reason = st.selectbox("Replacement Reason", reason_options)

other_component = ""
if selected_component == "Other":
    other_component = st.text_input("Component Name *")

other_reason = ""
if selected_reason == "Other":
    other_reason = st.text_input("Reason for Replacement *")

st.markdown("### 🏷️ OLD and NEW component labels")
st.caption("Upload both labels. The complete serial numbers will be extracted automatically and can still be edited.")

old_col, new_col = st.columns(2)

with old_col:
    st.markdown("#### OLD COMPONENT")
    old_photo = st.file_uploader(
        "Upload OLD label",
        type=["png", "jpg", "jpeg"],
        key=f"replacement_old_photo_{uploader_version}",
    )
    if old_photo is not None:
        old_bytes = old_photo.getvalue()
        old_hash = _hash_bytes(old_bytes)
        old_preview = _safe_open_image(old_bytes)
        if old_preview:
            st.image(old_preview, caption="OLD label", use_container_width=True)
        if client and old_hash and old_hash != st.session_state.replacement_last_old_hash:
            with st.spinner("Reading OLD label..."):
                extracted_old = extract_component_label(old_bytes)
                st.session_state.replacement_old_item = extracted_old["item"]
                st.session_state.replacement_old_pn = extracted_old["pn"]
                if extracted_old["sn"]:
                    st.session_state.replacement_old_sn = extracted_old["sn"]
                st.session_state.replacement_last_old_hash = old_hash
            st.success("OLD serial extracted!")
    st.text_input("OLD Serial Number *", key="replacement_old_sn")
    if st.session_state.replacement_old_item or st.session_state.replacement_old_pn:
        st.caption(
            f"Detected: {st.session_state.replacement_old_item or 'Item not identified'}"
            f" | P/N: {st.session_state.replacement_old_pn or 'N/A'}"
        )

with new_col:
    st.markdown("#### NEW COMPONENT")
    new_photo = st.file_uploader(
        "Upload NEW label",
        type=["png", "jpg", "jpeg"],
        key=f"replacement_new_photo_{uploader_version}",
    )
    if new_photo is not None:
        new_bytes = new_photo.getvalue()
        new_hash = _hash_bytes(new_bytes)
        new_preview = _safe_open_image(new_bytes)
        if new_preview:
            st.image(new_preview, caption="NEW label", use_container_width=True)
        if client and new_hash and new_hash != st.session_state.replacement_last_new_hash:
            with st.spinner("Reading NEW label..."):
                extracted_new = extract_component_label(new_bytes)
                st.session_state.replacement_new_item = extracted_new["item"]
                st.session_state.replacement_new_pn = extracted_new["pn"]
                if extracted_new["sn"]:
                    st.session_state.replacement_new_sn = extracted_new["sn"]
                st.session_state.replacement_last_new_hash = new_hash
            st.success("NEW serial extracted!")
    st.text_input("NEW Serial Number *", key="replacement_new_sn")
    if st.session_state.replacement_new_item or st.session_state.replacement_new_pn:
        st.caption(
            f"Detected: {st.session_state.replacement_new_item or 'Item not identified'}"
            f" | P/N: {st.session_state.replacement_new_pn or 'N/A'}"
        )

if (old_photo is not None or new_photo is not None) and not client:
    st.warning("OPENAI_API_KEY not set in secrets — label auto-extract disabled. Enter the serial numbers manually.")

swap_col, _ = st.columns([1, 2])
with swap_col:
    st.button("⇄ Swap OLD / NEW", on_click=swap_serials)

old_sn_clean = st.session_state.replacement_old_sn.strip()
new_sn_clean = st.session_state.replacement_new_sn.strip()
if old_sn_clean and new_sn_clean and old_sn_clean == new_sn_clean:
    st.error("OLD and NEW serial numbers must be different.")

st.divider()


# =====================
# ATTACHMENTS AND DETAILS
# =====================
st.subheader("📎 Attachments and Details")

component_list_attached = st.checkbox("Component list completed before replacement is attached", value=True)
old_photo_attached = st.checkbox("OLD component photo will be attached", value=old_photo is not None)
new_photo_attached = st.checkbox("NEW component photo will be attached", value=new_photo is not None)

additional_details = st.text_area(
    "📝 Additional Details (optional)",
    placeholder="Example: Burster No. 7 was jammed and failed operational testing.",
)


# =====================
# GENERATE REQUEST
# =====================
generate = st.button("✅ Generate Replacement Request", type="primary", use_container_width=True)

if generate:
    place_name = st.session_state.replacement_place_name.strip()
    rdl = _clean_rdl(st.session_state.replacement_rdl)
    old_sn = st.session_state.replacement_old_sn.strip()
    new_sn = st.session_state.replacement_new_sn.strip()
    component_name = _component_display(selected_component, other_component)

    missing_fields = []
    if not place_name:
        missing_fields.append("Retailer / Site Name")
    if not rdl:
        missing_fields.append("RDL")
    if selected_component == "Other" and not other_component.strip():
        missing_fields.append("Component Name")
    if selected_reason == "Other" and not other_reason.strip():
        missing_fields.append("Reason for Replacement")
    if not old_sn:
        missing_fields.append("OLD Serial Number")
    if not new_sn:
        missing_fields.append("NEW Serial Number")

    if missing_fields:
        st.error("Complete the required fields: " + ", ".join(missing_fields))
    elif old_sn == new_sn:
        st.error("OLD and NEW serial numbers must be different.")
    else:
        st.session_state.replacement_generated_text = build_request(
            place_name=place_name,
            address=st.session_state.replacement_address,
            rl=st.session_state.replacement_rl,
            rdl=rdl,
            sst_serial=st.session_state.replacement_sst_serial,
            component_name=component_name,
            old_sn=old_sn,
            new_sn=new_sn,
            reason_sentence=_replacement_reason_sentence(selected_reason, other_reason),
            details=additional_details,
            component_list_attached=component_list_attached,
            old_photo_attached=old_photo_attached,
            new_photo_attached=new_photo_attached,
        )


if st.session_state.replacement_generated_text:
    st.divider()
    st.subheader("📄 Generated REF Request")
    st.code(st.session_state.replacement_generated_text, language="text")

    copy_col, download_col = st.columns(2)
    with copy_col:
        copy_to_clipboard_button(st.session_state.replacement_generated_text)
    with download_col:
        rdl_file = _clean_rdl(st.session_state.replacement_rdl) or "new"
        st.download_button(
            "⬇️ Download Request (.txt)",
            data=st.session_state.replacement_generated_text,
            file_name=f"component_replacement_RDL_{rdl_file}.txt",
            mime="text/plain",
            use_container_width=True,
        )

st.divider()
st.button("🗑️ Clear Form", on_click=clear_page)
