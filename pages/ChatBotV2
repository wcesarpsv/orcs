import streamlit as st
import os
import json
import fitz  # PyMuPDF
import re
import time

# LangChain
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# OpenAI
from openai import OpenAI


# ================= CONFIG =================
st.set_page_config(page_title="Procedures Assistant", layout="wide")

DOC_DIR = "documents"
CONFIG_PATH = "config/image_maps.json"
IMAGE_WIDTH = 450

# Load secrets
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("OpenAI API Key missing. Please check your secrets.")
    st.stop()


# ================= LOAD CONFIG =================
@st.cache_data
def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading config: {e}")
            return {"step_image_map": {}, "image_query_map": []}
    return {"step_image_map": {}, "image_query_map": []}

config = load_config()
STEP_IMAGE_MAP = config.get("step_image_map", {})
IMAGE_QUERY_MAP = config.get("image_query_map", [])


# ================= EXTRACT SERIAL NUMBERS FROM TEXT =================
def extract_serial_numbers(text):
    """Extrai números de série únicos do texto"""
    serials = set()
    
    # Padrão para pkey
    pkey_pattern = r'"pkey"\s*:\s*"([A-Z0-9]+)"'
    pkey_matches = re.findall(pkey_pattern, text)
    for match in pkey_matches:
        if match and len(match) > 10:
            serials.add(match)
    
    return list(serials)


# ================= EXTRACT COMPONENTS WITH SERIALS =================
def extract_components_with_serials(text):
    """Extrai componentes e seus respectivos números de série"""
    components = []
    
    # Dividir por linhas
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Procurar padrão: Componente – {json}
        component_match = re.match(r'^([A-Za-z\s]+\s*\d*)\s*[–\-:]\s*(.+)$', line)
        if component_match:
            component_name = component_match.group(1).strip()
            json_part = component_match.group(2).strip()
            
            # Extrair pkey do JSON
            pkey_match = re.search(r'"pkey"\s*:\s*"([^"]+)"', json_part)
            if pkey_match:
                serial = pkey_match.group(1)
                components.append({
                    "component": component_name,
                    "serial": serial,
                    "json_data": json_part,
                    "scanned": False  # Flag para controlar se já foi escaneado
                })
    
    return components


# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    if not os.path.exists(DOC_DIR):
        return None

    docs = []
    all_components = []  # Armazenar todos os componentes

    for root, _, files in os.walk(DOC_DIR):
        for file in files:
            path = os.path.join(root, file)
            text = ""

            # PDF
            if file.lower().endswith(".pdf"):
                try:
                    with fitz.open(path) as pdf:
                        text = "\n".join(page.get_text() for page in pdf)
                except Exception:
                    text = ""

            # Markdown / TXT
            elif file.lower().endswith((".md", ".txt")):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    text = ""
            else:
                continue

            if text.strip():
                # Extrair componentes com seus seriais
                doc_components = extract_components_with_serials(text)
                all_components.extend(doc_components)
                
                # Adicionar metadados com componentes
                metadata = {
                    "source": os.path.relpath(path, DOC_DIR),
                    "components": doc_components if doc_components else []
                }
                
                docs.append(
                    Document(
                        page_content=text,
                        metadata=metadata
                    )
                )

    if not docs:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )
    chunks = splitter.split_documents(docs)

    # Preservar metadados nos chunks
    for chunk in chunks:
        if "components" not in chunk.metadata:
            chunk.metadata["components"] = []

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Armazenar dados na sessão
    st.session_state.all_components = all_components
    
    return FAISS.from_documents(chunks, embeddings)


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("Refresh Knowledge Base"):
        st.cache_resource.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📚 Guide")
    st.markdown(
        """
        **Serial Scanning Mode:**
        1. Click 'Start Serial Scan'
        2. Scan first component's barcode
        3. Click 'Next' to move to next component
        4. Repeat for all components
        5. Click 'Finish' when done
        """
    )
    
    # Inicializar estado de varredura
    if 'scan_mode' not in st.session_state:
        st.session_state.scan_mode = False
    if 'current_scan_index' not in st.session_state:
        st.session_state.current_scan_index = 0
    if 'scanned_components' not in st.session_state:
        st.session_state.scanned_components = []
    if 'expected_components' not in st.session_state:
        st.session_state.expected_components = []
    
    # Botão para iniciar modo de varredura
    if not st.session_state.scan_mode:
        if st.button("🚀 Start Serial Scan", type="primary", use_container_width=True):
            st.session_state.scan_mode = True
            st.session_state.current_scan_index = 0
            st.session_state.scanned_components = []
            st.rerun()
    else:
        if st.button("🛑 Finish Scanning", type="secondary", use_container_width=True):
            st.session_state.scan_mode = False
            st.rerun()
    
    st.markdown("---")
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# ================= INIT APP =================
st.title("🛠️ Work Procedures Assistant")

