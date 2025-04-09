import streamlit as st
import fitz  # PyMuPDF
import openai

st.set_page_config(page_title="Analyse IA de contrat", layout="centered")
st.title("🧠 Analyse intelligente de contrat d'assurance")

# 1. Entrée de la clé API OpenAI
openai_api_key = st.text_input("🔐 Ta clé OpenAI (nécessaire pour l’analyse)", type="password")
if not openai_api_key:
    st.warning("💡 Entre ta clé pour activer l'analyse IA.")
    st.stop()
openai.api_key = openai_api_key

# 2. Upload du fichier PDF
uploaded_file = st.file_uploader("📄 Téléverse ton contrat PDF", type="pdf")

if uploaded_file:
    # 3. Lecture du texte du PDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)

    # 4. Affichage du texte brut
    with st.expander("📘 Voir le texte extrait du contrat"):
        st.text_area("Contenu du contrat", text, height=300)

    # 5. Analyse IA
    st.subheader("🧠 Analyse par l'IA en langage simple")
    with st.spinner("Analyse en cours avec l'IA..."):

        prompt = f"""
Tu es un expert en assurance. Ton rôle est d'expliquer ce contrat à quelqu'un qui ne comprend rien à l'assurance.

Fais :
1. Un résumé clair de ce que le contrat couvre.
2. Une explication des exclusions ou points à surveiller.
3. Des recommandations utiles.
4. Ce qu’il manque ou pourrait être amélioré.

Voici le texte du contrat :
{text[:5000]}
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        output = response.choices[0].message["content"]
        st.write(output)
