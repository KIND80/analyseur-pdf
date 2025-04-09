import streamlit as st
import fitz  # PyMuPDF
import openai

from openai import OpenAI

st.set_page_config(page_title="Analyse IA de contrat", layout="centered")
st.title("🧠 Analyse intelligente de contrat d'assurance")

# 1. Entrée de la clé API OpenAI
api_key = st.text_input("🔐 Entre ta clé OpenAI :", type="password")
if not api_key:
    st.warning("⚠️ Clé requise pour analyser le contrat.")
    st.stop()

client = OpenAI(api_key=api_key)

# 2. Upload du fichier PDF
uploaded_file = st.file_uploader("📄 Téléverse ton contrat PDF", type="pdf")

if uploaded_file:
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)

    with st.expander("📘 Voir le texte extrait du contrat"):
        st.text_area("Contenu du contrat", text, height=300)

    st.subheader("🧠 Analyse IA :")
    with st.spinner("Analyse en cours avec ChatGPT..."):

        prompt = f"""
Tu es un expert en assurance. Explique ce contrat à quelqu'un qui n'y connaît rien.

1. Résume ce que le contrat couvre.
2. Explique les exclusions importantes.
3. Fais des recommandations utiles.
4. Dis ce qu'il manque ou mérite d'être vérifié.

Voici le contrat :
{text[:5000]}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un assistant expert en assurance, très pédagogue."},
                    {"role": "user", "content": prompt}
                ]
            )
            output = response.choices[0].message.content
            st.write(output)

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
