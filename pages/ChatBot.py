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
st.set_page_config(page_title="Work Procedures Assistant", layout="wide")

DOC_DIR = "documents"
IMAGE_REGISTRY_PATH = "config/image_registry.json"
IMAGE_WIDTH = 450

VISUAL_KEYWORDS = {"show", "see", "picture", "photo", "image"}

# Load OpenAI
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("❌ OpenAI API Key missing in Streamlit secrets.")
    st.stop()


# ================= LOAD IMAGE REGISTRY =================
@st.cache_data
def load_image_registry():
    with open(IMAGE_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("images", [])


IMAGE_REGISTRY = load_image_registry()


# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    docs = []

    for root, _, files in os.walk(DOC_DIR):
        for file in files:
            path = os.path.join(root, file)

            if file.lower().endswith(".pdf"):
                with fitz.open(path) as pdf:
                    text = "\n".join(page.get_text() for page in pdf)

            elif file.lower().endswith((".md", ".txt")):
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
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

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )

    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return FAISS.from_documents(chunks, embeddings)


# ================= IMAGE RESOLUTION =================
def resolve_images(prompt, procedure, registry):
    q = set(prompt.lower().split())
    images = []

    for img in registry:
        if img["procedure"] != procedure:
            continue

        if q.intersection(set(img["tags"])):
            images.append(img["path"])

    return images


# ================= INTENT / PROCEDURE HEURISTICS =================
def infer_procedure(prompt, default_procedure):
    p = prompt.lower()

    if any(k in p for k in ["small", "large"]):
        if "carmanah" in p:
            return "installation/carmanah_installation.md"
        if "admart" in p:
            return "installation/admart_installation.md"

    return default_procedure


def is_visual_request(prompt):
    p = prompt.lower()
    return any(k in p for k in VISUAL_KEYWORDS)


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ Settings")

    if st.button("🔄 Refresh Knowledge Base"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# ================= INIT =================
st.title("🛠️ Work Procedures Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

db = load_vector_db()


# ================= CHAT HISTORY =================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for img in msg.get("images", []):
            if os.path.exists(img):
                st.image(img, width=IMAGE_WIDTH)


# ================= CHAT INPUT =================
if prompt := st.chat_input("Ask a question about procedures..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    prompt_lower = prompt.lower()

    # ---------- RAG SEARCH ----------
    results = db.similarity_search(prompt, k=3)
    context = "\n\n".join(doc.page_content for doc in results)

    rag_procedure = results[0].metadata.get("source")
    active_procedure = infer_procedure(prompt, rag_procedure)

    # ---------- VISUAL ONLY MODE ----------
    if is_visual_request(prompt):
        response_content = "Here is the image you requested."
    else:
        history_context = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in st.session_state.messages[-5:]
        )

        llm_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a work procedures assistant. "
                        "Answer ONLY using the provided documentation. "
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

        response_content = llm_response.choices[0].message.content.strip()

    # ---------- IMAGE RESOLUTION ----------
    if response_content == "This situation is not documented yet.":
        response_images = []
    else:
        response_images = resolve_images(
            prompt,
            active_procedure,
            IMAGE_REGISTRY
        )

    # ---------- DISPLAY ASSISTANT ----------
    with st.chat_message("assistant"):
        st.markdown(response_content)
        for img in response_images:
            if os.path.exists(img):
                st.image(img, width=IMAGE_WIDTH)
            else:
                st.warning(f"Image not found: {img}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_content,
            "images": response_images
        }
    )
