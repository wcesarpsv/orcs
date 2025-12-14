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
                        metadata={"source": os.path.relpath(path, DOC_DIR)}
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
            
            # Simple heuristic to find step numbers and associate images
            # Re-using the logic from the original code but adapted for our config structure
            for line in lines:
                if line.strip() and line.lstrip()[0].isdigit():
                    try:
                        # naive parser for "1. Do something" -> 1
                        current_step = str(line.split(".")[0]) 
                    except:
                        pass
                
                if current_step:
                    # Check all sources in results to see if they match mapped images
                    for doc in results:
                        src = doc.metadata.get("source")
                        # Normalize path slashes for cross-platform mapping check if needed, 
                        # but keeping simple for now as per original code logic
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
