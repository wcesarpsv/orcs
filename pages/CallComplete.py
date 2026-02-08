import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Report Generator", layout="centered")
st.title("🛠️ WJS Service Report Generator")
st.caption("Hybrid mode: fixed layout + optional AI polishing for details")
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
# AI: POLISH ONLY DETAILS
# =====================
def polish_details_ai(raw_details: str) -> str:
    """
    Rewrites the technician's detail text in a professional tone.
    Does NOT add assumptions or new steps.
    """
    if not client:
        return raw_details.strip()

    raw_details = (raw_details or "").strip()
    if not raw_details:
        return ""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the technician notes into a concise, professional service report details section. "
                        "Do not add assumptions, do not invent steps, do not add new facts. "
                        "Keep all facts present in the notes. Use clear sentences."
                    ),
                },
                {"role": "user", "content": raw_details},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # fallback if API fails
        return raw_details.strip()

# =====================
# COPY BUTTON
# =====================
def copy_to_clipboard_button(text: str):
    # Escape basic HTML entities to avoid breaking the textarea
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
            style="
                background-color:#2563eb;
                color:white;
                border:none;
                padding:10px 16px;
                border-radius:6px;
                font-size:14px;
                cursor:pointer;
            ">
            📋 Copy to clipboard
        </button>

        <script>
        function copyText() {{
            const el = document.getElementById("clipboard-text");
            const text = el.value;
            navigator.clipboard.writeText(text).then(() => {{
                alert("Report copied to clipboard!");
            }}).catch(() => {{
                alert("Could not copy automatically. Please select and copy manually.");
            }});
        }}
        </script>
        """,
        height=60,
    )

# =====================
# OFFLINE TEMPLATES (FIXED LAYOUT)
# =====================
def format_extras(itens_extras: list[str]) -> str:
    if not itens_extras:
        return ""
    lines = "\n".join([f"- {i}" for i in itens_extras])
    return f"Additional materials used:\n{lines}"

def template_pm(local: str, reference: str, extras_block: str) -> str:
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

def template_installation(reference: str, details: str, extras_block: str) -> str:
    # fixed header + fixed closing, variable details in the middle
    details = details.strip() if details else "No issues reported."
    base = f"""
WJS Large Carmanah - {local} ({reference}) - Installation Summary

Upon arrival at the site, the retailer indicated the preferred installation location and desired height for the sign.

{details}

After completion, I explained the work performed to the retailer and demonstrated that the equipment was operating correctly.
""".strip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

def template_deinstallation(reference: str, details: str, extras_block: str) -> str:
    details = details.strip() if details else "No issues reported."
    base = f"""
WJS Sign Deinstallation {local} ({reference}) - Summary 

Upon arrival at the site, the retailer indicated the sign to be removed.

{details}

The equipment is being returned to the warehouse.
""".strip()

    if extras_block:
        base += "\n\n" + extras_block
    return base

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
        st.warning("AI is ON, but OPENAI_API_KEY is not set in secrets. I will use your text as-is.")

    local = st.text_input("📍 Place Name", placeholder="Example: Gateway Newstand 434")
    reference = st.text_input("🔢 Reference Number (RDL / RL)", placeholder="Example: RDL 43741 / RL 601962")

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
    # Extras list
    itens_extras = []
    if cat5: itens_extras.append("CAT5 network cable")
    if extension: itens_extras.append("Power extension")
    if power_supply: itens_extras.append("Power supply")
    if transceiver: itens_extras.append("Transceiver")
    if router: itens_extras.append("Router")
    if mounting: itens_extras.append("Mounting hardware")
    if adapters: itens_extras.append("Adapters")

    if extras_custom.strip():
        itens_extras.extend([i.strip() for i in extras_custom.split("\n") if i.strip()])

    extras_block = format_extras(itens_extras)

    # Polishing only the details section (optional)
    details_final = descricao.strip()
    if use_ai and details_final:
        with st.spinner("Polishing details with AI..."):
            details_final = polish_details_ai(details_final)

    # Generate final text using fixed templates
    if report_type == "PM":
        texto_final = template_pm(local.strip(), reference.strip(), details_final, extras_block)
    elif report_type == "INSTALLATION":
        texto_final = template_installation(reference.strip(), details_final, extras_block)
    else:
        texto_final = template_deinstallation(reference.strip(), details_final, extras_block)

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
