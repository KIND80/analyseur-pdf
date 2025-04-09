import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
import base64

# Configuration de la page
st.set_page_config(page_title="Comparateur de contrats santé", layout="centered")
st.title("📋 Analyse intelligente de vos contrats santé")

# Clé API utilisateur
api_key = st.text_input("🔐 Entrez votre clé OpenAI (commence par sk-...)", type="password")
if not api_key:
    st.warning("⚠️ Une clé API OpenAI est requise pour lancer l'analyse.")
    st.stop()

client = OpenAI(api_key=api_key)

# Objectif utilisateur
user_objective = st.radio(
    "🎯 Quel est votre objectif principal ?",
    ["📉 Réduire les coûts", "📈 Améliorer les prestations"],
    index=0
)

# Upload PDF
uploaded_files = st.file_uploader(
    "📄 Téléversez jusqu'à 3 contrats PDF",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.error("⚠️ Vous ne pouvez comparer que 3 contrats maximum.")
        st.stop()

    contract_texts = []
    for file in uploaded_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        contract_texts.append(text)

    with st.spinner("📖 Lecture et analyse des contrats en cours..."):

        base_prompt = """
Tu es un conseiller expert en assurance santé.

Ton objectif est de produire une analyse :
- claire 🧠
- structurée 🧾
- synthétique ✍️
- mais complète 💡

Voici ce que tu dois faire :

1. 📄 Résume chaque contrat en 3-4 phrases simples. Précise ce qu’il couvre, ce qu’il **exclut**, et les **franchises / primes / limites** importantes.
2. ❗️ Repère les **doublons** (ex: 2 contrats couvrent la même chose).
3. ⚖️ Crée un **tableau comparatif clair** (une ligne par contrat, une colonne pour chaque aspect : soins, hospitalisation, médecine alternative, dentaire, franchise, etc.).
4. 🧭 Donne une **recommandation personnalisée** basée sur l’objectif de l’utilisateur.
5. 💬 Pose une **question finale intelligente** pour affiner le conseil.
6. 🚫 Ne mentionne jamais que c’est une IA ou un assistant numérique.

Utilise des titres, des bullet points, des emojis, du texte **en gras**, et marque la recommandation en VERT.
"""

        contrats_formates = ""
        for i, txt in enumerate(contract_texts):
            contrats_formates += f"\nContrat {i+1} :\n{txt[:3000]}\n"

        final_prompt = (
            base_prompt
            + f"\n\nPréférence de l'utilisateur : {user_objective}\n"
            + contrats_formates
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller humain, clair et professionnel."},
                    {"role": "user", "content": final_prompt}
                ]
            )

            output = response.choices[0].message.content
            st.markdown(output, unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("💬 *Analyse basée sur les contrats fournis.*")

            # Export PDF
            if st.button("📤 Télécharger l'analyse en PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Arial", size=12)
                for line in output.split("\n"):
                    pdf.multi_cell(0, 10, line)
                pdf_output = "analysis.pdf"
                pdf.output(pdf_output)

                with open(pdf_output, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="analyse.pdf">👉 Télécharger le fichier PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Erreur : {e}")

    # Système de messagerie
    st.markdown("### 🤔 Vous avez une question sur vos contrats ?")

    with st.form("followup_form"):
        user_question = st.text_input("Posez votre question ici 👇")
        submit = st.form_submit_button("Envoyer")

    if submit and user_question:
        with st.spinner("Réponse en cours..."):
            followup_prompt = f"""
L'utilisateur a fourni {len(contract_texts)} contrats. Voici l'analyse :
{output}

Question utilisateur : {user_question}

Réponds clairement, sans redemander les contrats. Sois humain et professionnel.
"""
            try:
                followup_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller humain clair."},
                        {"role": "user", "content": followup_prompt}
                    ]
                )
                answer = followup_response.choices[0].message.content
                st.markdown(answer, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ Erreur : {e}")

# Zone de contact
tab_contact = st.expander("📬 En savoir plus ou poser une question ?")
with tab_contact:
    st.markdown("Vous pouvez écrire directement à **contact@fideleconseiller.ch** pour toute question complémentaire sur l'analyse ou le fonctionnement de ce service.")
    st.markdown("Nous vous répondrons sous 24h avec plaisir.")
