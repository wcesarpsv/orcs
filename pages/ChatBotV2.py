import streamlit as st
import os
import json
import fitz  # PyMuPDF
import re

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
    # Padrões específicos para o formato mostrado
    serials = set()
    
    # Padrão 1: {"pkey":"251213132233356959381640204AZ"}
    pkey_pattern = r'"pkey"\s*:\s*"([A-Z0-9]+)"'
    pkey_matches = re.findall(pkey_pattern, text)
    for match in pkey_matches:
        if match and len(match) > 10:  # Verifica se tem comprimento razoável
            serials.add(match)
    
    # Padrão 2: lastNode":"DON9" (extrair DON9)
    node_pattern = r'"lastNode"\s*:\s*"([A-Z0-9]+)"'
    node_matches = re.findall(node_pattern, text)
    for match in node_matches:
        if match and match != "DON9":  # Filtra DON9 se for sempre o mesmo
            serials.add(match)
    
    # Padrão 3: Nome do componente + serial (ex: Burster 1 – {"lastNode":"DON9","cids":{"pkey":"251213132233356959381640204AZ"}})
    component_pattern = r'([A-Za-z\s]+)\s*\d*\s*[–\-:]\s*\{[^}]+\"pkey\"\s*:\s*\"([A-Z0-9]+)\"'
    comp_matches = re.findall(component_pattern, text)
    for comp_name, serial in comp_matches:
        if serial and len(serial) > 10:
            serials.add(f"{comp_name.strip()}: {serial}")
    
    # Padrão 4: Códigos longos alfanuméricos
    long_code_pattern = r'\b([A-Z0-9]{20,30})\b'
    long_matches = re.findall(long_code_pattern, text)
    for match in long_matches:
        # Verificar se não é um número comum
        if not match.isdigit() and not all(c == '0' for c in match):
            serials.add(match)
    
    # Padrão 5: Capturar todo o objeto JSON para análise posterior
    json_pattern = r'\{[^{}]*"pkey"[^{}]*\}'
    json_matches = re.findall(json_pattern, text)
    for json_str in json_matches:
        try:
            data = json.loads(json_str.replace("'", '"'))
            if "pkey" in str(data):  # Procura pkey em qualquer nível
                # Função recursiva para encontrar pkey
                def find_pkey(obj):
                    if isinstance(obj, dict):
                        if "pkey" in obj:
                            return obj["pkey"]
                        for value in obj.values():
                            result = find_pkey(value)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_pkey(item)
                            if result:
                                return result
                    return None
                
                pkey_value = find_pkey(data)
                if pkey_value:
                    serials.add(pkey_value)
        except:
            # Se não conseguir parsear como JSON, tenta extrair diretamente
            pkey_direct = re.search(r'"pkey"\s*:\s*"([^"]+)"', json_str)
            if pkey_direct:
                serials.add(pkey_direct.group(1))
    
    return list(serials)


# ================= EXTRACT COMPONENTS WITH SERIALS =================
def extract_components_with_serials(text):
    """Extrai componentes e seus respectivos números de série"""
    components = []
    
    # Dividir por linhas
    lines = text.split('\n')
    current_component = None
    
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
                    "full_json": json_part
                })
    
    return components


# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    if not os.path.exists(DOC_DIR):
        return None

    docs = []
    all_serials = []  # Armazenar todos os números de série encontrados
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
                # Extrair números de série deste documento
                doc_serials = extract_serial_numbers(text)
                all_serials.extend(doc_serials)
                
                # Extrair componentes com seus seriais
                doc_components = extract_components_with_serials(text)
                all_components.extend(doc_components)
                
                # Adicionar metadados com números de série e componentes
                metadata = {
                    "source": os.path.relpath(path, DOC_DIR),
                    "serials": doc_serials if doc_serials else [],
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
        if "serials" not in chunk.metadata:
            chunk.metadata["serials"] = []
        if "components" not in chunk.metadata:
            chunk.metadata["components"] = []

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Armazenar dados na sessão
    st.session_state.all_serials = list(set(all_serials))
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
        **How to use:**
        1. Ask a question about work procedures.
        2. If you need a photo, ask for it (e.g., "show me the serial number").
        3. Follow step-by-step instructions.
        """
    )
    
    # Mostrar números de série encontrados
    if 'all_serials' in st.session_state and st.session_state.all_serials:
        with st.expander("📋 Serial Numbers Found"):
            for i, serial in enumerate(st.session_state.all_serials[:10], 1):
                st.code(serial, language=None)
            if len(st.session_state.all_serials) > 10:
                st.write(f"... and {len(st.session_state.all_serials) - 10} more")
    
    # Mostrar componentes encontrados
    if 'all_components' in st.session_state and st.session_state.all_components:
        with st.expander("🔧 Components Found"):
            for comp in st.session_state.all_components[:10]:
                st.write(f"**{comp['component']}**: `{comp['serial']}`")
            if len(st.session_state.all_components) > 10:
                st.write(f"... and {len(st.session_state.all_components) - 10} more")
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# ================= INIT APP =================
st.title("🛠️ Work Procedures Assistant")

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
            if "components" in message:
                st.markdown("---")
                st.subheader("🔧 Components Identified")
                for comp in message["components"]:
                    col1, col2, col3 = st.columns([2, 3, 1])
                    with col1:
                        st.write(f"**{comp['component']}**")
                    with col2:
                        st.code(comp['serial'], language=None)
                    with col3:
                        if st.button("📋", key=f"copy_{comp['serial']}"):
                            st.write(f"Copied: {comp['serial']}")
                            # Lógica para copiar para área de transferência aqui

    # ================= CHAT INPUT =================
    if prompt := st.chat_input("Ask a question about procedures..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process standard queries
        q = prompt.lower()
        response_images = []
        response_content = ""
        response_components = []

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
            
            # Coletar componentes únicos de todos os resultados
            unique_components = []
            seen_serials = set()
            
            for doc in results:
                if "components" in doc.metadata and doc.metadata["components"]:
                    for comp in doc.metadata["components"]:
                        if comp["serial"] not in seen_serials:
                            seen_serials.add(comp["serial"])
                            unique_components.append(comp)
            
            # Extrair componentes do prompt também
            prompt_components = extract_components_with_serials(prompt)
            for comp in prompt_components:
                if comp["serial"] not in seen_serials:
                    seen_serials.add(comp["serial"])
                    unique_components.append(comp)
            
            response_components = unique_components
            
            # Se a pergunta é sobre números de série, adicionar ao contexto
            serial_context = ""
            if response_components:
                component_list = "\n".join([f"- {comp['component']}: {comp['serial']}" for comp in response_components])
                serial_context = f"\n\nComponents with serial numbers: \n{component_list}"

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
                            "When mentioning serial numbers, list each component separately with its specific serial number. "
                            "Do NOT repeat the same serial number for different components. "
                            "Always answer step-by-step when applicable. "
                            "If the user asks for a photo, say: 'See the image below.' "
                            "If the answer is not in the documents, say exactly: "
                            "'This situation is not documented yet.'"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"History:\n{history_context}\n\nDocumentation:\n{context}{serial_context}\n\nQuestion: {prompt}"
                    }
                ]
            )
            
            response_content = llm_response.choices[0].message.content

            # Parse for Step Images
            lines = response_content.split("\n")
            current_step = None
            
            # Simple heuristic to find step numbers and associate images
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
            
            # Mostrar componentes encontrados em formato tabular
            if response_components:
                st.markdown("---")
                st.subheader("🔧 Components Identified")
                
                # Criar tabela
                for i, comp in enumerate(response_components, 1):
                    col1, col2, col3 = st.columns([3, 5, 1])
                    with col1:
                        st.markdown(f"**{comp['component']}**")
                    with col2:
                        st.code(comp['serial'], language=None)
                    with col3:
                        copy_key = f"copy_{comp['serial']}_{i}"
                        if st.button("📋", key=copy_key, help="Copy serial number"):
                            # Usar JavaScript para copiar para área de transferência
                            js_code = f"""
                            <script>
                            navigator.clipboard.writeText("{comp['serial']}");
                            </script>
                            """
                            st.components.v1.html(js_code)
                            st.toast(f"Copied: {comp['serial']}", icon="✅")
            
            for img in response_images:
                if os.path.exists(img):
                    st.image(img, width=IMAGE_WIDTH)
                else:
                    st.warning(f"Image not found: {img}")

        # Save to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_content,
            "images": response_images,
            "components": response_components
        })
