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
# SEQUÊNCIA OFICIAL (15 componentes)
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
        comp: {"Serial": "", "Barcode": "", "Status": "PENDING"}
        for comp in PM_SEQUENCE
    }

if "pm_scanned" not in st.session_state:
    st.session_state.pm_scanned = {
        comp: False for comp in PM_SEQUENCE
    }

# 🔑 BUFFER GLOBAL DO SCANNER
if "scanner_buffer" not in st.session_state:
    st.session_state.scanner_buffer = None

# 🔑 LISTA DE CÓDIGOS JÁ ESCANEADOS (para evitar duplicação)
if "scanned_codes" not in st.session_state:
    st.session_state.scanned_codes = []

# =====================
# PASSO ATUAL
# =====================
step = st.session_state.pm_step

if step < TOTAL_STEPS:
    component = PM_SEQUENCE[step]
    
    # 🔥 VERIFICA SE O COMPONENTE ATUAL JÁ FOI ESCANEADO
    if st.session_state.pm_scanned[component]:
        st.warning(f"⚠️ {component} already scanned! Moving to next component...")
        import time
        time.sleep(1)
        st.session_state.pm_step += 1
        st.rerun()

    st.subheader(f"Step {step + 1} / {TOTAL_STEPS}")
    st.markdown(f"## 🔒 CURRENT COMPONENT: **{component}**")
    
    # Mostra progresso
    progress = step / TOTAL_STEPS
    st.progress(progress)

    # Campos (somente leitura após scan)
    col1, col2 = st.columns(2)
    
    with col1:
        st.text_input(
            "Serial Number",
            value=st.session_state.pm_data[component]["Serial"],
            disabled=True,
            key=f"serial_{component}"
        )
    
    with col2:
        st.text_input(
            "Barcode",
            value=st.session_state.pm_data[component]["Barcode"],
            disabled=True,
            key=f"barcode_{component}"
        )

    # =====================
    # VISUALIZAÇÃO DOS ESCANEADOS
    # =====================
    with st.expander("📋 Scanned Components (Click to View)"):
        scanned_list = []
        for i, comp in enumerate(PM_SEQUENCE):
            if i < step:
                status = "✅"
                code = st.session_state.pm_data[comp]["Barcode"]
                scanned_list.append(f"{status} {comp}: {code}")
            elif i == step:
                scanned_list.append(f"🔜 {comp}: Waiting...")
            else:
                scanned_list.append(f"⏳ {comp}: Not scanned")
        
        for item in scanned_list:
            st.write(item)

    # =====================
    # SCANNER
    # =====================
    st.markdown("### 📷 Scan barcode with camera")
    st.info(f"Point camera at {component} barcode")

    # Scanner com chave única
    scanned = qrcode_scanner(key=f"scanner_{component}")

    # Processa o código escaneado
    if scanned and scanned != st.session_state.scanner_buffer:
        st.session_state.scanner_buffer = scanned
        
        # 🔥 VERIFICA SE O CÓDIGO JÁ FOI USADO
        if scanned in st.session_state.scanned_codes:
            st.error(f"❌ This barcode was already scanned for another component!")
            st.warning("Please scan a different barcode.")
            st.session_state.scanner_buffer = None
            st.rerun()
        
        # Validação do código
        if len(scanned) < 6:
            st.error("Invalid barcode (too short). Please rescan.")
            st.session_state.scanner_buffer = None
        else:
            # Grava os dados
            st.session_state.pm_data[component]["Barcode"] = scanned
            st.session_state.pm_data[component]["Serial"] = scanned
            st.session_state.pm_data[component]["Status"] = "SCANNED"
            st.session_state.pm_scanned[component] = True
            
            # Adiciona à lista de códigos escaneados (evita duplicação)
            st.session_state.scanned_codes.append(scanned)
            
            # Limpa o buffer
            st.session_state.scanner_buffer = None
            
            # Feedback
            st.success(f"✅ {component} scanned successfully!")
            st.balloons()
            
            # Mostra o código escaneado
            st.code(f"Barcode: {scanned}")
            
            # Auto-advance com delay
            import time
            time.sleep(1.5)
            st.session_state.pm_step += 1
            st.rerun()

    # =====================
    # CONTROLES MANUAIS
    # =====================
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("⏮️ Previous", disabled=(step == 0)):
            st.session_state.pm_step -= 1
            st.rerun()
    
    with col2:
        if st.button("🔄 Rescan Current", type="secondary"):
            # Permite reescanear o componente atual
            st.session_state.pm_data[component] = {"Serial": "", "Barcode": "", "Status": "PENDING"}
            st.session_state.pm_scanned[component] = False
            if component in st.session_state.scanned_codes:
                st.session_state.scanned_codes.remove(component)
            st.rerun()
    
    with col3:
        if st.button("⏭️ Skip Component", type="secondary"):
            st.warning(f"Skipping {component} - No barcode available")
            st.session_state.pm_data[component]["Status"] = "SKIPPED"
            st.session_state.pm_scanned[component] = True
            st.session_state.pm_step += 1
            st.rerun()