# Inicializar mensagens
if "messages" not in st.session_state:
    st.session_state.messages = []

# Load DB
db = load_vector_db()

if db is None:
    st.warning(f"⚠️ No documents found in `{DOC_DIR}`. Please add files to start.")
else:
    # ================= DISPLAY CHAT HISTORY =================
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "images" in message:
                for img_path in message["images"]:
                    if os.path.exists(img_path):
                        st.image(img_path, width=IMAGE_WIDTH)

    # ================= SERIAL SCANNING MODE =================
    if st.session_state.scan_mode:
        st.markdown("---")
        st.header("🔍 Serial Scanning Mode")
        
        # Primeira vez: obter lista de componentes esperados
        if not st.session_state.expected_components:
            with st.spinner("Loading component list..."):
                # Buscar no banco de dados
                results = db.similarity_search("component list serial numbers", k=2)
                all_components = []
                for doc in results:
                    if "components" in doc.metadata:
                        all_components.extend(doc.metadata["components"])
                
                if all_components:
                    # Remover duplicatas
                    seen = set()
                    unique_components = []
                    for comp in all_components:
                        if comp["component"] not in seen:
                            seen.add(comp["component"])
                            unique_components.append(comp)
                    
                    st.session_state.expected_components = unique_components
                    st.success(f"Found {len(unique_components)} components to scan")
        
        # Mostrar progresso
        if st.session_state.expected_components:
            total = len(st.session_state.expected_components)
            current = st.session_state.current_scan_index + 1
            
            # Barra de progresso
            progress = current / total if total > 0 else 0
            st.progress(progress, text=f"Component {current} of {total}")
            
            # Componente atual
            current_component = st.session_state.expected_components[
                min(st.session_state.current_scan_index, len(st.session_state.expected_components) - 1)
            ]
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"🔧 {current_component['component']}")
                st.info(f"**Expected Serial:** `{current_component['serial']}`")
            
            with col2:
                st.metric("Status", f"{current}/{total}")
            
            # Área para escanear o código de barras
            st.markdown("---")
            st.subheader("📷 Scan Barcode")
            
            # Input para o serial escaneado
            scanned_serial = st.text_input(
                f"Scan barcode for {current_component['component']}:",
                key=f"scan_input_{st.session_state.current_scan_index}",
                placeholder="Scan barcode or enter serial manually..."
            )
            
            # Botões de controle
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("⏮️ Previous", disabled=st.session_state.current_scan_index == 0):
                    st.session_state.current_scan_index = max(0, st.session_state.current_scan_index - 1)
                    st.rerun()
            
            with col2:
                if scanned_serial:
                    # Verificar se o serial escaneado corresponde ao esperado
                    if scanned_serial == current_component['serial']:
                        st.success("✅ Serial matches!")
                    else:
                        st.warning(f"⚠️ Serial mismatch. Expected: {current_component['serial']}")
                
                if st.button("✅ Confirm & Next", type="primary", disabled=not scanned_serial):
                    # Registrar o componente escaneado
                    scanned_data = {
                        "component": current_component['component'],
                        "expected_serial": current_component['serial'],
                        "scanned_serial": scanned_serial,
                        "timestamp": time.time(),
                        "match": scanned_serial == current_component['serial']
                    }
                    st.session_state.scanned_components.append(scanned_data)
                    
                    # Mover para o próximo componente
                    if st.session_state.current_scan_index < len(st.session_state.expected_components) - 1:
                        st.session_state.current_scan_index += 1
                        st.rerun()
                    else:
                        # Último componente escaneado
                        st.session_state.scan_mode = False
                        st.success("🎉 All components scanned!")
                        st.rerun()
            
            with col3:
                if st.button("⏭️ Skip", type="secondary"):
                    if st.session_state.current_scan_index < len(st.session_state.expected_components) - 1:
                        st.session_state.current_scan_index += 1
                        st.rerun()
            
            # Mostrar histórico de componentes escaneados
            if st.session_state.scanned_components:
                st.markdown("---")
                st.subheader("📋 Scan History")
                
                for i, scan in enumerate(st.session_state.scanned_components):
                    status = "✅" if scan['match'] else "❌"
                    col1, col2, col3 = st.columns([2, 3, 1])
                    with col1:
                        st.write(f"{i+1}. {scan['component']}")
                    with col2:
                        if scan['match']:
                            st.success(f"Scanned: `{scan['scanned_serial']}`")
                        else:
                            st.error(f"Scanned: `{scan['scanned_serial']}` (Expected: `{scan['expected_serial']}`)")
                    with col3:
                        st.write(status)
        
        else:
            st.warning("No components found in documents. Please check your documentation.")
            if st.button("Exit Scan Mode"):
                st.session_state.scan_mode = False
                st.rerun()
    
    # ================= CHAT INPUT (Normal Mode) =================
    else:
        # Mostrar resumo se houve varredura
        if st.session_state.scanned_components:
            with st.expander("📊 Scan Summary", expanded=True):
                total = len(st.session_state.scanned_components)
                matches = sum(1 for s in st.session_state.scanned_components if s['match'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Scanned", total)
                with col2:
                    st.metric("Matches", f"{matches}/{total}")
                
                if st.button("Generate Scan Report"):
                    # Gerar relatório
                    report_lines = ["# Serial Scan Report", ""]
                    for scan in st.session_state.scanned_components:
                        status = "MATCH" if scan['match'] else "MISMATCH"
                        report_lines.append(f"## {scan['component']}")
                        report_lines.append(f"- Expected: `{scan['expected_serial']}`")
                        report_lines.append(f"- Scanned: `{scan['scanned_serial']}`")
                        report_lines.append(f"- Status: **{status}**")
                        report_lines.append("")
                    
                    report_text = "\n".join(report_lines)
                    st.download_button(
                        label="📥 Download Report",
                        data=report_text,
                        file_name=f"serial_scan_report_{time.strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
        
        # Chat normal
        if prompt := st.chat_input("Ask a question about procedures..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Process standard queries
            q = prompt.lower()
            response_images = []
            response_content = ""

            # Check for direct image requests
            direct_image_found = False
            for item in IMAGE_QUERY_MAP:
                if any(k in q for k in item["keywords"]):
                    response_content = f"### 🖼️ {item['title']}\nHere is the image you requested."
                    response_images = item["images"]
                    direct_image_found = True
                    break
            
            if not direct_image_found:
                # RAG Search
                results = db.similarity_search(prompt, k=3)
                context = "\n\n".join(doc.page_content for doc in results)

                # Build conversation history for context
                history_context = "\n".join(
                    [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]]
                )

                # Generate response
                llm_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a work procedures assistant. "
                                "Answer ONLY using the provided documentation. "
                                "Always answer step-by-step when applicable. "
                                "If the user asks for a photo, say: 'See the image below.' "
                                "If the answer is not in the documents, say exactly: "
                                "'This situation is not documented yet.'"
                            )
                        },
                        {
                            "role": "user",
                            "content": f"History:\n{history_context}\n\nDocumentation:\n{context}\n\nQuestion: {prompt}"
                        }
                    ]
                )
                
                response_content = llm_response.choices[0].message.content

                # Parse for Step Images
                lines = response_content.split("\n")
                current_step = None
                
                for line in lines:
                    if line.strip() and line.lstrip()[0].isdigit():
                        try:
                            current_step = str(line.split(".")[0]) 
                        except:
                            pass
                    
                    if current_step:
                        # Check all sources in results to see if they match mapped images
                        for doc in results:
                            src = doc.metadata.get("source")
                            if src in STEP_IMAGE_MAP and current_step in STEP_IMAGE_MAP[src]:
                                imgs = STEP_IMAGE_MAP[src][current_step]
                                for img in imgs:
                                    if img not in response_images:
                                        response_images.append(img)

            # Display Assistant Response
            with st.chat_message("assistant"):
                st.markdown(response_content)
                for img in response_images:
                    if os.path.exists(img):
                        st.image(img, width=IMAGE_WIDTH)
                    else:
                        st.warning(f"Image not found: {img}")

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_content,
                "images": response_images
            })
