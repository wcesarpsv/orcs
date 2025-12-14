import streamlit as st
import os
import json
import fitz  # PyMuPDF

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
IMAGE_REGISTRY_PATH = "config/image_registry.json"
IMAGE_WIDTH = 450

# Load OpenAI
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("❌ OpenAI API Key missing in Streamlit secrets.")
    st.stop()


# ================= LOAD IMAGE REGISTRY =================
@st.cache_data
def load_image_registry():
    try:
        with open(IMAGE_REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("images", [])
    except Exception as e:
        st.error(f"Error loading image registry: {e}")
        return []


IMAGE_REGISTRY = load_image_registry()


# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    if not os.path.exists(DOC_DIR):
        return None

    docs = []

    for root, _, files in os.walk(DOC_DIR):
        for file in files:
            path = os.path.join(root, file)

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
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": os.path.relpath(path, DOC_DIR),
                            "doc_id": os.path.splitext(file)[0]
                        }
                    )
                )

    if not docs:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )
    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    return FAISS.from_documents(chunks, embeddings)


# ================= IMAGE RESOLUTION LOGIC =================
def resolve_images(prompt: str, procedure: str, registry: list) -> list:
    """
    Deterministic image resolver.
    Images are matched ONLY if:
    - They belong to the active procedure
    - One or more tags appear in the user prompt
    """
    q = set(prompt.lower().split())
    images = []

    for img in registry:
        if img.get("procedure") != procedure:
            continue

        if q.intersection(set(img.get("tags", []))):
            images.append(img["path"])

    return images


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ Settings")

    if st.button("🔄 Refresh Knowledge Base"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📚 How to use")
    st.markdown(
        """
        1. Ask a question about work procedures  
        2. Be specific (device, symptom, action)  
        3. Images will appear only when relevant  
        """
    )

    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# ================= INIT APP =================
st.title("🛠️ Work Procedures Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

db = load_vector_db()

if db is None:
    st.warning(f"⚠️ No documents found in `{DOC_DIR}`.")
    st.stop()


# ================= DISPLAY CHAT HISTORY =================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        for img in message.get("images", []):
            if os.path.exists(img):
                st.image(img, width=IMAGE_WIDTH)


# ================= CHAT INPUT =================
if prompt := st.chat_input("Ask a question about procedures..."):
    # User message
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # ================= RAG SEARCH =================
    results = db.similarity_search(prompt, k=3)
    context = "\n\n".join(doc.page_content for doc in results)

    active_procedure = results[0].metadata.get("source")

    history_context = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in st.session_state.messages[-5:]
    )

    # ================= LLM RESPONSE =================
    llm_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a work procedures assistant. "
                    "Answer ONLY using the provided documentation. "
                    "Always respond step-by-step when applicable. "
                    "If the answer is not in the documents, say exactly: "
                    "'This situation is not documented yet.'"
                )
            },
            {
                "role": "user",
                "content": (
                    f"History:\n{history_context}\n\n"
                    f"Documentation:\n{context}\n\n"
                    f"Question: {prompt}"
                )
            }
        ]
    )

    response_content = llm_response.choices[0].message.content

    # ================= IMAGE RESOLUTION =================
    response_images = resolve_images(
        prompt=prompt,
        procedure=active_procedure,
        registry=IMAGE_REGISTRY
    )

    # ================= DISPLAY ASSISTANT =================
    with st.chat_message("assistant"):
        st.markdown(response_content)
        for img in response_images:
            if os.path.exists(img):
                st.image(img, width=IMAGE_WIDTH)
            else:
                st.warning(f"Image not found: {img}")

    # Save history
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_content,
            "images": response_images
        }
    )