else:
    # =====================
    # FINALIZAÇÃO
    # =====================
    st.success("✅ PM Component Scan Completed!")
    st.balloons()
    
    # =====================
    # RELATÓRIO FINAL
    # =====================
    st.subheader("📊 Final Report - All Components")
    
    # Cria DataFrame
    report_data = []
    for comp in PM_SEQUENCE:
        data = st.session_state.pm_data[comp]
        report_data.append({
            "Component": comp,
            "Serial Number": data["Serial"] if data["Serial"] else "NOT SCANNED",
            "Barcode": data["Barcode"] if data["Barcode"] else "NOT SCANNED",
            "Status": data["Status"]
        })
    
    df = pd.DataFrame(report_data)
    
    # Mostra tabela colorida
    def color_status(val):
        if val == "SCANNED":
            return "background-color: #d4edda; color: #155724;"
        elif val == "SKIPPED":
            return "background-color: #fff3cd; color: #856404;"
        else:
            return "background-color: #f8d7da; color: #721c24;"
    
    styled_df = df.style.applymap(color_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # =====================
    # EXPORTAR PARA EXCEL
    # =====================
    st.divider()
    st.subheader("📥 Export to Excel")
    
    # Cria Excel com formatação
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Data completa
        df.to_excel(writer, sheet_name='PM_SST_Scan', index=False)
        
        # Sheet 2: Resumo
        summary_df = pd.DataFrame({
            'Summary': [
                f'Total Components: {TOTAL_STEPS}',
                f'Scanned: {len([x for x in df["Status"] if x == "SCANNED"])}',
                f'Skipped: {len([x for x in df["Status"] if x == "SKIPPED"])}',
                f'Pending: {len([x for x in df["Status"] if x == "PENDING"])}',
                f'Scan Date: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}'
            ]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Sheet 3: Lista para impressão
        labels_data = []
        for _, row in df.iterrows():
            labels_data.append(f"COMPONENT: {row['Component']}")
            labels_data.append(f"SERIAL: {row['Serial Number']}")
            labels_data.append(f"BARCODE: {row['Barcode']}")
            labels_data.append(f"STATUS: {row['Status']}")
            labels_data.append("---")
        
        labels_df = pd.DataFrame({"Labels": labels_data})
        labels_df.to_excel(writer, sheet_name='Print_Labels', index=False)
    
    excel_data = output.getvalue()
    
    # Botão de download
    st.download_button(
        label="⬇️ Download Excel Report (.xlsx)",
        data=excel_data,
        file_name=f"PM_SST_Scan_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Click to download complete report in Excel format"
    )
    
    # =====================
    # VISUALIZAÇÃO ADICIONAL
    # =====================
    st.divider()
    
    # Labels para impressão
    with st.expander("🏷️ Print Labels"):
        labels_text = ""
        for _, row in df.iterrows():
            if row['Status'] == 'SCANNED':
                labels_text += f"""
                COMPONENT: {row['Component']}
                SERIAL: {row['Serial Number']}
                BARCODE: {row['Barcode']}
                
                ====================
                
                """
        st.text_area("Labels for printing", labels_text, height=300)
    
    # Lista de componentes
    with st.expander("📋 Component List (for SST)"):
        component_list = "COMPONENT LIST - PM SST\n" + "="*30 + "\n"
        for _, row in df.iterrows():
            component_list += f"{row['Component']} – {row['Serial Number']}\n"
        st.text_area("Component List", component_list, height=200)
    
    # =====================
    # RESET
    # =====================
    st.divider()
    st.subheader("🔄 Start New Scan")
    
    if st.button("🔁 Start New PM Scan", type="primary"):
        # Limpa TODOS os estados
        keys_to_clear = [
            "pm_step", "pm_data", "pm_scanned", 
            "scanner_buffer", "scanned_codes"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.success("Ready for new scan!")
        st.rerun()
