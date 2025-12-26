import streamlit as st
import os
import fitz  # PyMuPDF
import sys

# Add root directory to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from utils.image_processing import describe_image
except ImportError:
    st.error("❌ utility module not found. Check 'utils/image_processing.py'")
    st.stop()

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
VECTOR_STORE_PATH = "faiss_index"
IMAGE_WIDTH = 450


# Load OpenAI
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("❌ OpenAI API Key missing in Streamlit secrets.")
    st.stop()


# ================= LOAD DOCUMENTS & VECTOR DB =================
def load_and_process_documents():
    """Reads all PDFs, text files, and IMAGES from doc_dir and returns chunks."""
    docs = []
    
    status_text = st.empty()
    status_text.info("📂 Scanning documents and analyzing images (this may take a while)...")
    
    # Initialize Text Splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )

    for root, _, files in os.walk(DOC_DIR):
        for file in files:
            path = os.path.join(root, file)
            # Relative path for metadata
            rel_path = os.path.relpath(path, DOC_DIR)
            
            # --- PROCESS PDF ---
            if file.lower().endswith(".pdf"):
                with fitz.open(path) as pdf:
                    text = "\n".join(page.get_text() for page in pdf)
                if text.strip():
                    docs.append(Document(page_content=text, metadata={"source": rel_path, "type": "text"}))

            # --- PROCESS TEXT/MD ---
            elif file.lower().endswith((".md", ".txt")):
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                if text.strip():
                    docs.append(Document(page_content=text, metadata={"source": rel_path, "type": "text"}))

            # --- PROCESS IMAGES (NEW) ---
            elif file.lower().endswith((".jpg", ".jpeg", ".png")):
                # Generate description using GPT-4o-mini
                try:
                    description = describe_image(client, path)
                    # We store the description as the 'content' so we can vector search it
                    # But we mark type='image' so we know to display the image itself
                    docs.append(Document(
                        page_content=f"Image related to: {rel_path}\nDescription: {description}", 
                        metadata={"source": rel_path, "type": "image", "full_path": path}
                    ))
                except Exception as e:
                    print(f"Skipping image {file}: {e}")
            else:
                continue

    status_text.empty()
    
    # Split big text docs into chunks (images are usually small enough, but good to ensure consistency)
    return splitter.split_documents(docs)


@st.cache_resource
def get_vector_db():
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Check if index exists on disk
    if os.path.exists(VECTOR_STORE_PATH):
        try:
            return FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            st.warning(f"⚠️ Could not load existing index: {e}. Rebuilding...")
    
    # If not, build it and save
    chunks = load_and_process_documents()
    if not chunks:
        return None
        
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(VECTOR_STORE_PATH)
    return db


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ Settings")

    if st.button("🔄 Force Rebuild Knowledge Base"):
        st.cache_resource.clear()
        if os.path.exists(VECTOR_STORE_PATH):
            import shutil
            shutil.rmtree(VECTOR_STORE_PATH)
        st.rerun()

    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# ================= INIT =================
st.title("🛠️ Work Procedures Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Load DB (Persistent)
db = get_vector_db()

if not db:
    st.warning("⚠️ No documents found. Please add files to the 'documents' folder.")
    st.stop()


# ================= CHAT HISTORY =================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Display images if any were associated with this message
        for img_path in msg.get("images", []):
            if os.path.exists(img_path):
                st.image(img_path, width=IMAGE_WIDTH)


# ================= CHAT INPUT =================
if prompt := st.chat_input("Ask a question about procedures..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ---------- RAG SEARCH ----------
    # Retrieve top k (mixed text and images)
    results = db.similarity_search(prompt, k=4)
    
    context_text_parts = []
    retrieved_images = []

    for doc in results:
        # Build context for LLM
        context_text_parts.append(f"[{doc.metadata.get('source')}]: {doc.page_content}")
        
        # Collect images to display
        if doc.metadata.get("type") == "image":
            full_path = doc.metadata.get("full_path")
            if full_path and full_path not in retrieved_images:
                retrieved_images.append(full_path)

    context = "\n\n".join(context_text_parts)
    
    # ---------- GENERATE ANSWER ----------
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
                    "Use the provided context (which includes text and descriptions of images) to answer. "
                    "If the answer involves an image that was retrieved, mention it effectively."
                    "If the answer is not in the documents, say exactly: 'This situation is not documented yet.'"
                )
            },
            {
                "role": "user",
                "content": (
                    f"History:\n{history_context}\n\n"
                    f"Context/Documentation:\n{context}\n\n"
                    f"Question: {prompt}"
                )
            }
        ]
    )

    response_content = llm_response.choices[0].message.content.strip()

    # ---------- DISPLAY ----------
    with st.chat_message("assistant"):
        st.markdown(response_content)
        
        # If the LLM says it's not documented, don't show images (unless they seem very relevant? strict logic for now)
        if response_content != "This situation is not documented yet.":
            for img in retrieved_images:
                if os.path.exists(img):
                    st.image(img, caption=os.path.basename(img), width=IMAGE_WIDTH)
                else:
                    st.warning(f"Image not found: {img}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_content,
            "images": retrieved_images if response_content != "This situation is not documented yet." else []
        }
    )
