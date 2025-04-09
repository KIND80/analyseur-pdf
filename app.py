import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI

# Configuration de la page
st.set_page_config(page_title="Comparateur de contrats santé", layout="centered")
st.title("📋 Analyse intelligente de vos contrats santé")

# Clé API OpenAI
api_key = st.text_input("🔐 Entre ta clé OpenAI :", type="password")
if not api_key:
    st.warning("⚠️ Clé requise pour lancer l'analyse.")
    st.stop()

client = OpenAI(api_key=api_key)

# Choix utilisateur
user_objective = st.radio(
    "🎯 Quel est votre objectif principal ?",
    ["📉 Réduire les coûts", "📈 Améliorer les prestations"],
    index=0
)

# Upload fichiers
uploaded_files = st.file_uploader(
    "📄 Téléverse jusqu'à 3 contrats PDF",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.error("⚠️ Tu ne peux comparer que 3 contrats maximum.")
        st.stop()

    # Extraction des textes
    contract_texts = []
    for file in uploaded_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        contract_texts.append(text)

    with st.spinner("📖 Lecture et analyse des contrats en cours..."):

        # PROMPT GPT-4
        base_prompt = """
Tu es un conseiller expert en assurance santé. Tu dois analyser plusieurs contrats fournis par un utilisateur.

Ton objectif est de produire une analyse :
- claire 🧠
- structurée 🧾
- synthétique ✍️
- mais complète 💡

Voici ce que tu dois faire :

1. 📄 Résume chaque contrat en 3-4 phrases simples. Précise ce qu’il couvre, ce qu’il **exclut**, et les **franchises / primes / limites** importantes.
2. ❗️ Repère les **doublons** (ex: 2 contrats couvrent la même chose).
3. ⚖️ Crée un **tableau comparatif clair** (une ligne par contrat, une colonne pour chaque aspect : soins, hospitalisation, médecine alternative, dentaire, franchise, etc.).
4. 🧭 Donne une **recommandation personnalisée** basée sur l’objectif de l’utilisateur (réduire les coûts ou améliorer la couverture).
5. 💬 Pose une **question finale intelligente** à l’utilisateur pour affiner le conseil (par exemple : “Êtes-vous prêt à augmenter votre franchise pour payer moins chaque mois ?”)
6. 🚫 Ne mentionne jamais que c’est une IA ou un assistant numérique.

Utilise des titres, des bullet points, des emojis, et du texte **en gras** pour rendre tout ça lisible.
"""

        contrats_formates = ""
        for i, txt in enumerate(contract_texts):
            contrats_formates += f"\nContrat {i+1} :\n{txt[:3000]}\n"

        final_prompt = (
            base_prompt
            + f"\n\nPréférence de l'utilisateur : {user_objective}\n"
            + contrats_formates
        )

        # Appel GPT-4
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en assurance. Tu fais des analyses claires, professionnelles et pédagogiques."
                    },
                    {
                        "role": "user",
                        "content": final_prompt
                    }
                ]
            )

            output = response.choices[0].message.content
            st.markdown(output, unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("📌 *Analyse basée sur les documents fournis.*")

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
