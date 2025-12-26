#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
md_image_placer.py

App Streamlit para:
- Fazer upload de um arquivo Markdown (.md)
- Fazer upload de um .zip com imagens (ex: sst_relocation_images.zip)
- Escolher em que seção (heading) do .md inserir cada imagem
- Gerar um novo .md com linhas de imagem no formato:

    ![Legenda](images/nome_da_imagem.ext)

Uso:
    streamlit run md_image_placer.py
"""

import os
from io import BytesIO
import zipfile

import streamlit as st


# ============ Funções auxiliares de Markdown ============ #

def parse_headings(md_text: str):
    """
    Encontra todas as linhas de heading no markdown.
    Retorna lista de tuplas: (line_index, heading_level, heading_text)
    """
    headings = []
    lines = md_text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            # Conta quantos '#' no início
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            headings.append((idx, level, text))
    return headings


def insert_image_after_heading(lines, heading_index, image_markdown: str):
    """
    Insere a linha de imagem logo após a linha do heading escolhido.
    """
    insert_pos = heading_index + 1
    # Adiciona uma linha em branco antes e/ou depois para ficar mais bonito
    new_lines = lines[:insert_pos] + ["", image_markdown, ""] + lines[insert_pos:]
    return new_lines


# ============ App Streamlit ============ #

st.set_page_config(page_title="Markdown Image Placer", layout="wide")
st.title("🖼️ Colocar imagens no .md (Procedimentos)")

st.markdown(
    """
Fluxo sugerido:

1. Use **convert_docs.py** para gerar:
   - `meu_procedimento.md`
   - `meu_procedimento_images.zip`
2. Aqui, faça upload do `.md` e do `.zip`.
3. Escolha **em qual seção** cada imagem deve entrar.
4. Baixe o novo `.md` com as imagens já referenciadas.

Depois é só colocar esse `.md` e as imagens na pasta certa do seu app de procedimentos.
"""
)

# --- Upload do Markdown --- #
uploaded_md = st.file_uploader("📄 Envie o arquivo Markdown (.md)", type=["md", "markdown", "txt"])

# --- Upload das imagens em ZIP --- #
uploaded_zip = st.file_uploader("🗂️ Envie o .zip com as imagens", type=["zip"])

if uploaded_md is None:
    st.info("Envie primeiro o arquivo .md gerado pelo convert_docs.py.")
    st.stop()

md_bytes = uploaded_md.read()
md_text_original = md_bytes.decode("utf-8", errors="ignore")

# Colocamos as linhas do md no session_state para permitir edições sucessivas
if "md_lines" not in st.session_state or st.session_state.get("current_md_name") != uploaded_md.name:
    st.session_state["md_lines"] = md_text_original.splitlines()
    st.session_state["current_md_name"] = uploaded_md.name

lines = st.session_state["md_lines"]

# --- Parse dos headings --- #
headings = parse_headings("\n".join(lines))

st.sidebar.header("⚙️ Configurações")
path_prefix = st.sidebar.text_input("Prefixo do caminho das imagens", value="images/")

st.subheader("📌 Seções detectadas no Markdown")
if not headings:
    st.warning("Nenhum heading (#, ##, ###, etc.) encontrado no .md. Mesmo assim, você pode editar manualmente.")
else:
    for idx, (line_idx, level, text) in enumerate(headings):
        indent = " " * (level - 1) * 2
        st.text(f"{idx}. {indent}{'#' * level} {text} (linha {line_idx})")

# --- Processar ZIP de imagens --- #
image_names = []
if uploaded_zip is not None:
    zip_bytes = uploaded_zip.read()
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        all_files = [f for f in zf.namelist() if not f.endswith("/")]
        # Só pegamos o basename (sem diretório interno)
        base_names = [os.path.basename(f) for f in all_files]
        # Remove vazios e duplicados, mantém ordem aproximada
        seen = set()
        for name in base_names:
            if name and name not in seen:
                seen.add(name)
                image_names.append(name)

if uploaded_zip is None:
    st.info("Se quiser mapear imagens, envie também o .zip gerado pelo convert_docs.py.")
else:
    st.subheader("🖼️ Imagens disponíveis no .zip")
    if image_names:
        st.write(", ".join(image_names))
    else:
        st.warning("Nenhuma imagem válida encontrada dentro do .zip.")

# --- Bloco de inserção de imagem --- #
st.subheader("➕ Inserir imagem em uma seção")

if not headings:
    st.info("Como não há headings, você pode depois editar o .md direto. (Mas recomendo usar títulos nos procedimentos.)")
else:
    if image_names:
        selected_image = st.selectbox("Escolha a imagem", options=image_names)
    else:
        selected_image = None

    section_labels = [f"{i} - {h[2]} (nível {h[1]})" for i, h in enumerate(headings)]
    selected_section_idx = st.selectbox("Escolha a seção onde a imagem será inserida", options=list(range(len(headings))), format_func=lambda i: section_labels[i])

    default_caption = ""
    if selected_image:
        # Sugere legenda baseada no nome do arquivo
        default_caption = os.path.splitext(selected_image)[0].replace("_", " ").title()

    caption = st.text_input("Legenda da imagem (alt text)", value=default_caption)

    if st.button("📍 Inserir imagem abaixo desta seção"):
        if selected_image is None:
            st.warning("Você precisa escolher uma imagem primeiro.")
        else:
            heading_line_index = headings[selected_section_idx][0]
            image_path = f"{path_prefix.rstrip('/')}/{selected_image}"
            image_md_line = f"![{caption}]({image_path})"

            new_lines = insert_image_after_heading(lines, heading_line_index, image_md_line)
            st.session_state["md_lines"] = new_lines
            st.success(f"Imagem `{selected_image}` inserida abaixo da seção: {headings[selected_section_idx][2]}")

# --- Preview do Markdown atualizado --- #
st.subheader("👀 Preview do Markdown atualizado")
preview_text = "\n".join(st.session_state["md_lines"])
st.code(preview_text[:4000] + ("\n\n... (cortado)" if len(preview_text) > 4000 else ""), language="markdown")

# --- Download do novo .md --- #
output_md_name = os.path.splitext(uploaded_md.name)[0] + "_with_images.md"
st.download_button(
    label=f"⬇️ Baixar Markdown atualizado: {output_md_name}",
    data="\n".join(st.session_state["md_lines"]).encode("utf-8"),
    file_name=output_md_name,
    mime="text/markdown",
)
