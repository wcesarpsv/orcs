import streamlit as st
import os
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
st.title("🛠️ Work Procedures Assistant")

DOC_DIR = "documents"
IMAGE_WIDTH = 450

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ================= STEP → IMAGE MAP =================
STEP_IMAGE_MAP = {
    "inventory/wjs_inventory_sign_out.md": {
        3: ["documents/inventory/images/wjs_box_label_example.jpg"],
        4: ["documents/inventory/images/wjs_serial_number_example.jpg"],
    }
}


# ================= IMAGE QUERY MAP (direct photo requests) =================
IMAGE_QUERY_MAP = [
    {
        "keywords": ["serial", "serial number", "wjs serial", "photo of serial"],
        "title": "WJS serial number example",
        "images": ["documents/inventory/images/wjs_serial_number_example.jpg"],
    },
    {
        "keywords": ["box label", "label", "wjs box", "model label"],
        "title": "WJS box label example",
        "images": ["documents/inventory/images/wjs_box_label_example.jpg"],
    },
]

STEP_IMAGE_MAP.update({
    "troubleshooting/wjs_troubleshooting_guide.md": {
        # Admart
        1: ["documents/troubleshooting/images/admart_no_power.jpg"],
        2: ["documents/troubleshooting/images/admart_flashing_decimals.jpg"],

        # Carmanah
        3: ["documents/troubleshooting/images/carmanah_no_power.jpg"],
        4: ["documents/troubleshooting/images/carmanah_flashing_decimals.jpg"],
        5: ["documents/troubleshooting/images/carmanah_moving_decimals.jpg"],

        # Transceiver / Router
        6: ["documents/troubleshooting/images/transceiver_green_led.jpg"],
        7: ["documents/troubleshooting/images/cisco_router_reset_button.jpg"],
    }
})



# ================= LOAD DOCUMENTS & VECTOR DB =================
@st.cache_resource
def load_vector_db():
    if not os.path.exists(DOC_DIR):
        st.error(f"Documents folder not found: '{DOC_DIR}'")
        st.stop()

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
        st.error("Documents were found, but no readable content was loaded.")
        st.stop()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )
    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    return FAISS.from_documents(chunks, embeddings)


# ================= INIT DB =================
db = None
try:
    db = load_vector_db()
except Exception:
    st.stop()


# ================= CHAT =================
question = st.text_input("Ask your question:")

if question:
    q = question.lower()

    # ================= DIRECT IMAGE REQUEST =================
    for item in IMAGE_QUERY_MAP:
        if any(k in q for k in item["keywords"]):
            st.markdown("### 🖼️ Photo")
            st.write(item["title"])

            for img in item["images"]:
                if os.path.exists(img):
                    st.image(img, width=IMAGE_WIDTH)
                else:
                    st.error(f"Image not found: {img}")

            st.stop()

    # ================= NORMAL RAG FLOW =================
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
                    "Always answer step-by-step when applicable. "
                    "Do not output Markdown image links like ![...](...). "
                    "If the user asks for a photo, say: 'See the image below.' "
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
    rendered_images = set()

    for line in lines:
        st.write(line)

        # Detect numbered steps (e.g., "4. Capture serial number")
        if line.strip() and line.lstrip()[0].isdigit():
            try:
                current_step = int(line.split(".")[0])
            except Exception:
                current_step = None

        if current_step is None:
            continue

        for doc in results:
            src = doc.metadata.get("source")

            if src in STEP_IMAGE_MAP and current_step in STEP_IMAGE_MAP[src]:
                for img in STEP_IMAGE_MAP[src][current_step]:
                    key = f"{src}:{current_step}:{img}"
                    if key not in rendered_images and os.path.exists(img):
                        st.image(img, width=IMAGE_WIDTH)
                        rendered_images.add(key)

    # ================= SOURCES =================
    with st.expander("📄 Sources used"):
        sources = sorted({doc.metadata.get("source", "Unknown") for doc in results})
        for src in sources:
            st.write(src)
