import streamlit as st
from openai import OpenAI

# =====================
# CONFIG
# =====================
st.set_page_config(
    page_title="WJS Report Generator",
    layout="centered"
)

st.title("🛠️ WJS Service Report Generator")
st.caption("PM • Installation • Deinstallation")
st.divider()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =====================
# FUNÇÃO AI
# =====================
def gerar_texto_ai(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a field service technician writing concise, "
                    "professional service reports. Do not add assumptions."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

# =====================
# FORMULÁRIO
# =====================
with st.form("report_form"):

    report_type = st.selectbox(
        "📄 Report Type",
        ["PM", "INSTALLATION", "DEINSTALLATION"]
    )

    use_ai = st.checkbox("🤖 Use AI to generate report (recommended)", value=True)

    local = st.text_input("📍 Place Name")
    reference = st.text_input("🔢 Reference Number (RDL / RL)")

    descricao = st.text_area(
        "📝 What happened? (facts only)",
        placeholder="Example:\nIssues with transceiver and cable. Installation took 35 extra minutes."
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
        placeholder="Cable ties\nVelcro straps"
    )

    submitted = st.form_submit_button("✅ Generate Report")

# =====================
# PROCESSAMENTO
# =====================
if submitted:

    # Itens extras
    itens_extras = []
    if cat5: itens_extras.append("CAT5 network cable")
    if extension: itens_extras.append("Power extension")
    if power_supply: itens_extras.append("Power supply")
    if transceiver: itens_extras.append("Transceiver")
    if router: itens_extras.append("Router")
    if mounting: itens_extras.append("Mounting hardware")
    if adapters: itens_extras.append("Adapters")

    if extras_custom.strip():
        itens_extras.extend(
            [i.strip() for i in extras_custom.split("\n") if i.strip()]
        )

    extras_texto = "\n".join(f"- {i}" for i in itens_extras) if itens_extras else "None"

    # =====================
    # PROMPT AI
    # =====================
    prompt = f"""
Report type: {report_type}
Location: {local}
Reference: {reference}

Facts:
{descricao if descricao else "No issues reported."}

Additional materials used:
{extras_texto}

Write a concise, professional service report.
Do not add assumptions or steps not mentioned.
"""

    # =====================
    # TEMPLATE FIXO (FALLBACK)
    # =====================
    def gerar_template_fixo():
        if report_type == "PM":
            return f"""
PM completed at {local} ({reference})

Burster bins, rollers, and all related peripherals were cleaned.
Serial numbers for all components were recorded.
All hardware components were tested and verified as operational.
Keys were returned to the retailer upon completion.
""".strip()

        elif report_type == "INSTALLATION":
            return f"""
WJS Large Carmanah - {reference} Installation Summary

Upon arrival at the site, the retailer indicated the preferred installation location and height.
{descricao}

After completion, the equipment was tested and verified as operational.
""".strip()

        else:
            return f"""
WJS Sign Deinstallation Summary – {reference}

Upon arrival at the site, the retailer indicated the sign to be removed.
The deinstallation was completed successfully and all required photos were taken.
The equipment is being returned to the warehouse.
{descricao}
""".strip()

    # =====================
    # GERAÇÃO FINAL
    # =====================
    with st.spinner("Generating report..."):
        if use_ai:
            texto_final = gerar_texto_ai(prompt)
        else:
            texto_final = gerar_template_fixo()

    # =====================
    # OUTPUT
    # =====================
    st.divider()
    st.subheader("📄 Generated Report")
    st.code(texto_final, language="text")

    st.download_button(
        "⬇️ Download Report (.txt)",
        data=texto_final,
        file_name=f"{report_type.lower()}_report.txt",
        mime="text/plain"
    )
