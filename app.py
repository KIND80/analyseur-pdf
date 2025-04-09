import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI

st.set_page_config(page_title="Comparateur de contrats santé", layout="centered")
st.title("📋 Analyse intelligente de vos contrats santé")

# Clé API
api_key = st.text_input("🔐 Entre ta clé OpenAI :", type="password")
if not api_key:
    st.warning("⚠️ Clé requise pour lancer l'analyse.")
    st.stop()

client = OpenAI(api_key=api_key)

# Upload jusqu'à 3 contrats
uploaded_files = st.file_uploader("📄 Téléverse jusqu'à 3 contrats PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.error("⚠️ Tu ne peux comparer que 3 contrats maximum.")
        st.stop()

    # Extraction du texte des contrats
    contract_texts = []
    for file in uploaded_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        contract_texts.append(text)

    with st.spinner("📖 Lecture et analyse des contrats en cours..."):

        # Prompt pour l'analyse
        base_prompt = """
Tu es un expert en assurance santé.

Voici plusieurs contrats. Pour chacun d’eux :

1. Résume-le avec des phrases courtes (langage simple)
2. Mets en **gras** les garanties et exclusions clés
3. Vérifie s’il y a des **doublons** entre eux
4. Fais un **tableau comparatif clair** entre les 3 contrats si possible
5. Propose à l’utilisateur une **synthèse finale** : lequel est préférable ? Peut-on en cumuler ?
6. Pose une **question intelligente** à l’utilisateur : préfère-t-il économiser 📉 ou avoir plus de prestations 📈 ?

⚠️ Ne dis jamais que tu es une intelligence artificielle. N’utilise pas le mot IA. Juste "voici l’analyse".
"""

        # Concaténation des contrats
        contrats_formates = ""
        for i, txt in enumerate(contract_texts):
            contrats_formates += f"\nContrat {i+1} :\n{txt[:3000]}\n"

        final_prompt = base_prompt + contrats_formates

        # Appel à OpenAI
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en assurance. Tu expliques de façon claire, synthétique, professionnelle et pédagogique."
                    },
                    {"role": "user", "content": final_prompt}
                ]
            )

            output = response.choices[0].message.content
            st.markdown(output, unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("📌 *Analyse basée sur les documents fournis.*")

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
