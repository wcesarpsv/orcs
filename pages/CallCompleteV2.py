import streamlit as st
import pandas as pd
from io import BytesIO
from streamlit_qrcode_scanner import qrcode_scanner

# =====================
# CONFIG
# =====================
st.set_page_config(page_title="PM SST – Guided Scan", layout="centered")
st.title("🧾 PM SST – Guided Component Scan")
st.caption("Follow the exact component order shown inside the machine")
st.divider()

# =====================
# SEQUÊNCIA OFICIAL
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
# SESSION STATE INIT
# =====================
if "pm_step" not in st.session_state:
    st.session_state.pm_step = 0

if "pm_data" not in st.session_state:
    st.session_state.pm_data = {
        comp: {"Serial": "", "Barcode": ""}
        for comp in PM_SEQUENCE
    }

if "pm_scanned" not in st.session_state:
    st.session_state.pm_scanned = {
        comp: False for comp in PM_SEQUENCE
    }

# 🔑 BUFFER GLOBAL DO SCANNER
if "scanner_buffer" not in st.session_state:
    st.session_state.scanner_buffer = None

# =====================
# PASSO ATUAL
# =====================
step = st.session_state.pm_step

if step < TOTAL_STEPS:
    component = PM_SEQUENCE[step]
    
    # 🔥 LIMPA O BUFFER SEMPRE QUE MUDAR DE COMPONENTE
    if "last_component" not in st.session_state:
        st.session_state.last_component = component
    
    if st.session_state.last_component != component:
        st.session_state.scanner_buffer = None
        st.session_state.last_component = component

    st.subheader(f"Step {step + 1} / {TOTAL_STEPS}")
    st.markdown(f"## 🔒 CURRENT COMPONENT: **{component}**")

    # Campos (somente leitura após scan)
    st.text_input(
        "Serial Number",
        value=st.session_state.pm_data[component]["Serial"],
        disabled=True,
        key=f"serial_{component}"
    )

    st.text_input(
        "Barcode",
        value=st.session_state.pm_data[component]["Barcode"],
        disabled=True,
        key=f"barcode_{component}"
    )

    # =====================
    # SCANNER (sempre ativo, mas controlado por buffer)
    # =====================
    st.markdown("### 📷 Scan barcode with camera")

    # 🔥 Use uma chave única para cada componente
    scanned = qrcode_scanner(key=f"scanner_{component}")

    # Se scanner retornou algo novo → guarda no buffer
    if scanned and scanned != st.session_state.scanner_buffer:
        st.session_state.scanner_buffer = scanned
        st.rerun()  # Atualiza imediatamente

    # =====================
    # CONSUME UMA ÚNICA VEZ
    # =====================
    if (
        st.session_state.scanner_buffer
        and not st.session_state.pm_scanned[component]
    ):
        code = st.session_state.scanner_buffer

        if len(code) < 6:
            st.error("Invalid barcode. Please rescan.")
            st.session_state.scanner_buffer = None
        else:
            # Grava SOMENTE no componente atual
            st.session_state.pm_data[component]["Barcode"] = code
            st.session_state.pm_data[component]["Serial"] = code
            st.session_state.pm_scanned[component] = True

            # 🔥 LIMPA O BUFFER (CHAVE DO PROBLEMA)
            st.session_state.scanner_buffer = None

            st.success(f"✅ {component} scanned: {code}")

            # Aguarda um pouco para mostrar o sucesso
            st.balloons()
            
            # AUTO-ADVANCE com pequeno delay
            import time
            time.sleep(0.5)
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
    # COMPONENT LIST
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
        # Limpa TODOS os estados
        keys_to_clear = ["pm_step", "pm_data", "pm_scanned", "scanner_buffer", "last_component"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
