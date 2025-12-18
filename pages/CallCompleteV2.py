import streamlit as st
import pandas as pd
from io import BytesIO

# QR / Barcode Scanner
from streamlit_qrcode_scanner import qrcode_scanner

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="PM SST – Guided Scan", layout="centered")
st.title("🧾 PM SST – Guided Component Scan")
st.caption("Follow the exact component order shown inside the machine")
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
# UI – PASSO ATUAL
# =====================
step = st.session_state.pm_step

if step < TOTAL_STEPS:
    component = PM_SEQUENCE[step]

    st.subheader(f"Step {step + 1} / {TOTAL_STEPS}")
    st.markdown(f"### 🔹 {component}")

    # Campos
    serial = st.text_input(
        "Serial Number",
        value=st.session_state.pm_data[component]["Serial"],
        key=f"sn_{component}"
    )

    barcode = st.text_input(
        "Barcode",
        value=st.session_state.pm_data[component]["Barcode"],
        key=f"bc_{component}"
    )

    # =====================
    # SCANNER (CÂMERA)
    # =====================
    st.markdown("### 📷 Scan barcode with camera")

    scanned_code = qrcode_scanner(
        key=f"scanner_{component}",
        placeholder="Point the camera at the barcode"
    )

    if scanned_code:
        st.session_state.pm_data[component]["Barcode"] = scanned_code
        st.session_state.pm_data[component]["Serial"] = scanned_code
        st.success(f"Scanned: {scanned_code}")

    col1, col2 = st.columns(2)

    with col1:
        if st.checkbox("Use Barcode as Serial Number", key=f"use_bc_{component}"):
            st.session_state.pm_data[component]["Serial"] = st.session_state.pm_data[component]["Barcode"]

    with col2:
        if st.button("✅ Save & Next"):
            if not st.session_state.pm_data[component]["Barcode"].strip():
                st.warning("Please scan the barcode before continuing.")
            else:
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

    # =====================
    # EXCEL
    # =====================
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SST Components")

    st.download_button(
        "⬇️ Download Excel (.xlsx)",
        output.getvalue(),
        file_name="PM_SST_Components.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # =====================
    # LABELS
    # =====================
    st.subheader("🏷️ Labels (Print & Attach)")
    labels = []
    for _, r in df.iterrows():
        labels.append(
            f"COMPONENT: {r['Component']}\n"
            f"SN: {r['Serial Number']}\n"
            f"BARCODE: {r['Barcode']}"
        )
    st.code("\n\n---\n\n".join(labels))

    # =====================
    # COMPONENT LIST (IGUAL À FOTO)
    # =====================
    st.subheader("📌 Component List (Inside SST)")
    summary = ["COMPONENT LIST"]
    for _, r in df.iterrows():
        summary.append(f"{r['Component']} – {r['Serial Number']}")
    st.code("\n".join(summary))

    # =====================
    # RESET
    # =====================
    if st.button("🔁 Start New PM"):
        st.session_state.pm_step = 0
        st.session_state.pm_data = {
            comp: {"Serial": "", "Barcode": ""}
            for comp in PM_SEQUENCE
        }
        st.rerun()
