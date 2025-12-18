import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO
from openai import OpenAI

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="WJS Service Report Generator", layout="wide")
st.title("🛠️ WJS Service Report Generator")
st.caption("Hybrid layout + PM Inventory + AI (optional)")
st.divider()

# =====================
# OPENAI SAFE CLIENT
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
# AI – POLISH DETAILS ONLY
# =====================
def polish_details_ai(text):
    if not client or not text.strip():
        return text.strip()
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the technician notes into a concise, professional service report details section. "
                        "Do not add assumptions or new steps. Keep all facts."
                    )
                },
                {"role": "user", "content": text}
            ],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return text.strip()

# =====================
# COPY BUTTON
# =====================
def copy_to_clipboard_button(text):
    safe_text = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )

    components.html(
        f"""
        <textarea id="clipboard-text" style="position:absolute; left:-9999px;">{safe_text}</textarea>
        <button onclick="copyText()"
            style="background:#2563eb;color:white;border:none;
                   padding:10px 16px;border-radius:6px;cursor:pointer;">
            📋 Copy to clipboard
        </button>
        <script>
        function copyText() {{
            navigator.clipboard.writeText(
                document.getElementById("clipboard-text").value
            ).then(() => alert("Copied to clipboard!"));
        }}
        </script>
        """,
        height=60
    )

# =====================
# PM DEFAULT COMPONENTS
# =====================
PM_COMPONENTS = [
    "Burster 1", "Burster 2", "Burster 3", "Burster 4",
    "Burster 5", "Burster 6", "Burster 7",
    "Scanner", "Printer", "Slip Reader",
    "LCD", "Keypad", "Enclosure", "Router", "Pin Pad"
]

# =====================
# FORM
# =====================
with st.form("main_form"):
    report_type = st.selectbox("📄 Report Type", ["PM", "INSTALLATION", "DEINSTALLATION"])
    use_ai = st.checkbox("🤖 Use AI to polish DETAILS section", value=True)

    colA, colB = st.columns(2)
    with colA:
        local = st.text_input("📍 Place Name")
    with colB:
        reference = st.text_input("🔢 Reference (RDL / RL)")

    descricao = st.text_area(
        "📝 Details (facts only)",
        placeholder="Issues, actions taken, delays, confirmations..."
    )

    # =====================
    # PM INVENTORY SECTION
    # =====================
    pm_df = None

    if report_type == "PM":
        st.subheader("🧾 PM – SST Component Inventory")

        component_rows = []
        for comp in PM_COMPONENTS:
            with st.expander(comp):
                sn = st.text_input(f"{comp} – Serial Number", key=f"{comp}_sn")
                bc = st.text_input(f"{comp} – Barcode", key=f"{comp}_bc")
                component_rows.append({
                    "Component": comp,
                    "Serial Number": sn,
                    "Barcode": bc
                })

        pm_df = pd.DataFrame(component_rows)

        st.subheader("📊 Collected Components")
        st.dataframe(pm_df, use_container_width=True)

    submitted = st.form_submit_button("✅ Generate Report")

# =====================
# GENERATION
# =====================
if submitted:

    details_final = polish_details_ai(descricao) if use_ai else descricao

    # ---------- PM EXTRAS ----------
    excel_bytes = None
    labels_text = ""
    component_summary = ""

    if report_type == "PM" and pm_df is not None:
        # Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pm_df.to_excel(writer, index=False, sheet_name="SST Components")
        excel_bytes = output.getvalue()

        # Labels
        labels = []
        for _, r in pm_df.iterrows():
            if r["Serial Number"] or r["Barcode"]:
                labels.append(
                    f"COMPONENT: {r['Component']}\n"
                    f"SN: {r['Serial Number']}\n"
                    f"BARCODE: {r['Barcode']}"
                )
        labels_text = "\n\n---\n\n".join(labels)

        # Summary (inside machine)
        lines = ["COMPONENT LIST"]
        for _, r in pm_df.iterrows():
            if r["Serial Number"]:
                lines.append(f"{r['Component']} – {r['Serial Number']}")
        component_summary = "\n".join(lines)

    # ---------- FINAL TEXT ----------
    if report_type == "PM":
        texto_final = f"""
PM completed at {local} ({reference})

Burster bins, rollers, and all related peripherals were cleaned.
Serial numbers and barcodes for all SST components were collected and recorded.
All hardware components were tested and verified as operational.
Keys were returned to the retailer upon completion.

All components were labeled inside the machine for future inspections.
""".strip()

    elif report_type == "INSTALLATION":
        texto_final = f"""
WJS Large Carmanah - {reference} Installation Summary

Upon arrival at the site, the retailer indicated the preferred installation location and height.

{details_final}

After completion, the equipment was tested and verified as operational.
""".strip()

    else:
        texto_final = f"""
WJS Sign Deinstallation Summary – {reference}

Upon arrival at the site, the retailer indicated the sign to be removed.

{details_final}

The equipment is being returned to the warehouse.
""".strip()

    # =====================
    # OUTPUT
    # =====================
    st.divider()
    st.subheader("📄 Final Report")
    st.code(texto_final)

    col1, col2 = st.columns(2)
    with col1:
        copy_to_clipboard_button(texto_final)
    with col2:
        st.download_button(
            "⬇️ Download Report (.txt)",
            texto_final,
            file_name=f"{report_type.lower()}_report.txt"
        )

    # ---------- PM OUTPUTS ----------
    if report_type == "PM":
        st.divider()
        st.subheader("📎 PM Attachments")

        st.download_button(
            "⬇️ Download SST Components Excel",
            excel_bytes,
            file_name="PM_SST_Components.xlsx"
        )

        st.subheader("🏷️ Labels (Print & Attach)")
        st.code(labels_text)

        st.subheader("📌 Component List (Inside Machine)")
        st.code(component_summary)
