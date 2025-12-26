#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
convert_docs.py

App Streamlit para:
- Fazer upload de um arquivo .docx (procedimento)
- Converter o conteúdo para Markdown (.md)
- Extrair as imagens internas do .docx
- Disponibilizar para download:
    - o .md
    - um .zip com todas as imagens, com nomes padronizados

Uso:
    streamlit run convert_docs.py
"""

import os
import zipfile
from io import BytesIO
from typing import Iterable, Union

import streamlit as st
from docx import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


# ================== Helpers para iterar blocos (parágrafos + tabelas) ================== #

def iter_block_items(parent) -> Iterable[Union[Paragraph, Table]]:
    """
    Itera sobre parágrafos e tabelas na ordem em que aparecem no documento.
    (Padrão de uso do python-docx)
    """
    parent_elm = parent.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


# ================== Conversão DOCX -> Markdown ================== #

def paragraph_to_markdown(p: Paragraph) -> str:
    """
    Converte um parágrafo do Word em uma linha de Markdown simples.
    - Headings -> #, ##, ### ...
    - Listas bullet -> -
    - Listas numeradas -> 1.
    - Texto normal -> linha simples
    """
    text = p.text.strip()
    if not text:
        return ""

    style_name = (p.style.name or "").lower()

    # Headings (Título 1, 2, 3...)
    if "heading" in style_name:
        level = 1
        for num in range(1, 7):
            if str(num) in style_name:
                level = num
                break
        return f"{'#' * level} {text}"

    # Lista com bullet
    if "list bullet" in style_name:
        return f"- {text}"

    # Lista numerada
    if "list number" in style_name:
        return f"1. {text}"

    # Parágrafo normal
    return text


def table_to_markdown(table: Table) -> str:
    """
    Converte uma tabela do Word em uma tabela Markdown simples.
    Se a tabela for meio 'estranha', pelo menos o texto fica legível.
    """
    rows_text = []
    for row in table.rows:
        cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
        rows_text.append("| " + " | ".join(cells) + " |")

    if not rows_text:
        return ""

    # Header + separador
    header = rows_text[0]
    num_cols = header.count("|") - 1
    separator = "|" + " --- |" * num_cols

    if len(rows_text) == 1:
        return header + "\n" + separator

    return header + "\n" + separator + "\n" + "\n".join(rows_text[1:])


def convert_docx_bytes_to_markdown(file_bytes: bytes) -> str:
    """
    Lê um .docx a partir de bytes e devolve um texto Markdown.
    """
    doc = DocxDocument(BytesIO(file_bytes))
    md_lines = []

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            line = paragraph_to_markdown(block)
            md_lines.append(line)
        elif isinstance(block, Table):
            table_md = table_to_markdown(block)
            md_lines.append(table_md)

        # Linha em branco para separar blocos
        md_lines.append("")

    md_text = "\n".join(md_lines).strip() + "\n"
    return md_text


# ================== Extração de imagens do DOCX ================== #

def extract_images_from_docx_bytes(file_bytes: bytes, base_name: str):
    """
    Extrai todas as imagens do .docx (word/media/*) a partir de bytes.

    Retorna:
        lista de tuplas (nome_arquivo, conteudo_bytes)
    """
    images = []
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        media_files = [f for f in zf.namelist() if f.startswith("word/media/")]
        if not media_files:
            return images

        idx = 1
        for media in media_files:
            ext = os.path.splitext(media)[1].lower()
            if ext not in [".png", ".jpg", ".jpeg", ".gif"]:
                continue

            img_name = f"{base_name}_{idx}{ext}"
            img_bytes = zf.read(media)
            images.append((img_name, img_bytes))
            idx += 1

    return images


# ================== App Streamlit ================== #

st.set_page_config(page_title="DOCX → Markdown Converter", layout="centered")
st.title("📄 DOCX → Markdown + Imagens")

st.markdown(
    """
Carregue um arquivo **.docx** com o procedimento (por exemplo, *SST Relocation*),  
e eu vou gerar:

- Um arquivo **Markdown (.md)** com o conteúdo do procedimento
- Um **.zip com todas as imagens** internas do documento, com nomes padronizados

Depois é só você baixar e colocar:
- O `.md` na pasta `documents/...`
- As imagens na subpasta `images/` que preferir
    """
)

uploaded_file = st.file_uploader("Envie um arquivo .docx", type=["docx"])

if uploaded_file is not None:
    # Nome base (sem extensão) para usar no .md e nas imagens
    original_name = uploaded_file.name
    base_name = os.path.splitext(original_name)[0]
    # Troca espaços por underscore para ficar mais amigável
    base_name_clean = base_name.replace(" ", "_").lower()

    file_bytes = uploaded_file.read()

    with st.spinner("Convertendo para Markdown e extraindo imagens..."):
        # Converter para Markdown
        md_text = convert_docx_bytes_to_markdown(file_bytes)
        # Extrair imagens
        images = extract_images_from_docx_bytes(file_bytes, base_name_clean)

    st.success("✅ Conversão concluída!")

    st.subheader("📑 Preview do Markdown (somente visualização)")
    st.code(md_text[:3000] + ("\n\n... (cortado)" if len(md_text) > 3000 else ""), language="markdown")

    # ---------- Download do Markdown ---------- #
    st.subheader("⬇️ Download dos arquivos gerados")

    md_filename = f"{base_name_clean}.md"
    st.download_button(
        label=f"Baixar Markdown: {md_filename}",
        data=md_text.encode("utf-8"),
        file_name=md_filename,
        mime="text/markdown",
    )

    # ---------- Download das imagens (ZIP) ---------- #
    if images:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_name, img_bytes in images:
                zf.writestr(img_name, img_bytes)
        zip_buffer.seek(0)

        zip_filename = f"{base_name_clean}_images.zip"
        st.download_button(
            label=f"Baixar imagens (.zip): {zip_filename}",
            data=zip_buffer,
            file_name=zip_filename,
            mime="application/zip",
        )

        st.markdown("**Imagens encontradas:**")
        for img_name, _ in images:
            st.write(f"- {img_name}")
    else:
        st.info("Nenhuma imagem foi encontrada dentro deste .docx.")
