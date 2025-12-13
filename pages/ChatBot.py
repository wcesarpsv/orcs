import streamlit as st
import os
import fitz  # PyMuPDF

# LangChain (imports atualizados e compatíveis)
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# OpenAI client (chat)
from openai import OpenAI


# ================= CONFIG =================
st.set_page_config(page_title="Procedures Assistant", layout="wide")
st.title("🛠️ Work Procedures Assistant")

DOC_DIR = "documents"

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    # --- Safety: folder exists ---
    if not os.path.exists(DOC_DIR):
        st.error(f"Documents folder not found: '{DOC_DIR}'")
        st.stop()

    docs = []

    # --- Recursive scan ---
    for root, _, files in os.walk(DOC_DIR):
        for file in files:
            path = os.path.join(root, file)

            # --- PDF ---
            if file.lower().endswith(".pdf"):
                try:
                    with fitz.open(path) as pdf:
                        text = "\n".join(page.get_text() for page in pdf)
                except Exception:
                    text = ""

                if text.strip():
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={"source": os.path.relpath(path, DOC_DIR)}
                        )
                    )

            # --- Markdown / TXT ---
            elif file.lower().endswith((".md", ".txt")):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    text = ""

                if text.strip():
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={"source": os.path.relpath(path, DOC_DIR)}
                        )
                    )

    # --- Safety: content loaded ---
    if not docs:
        st.error("Documents were found, but no readable content was loaded.")
        st.stop()

    # --- Chunking ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )
    chunks = splitter.split_documents(docs)

    # --- Embeddings (official OpenAI integration) ---
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    # --- Vector DB ---
    return FAISS.from_documents(chunks, embeddings)


# ================= INITIALIZE DB SAFELY =================
db = None
try:
    db = load_vector_db()
except Exception:
    st.stop()


# ================= CHAT =================
question = st.text_input("Ask your question:")

if question:
    if db is None:
        st.warning("Documents are not loaded yet.")
        st.stop()

    results = db.similarity_search(question, k=3)

    context = "\n\n".join(doc.page_content for doc in results)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a work procedures assistant. "
                    "Answer ONLY using the provided documentation. "
                    "Be clear, concise, and step-by-step when applicable. "
                    "If the answer is not in the documents, say exactly: "
                    "'This situation is not documented yet.'"
                )
            },
            {
                "role": "user",
                "content": f"Documentation:\n{context}\n\nQuestion: {question}"
            }
        ]
    )

    st.markdown("### ✅ Answer")
    st.write(response.choices[0].message.content)

    with st.expander("📄 Sources used"):
        sources = sorted({doc.metadata.get("source", "Unknown") for doc in results})
        for src in sources:
            st.write(src)
