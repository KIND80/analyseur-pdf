import streamlit as st
import fitz  # PyMuPDF

st.set_page_config(page_title="Analyse de contrat d'assurance", layout="centered")

st.title("📄 Analyse de contrat d’assurance")

uploaded_file = st.file_uploader("Téléverse ton contrat PDF", type="pdf")

if uploaded_file is not None:
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)

    st.subheader("📘 Texte extrait du PDF :")
    st.text_area("", text, height=300)

    st.subheader("🧠 Analyse automatique :")
    if "vol" in text.lower():
        st.success("✅ Ce contrat mentionne une couverture contre le vol.")
    else:
        st.warning("⚠️ Aucune mention du vol trouvée. Ce contrat pourrait être incomplet.")
