import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO

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
# CAMERA SCANNER (FUNCIONAL)
# =====================
def camera_scanner():
    components.html(
        """
        <div style="display:flex;flex-direction:column;align-items:center;">
            <button id="startBtn"
                style="
                    margin-bottom:10px;
                    padding:10px 16px;
                    background:#16a34a;
                    color:white;
                    border:none;
                    border-radius:6px;
                    font-size:15px;
                    cursor:pointer;
                ">
                📷 Start Camera
            </button>

            <div id="reader" style="width:300px;"></div>
        </div>

        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
        const readerId = "reader";
        const html5QrCode = new Html5Qrcode(readerId);

        document.getElementById("startBtn").addEventListener("click", async () => {
            try {
                await html5QrCode.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: 250 },
                    (decodedText) => {
                        const input = window.parent.document.querySelector(
                            'input[data-testid="stTextInput"][aria-label="Barcode"]'
                        );
                        if (input) {
                            input.value = decodedText;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        html5QrCode.stop();
                        alert("Barcode scanned successfully!");
                    }
                );
            } catch (err) {
                alert("Camera error: " + err);
            }
        });
        </script>
        """,
        height=380,
        scrolling=False,
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
        value=st.session_state.pm_data[component]["Serial"],
        key=f"sn_{component}"
    )

    barcode = st.text_input(
        "Barcode",
        value=st.session_state.pm_data[component]["Barcode"],
        key=f"bc_{component}"
    )

    with st.expander("📷 Scan barcode with camera"):
        camera_scanner()

    col1, col2 = st.columns(2)

    with col1:
        if st.checkbox("Use Barcode as Serial Number", key=f"use_bc_{component}"):
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
