import streamlit as st
import os
import fitz

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

from openai import OpenAI


# ================= CONFIG =================
st.set_page_config(page_title="Procedures Assistant", layout="wide")
st.title("🛠️ Work Procedures Assistant")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
DOC_DIR = "documents"

# ================= LOAD DOCS =================
@st.cache_resource
def load_vector_db():
    docs = []

    for file in os.listdir(DOC_DIR):
        path = os.path.join(DOC_DIR, file)

        if file.endswith(".pdf"):
            with fitz.open(path) as pdf:
                text = "\n".join(p.get_text() for p in pdf)
                docs.append(Document(page_content=text, metadata={"source": file}))

        elif file.endswith((".md", ".txt")):
            with open(path, "r", encoding="utf-8") as f:
                docs.append(Document(page_content=f.read(), metadata={"source": file}))

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings()
    return FAISS.from_documents(chunks, embeddings)

db = load_vector_db()

# ================= CHAT =================
question = st.text_input("Ask your question:")

if question:
    docs = db.similarity_search(question, k=3)
    context = "\n\n".join(d.page_content for d in docs)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a work procedures assistant. "
                    "Answer ONLY using the provided documentation. "
                    "If the answer is not in the documents, say: "
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

    with st.expander("📄 Sources"):
        for d in docs:
            st.write(d.metadata["source"])
