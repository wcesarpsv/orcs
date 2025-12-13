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


# IMAGE_MAP = {
#     "inventory/wjs_inventory_sign_out.md": [
#         "documents/inventory/images/wjs_box_label_example.jpg",
#         "documents/inventory/images/wjs_serial_number_example.jpg",
#     ]
# }


STEP_IMAGE_MAP = {
    "inventory/wjs_inventory_sign_out.md": {
        3: ["documents/inventory/images/wjs_box_label_example.jpg"],
        4: ["documents/inventory/images/wjs_serial_number_example.jpg"],
    }
}


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
    
    answer_text = response.choices[0].message.content
    lines = answer_text.split("\n")
    
    current_step = None
    
    for line in lines:
        st.write(line)
    
        # Detect step number (e.g., "4. Capture WJS serial number")
        if line.strip() and line.lstrip()[0].isdigit():
            try:
                current_step = int(line.split(".")[0])
            except:
                current_step = None
    
        # Show images right after the step that needs them
        for doc in results:
            src = doc.metadata.get("source")
            if (
                src in STEP_IMAGE_MAP
                and current_step in STEP_IMAGE_MAP[src]
            ):
                for img in STEP_IMAGE_MAP[src][current_step]:
                    if os.path.exists(img):
                        st.image(img, use_column_width=True)


    # ================= SHOW RELATED IMAGES =================
    # shown_images = set()
    
    # for doc in results:
    #     src = doc.metadata.get("source")
    #     if src in IMAGE_MAP:
    #         for img in IMAGE_MAP[src]:
    #             if img not in shown_images and os.path.exists(img):
    #                 st.image(img, use_column_width=True)
    #                 shown_images.add(img)


    # with st.expander("📄 Sources used"):
    #     sources = sorted({doc.metadata.get("source", "Unknown") for doc in results})
    #     for src in sources:
    #         st.write(src)
