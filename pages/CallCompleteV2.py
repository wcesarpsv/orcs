import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="PM SST – Guided Scanner", layout="centered")
st.title("🧾 PM SST – Guided Component Scan")
st.caption("Follow the exact sequence shown inside the machine")
st.divider()

# =====================
# SEQUÊNCIA OFICIAL (IGUAL À FOTO)
# =====================
PM_SEQUENCE = [
    "Burster 1",
    "Burster 2",
    "Burster 3",
    "Burster 4",
    "Burster 5",
    "Burster 6",
    "Burster 7",
    "Scanner",
    "Printer",
    "Slip Reader",
    "LCD",
    "Keypad",
    "Enclosure",
    "Router",
    "Pin Pad",
]

TOTAL_STEPS = len(PM_SEQUENCE)

# =====================
# SESSION STATE
# =====================
if "pm_step" not in st.session_state:
    st.session_state.pm_step = 0

if "pm_data" not in st.session_state:
    st.session_state.pm_data = {
        comp: {"Serial": "", "Barcode": ""}
        for comp in PM_SEQUENCE
    }

# =====================
# CAMERA SCANNER
# =====================
def camera_scanner(target_key):
    components.html(
        f"""
        <div id="reader" style="width:300px"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
        const scanner = new Html5Qrcode("reader");
        scanner.start(
            {{ facingMode: "environment" }},
            {{ fps: 10, qrbox: 250 }},
            (decodedText) => {{
                const input = window.parent.document.querySelector(
                    'input[data-testid="stTextInput"][aria-label="Barcode"]'
                );
                if (input) {{
                    input.value = decodedText;
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                scanner.stop();
            }}
        );
        </script>
        """,
        height=350
    )

# =====================
# UI – PASSO ATUAL
# =====================
step = st.session_state.pm_step

if step < TOTAL_STEPS:
    component = PM_SEQUENCE[step]

    st.subheader(f"Step {step + 1} / {TOTAL_STEPS}")
    st.markdown(f"### 🔹 {component}")

    serial = st.text_input(
        "Serial Number",
        value=st.session_state.pm_data[component]["Serial"]
    )

    barcode = st.text_input(
        "Barcode",
        value=st.session_state.pm_data[component]["Barcode"]
    )

    with st.expander("📷 Scan barcode with camera"):
        camera_scanner(component)

    col1, col2 = st.columns(2)

    with col1:
        if st.checkbox("Use Barcode as Serial Number"):
            serial = barcode

    with col2:
        if st.button("✅ Save & Next"):
            if not barcode.strip():
                st.warning("Please scan the barcode before continuing.")
            else:
                st.session_state.pm_data[component]["Serial"] = serial
                st.session_state.pm_data[component]["Barcode"] = barcode
                st.session_state.pm_step += 1
                st.rerun()

else:
    # =====================
    # FINALIZAÇÃO
    # =====================
    st.success("✅ PM Component Scan Completed")

    df = pd.DataFrame([
        {
            "Component": comp,
            "Serial Number": data["Serial"],
            "Barcode": data["Barcode"]
        }
        for comp, data in st.session_state.pm_data.items()
    ])

    st.subheader("📊 Collected Components")
    st.dataframe(df, use_container_width=True)

    # Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SST Components")

    st.download_button(
        "⬇️ Download Excel (.xlsx)",
        output.getvalue(),
        file_name="PM_SST_Components.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Labels
    st.subheader("🏷️ Labels (Print & Attach)")
    labels = []
    for _, r in df.iterrows():
        labels.append(
            f"COMPONENT: {r['Component']}\n"
            f"SN: {r['Serial Number']}\n"
            f"BARCODE: {r['Barcode']}"
        )
    st.code("\n\n---\n\n".join(labels))

    # Component List (igual à foto)
    st.subheader("📌 Component List (Inside SST)")
    summary = ["COMPONENT LIST"]
    for _, r in df.iterrows():
        summary.append(f"{r['Component']} – {r['Serial Number']}")
    st.code("\n".join(summary))

    if st.button("🔁 Start New PM"):
        st.session_state.pm_step = 0
        st.session_state.pm_data = {
            comp: {"Serial": "", "Barcode": ""}
            for comp in PM_SEQUENCE
        }
        st.rerun()
