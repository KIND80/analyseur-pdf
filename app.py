import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
import base64

# UI config
st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.markdown("""
<style>
    .recommendation {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        margin-top: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 Votre Assistant Assurance Santé Intelligent")
st.markdown("""
Téléversez jusqu'à **3 contrats PDF** et obtenez :
- une **analyse claire et simplifiée**
- la **détection de doublons** entre contrats
- un **tableau comparatif visuel**
- des **recommandations personnalisées**
- une **option de messagerie intelligente**
""")

# Clé API utilisateur
api_key = st.text_input("🔐 Entrez votre clé OpenAI (commence par sk-...)", type="password")
if not api_key:
    st.info("💡 Vous devez entrer votre clé API pour lancer l'analyse.")
    st.stop()

client = OpenAI(api_key=api_key)

# Objectif utilisateur
user_objective = st.radio(
    "🎯 Quel est votre objectif principal ?",
    ["📉 Réduire les coûts", "📈 Améliorer les prestations"],
    index=0
)

# Upload fichiers
uploaded_files = st.file_uploader(
    "📄 Téléversez vos contrats PDF (max 3)",
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

    with st.spinner("📖 Lecture et analyse des contrats..."):

        base_prompt = """
Tu es un conseiller expert en assurance santé. Ton rôle :
- Lire et expliquer chaque contrat simplement
- Repérer les doublons et les recouvrements
- Créer un tableau comparatif clair
- Faire des recommandations personnalisées (en vert)
- Poser une question finale utile à l'utilisateur

Tu ne dis jamais que tu es une IA. Tu rédiges comme un conseiller humain.
"""

        contrats_formates = ""
        for i, txt in enumerate(contract_texts):
            contrats_formates += f"\nContrat {i+1} :\n{txt[:3000]}\n"

        final_prompt = (
            base_prompt
            + f"\n\nObjectif utilisateur : {user_objective}\n"
            + contrats_formates
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller assurance humain et bienveillant."},
                    {"role": "user", "content": final_prompt}
                ]
            )

            output = response.choices[0].message.content
            st.markdown(output, unsafe_allow_html=True)
            st.markdown("""
            <div class='recommendation'>
                ✅ *Ces recommandations sont personnalisées selon vos contrats et vos préférences.*
            </div>
            """, unsafe_allow_html=True)

            if st.button("📥 Télécharger l'analyse en PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Arial", size=12)
                for line in output.split("\n"):
                    pdf.multi_cell(0, 10, line.encode("latin-1", "replace").decode("latin-1"))
                pdf_output = "analysis.pdf"
                pdf.output(pdf_output)
                with open(pdf_output, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="analyse.pdf">📄 Cliquez ici pour télécharger le PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Erreur : {e}")

    # Mini messagerie
    st.markdown("### 💬 Une question ? Posez-la ici :")
    with st.form("followup_form"):
        user_question = st.text_input("Votre question sur l'analyse ou un contrat 👇")
        submit = st.form_submit_button("Envoyer")

    if submit and user_question:
        with st.spinner("Réponse en cours..."):
            followup_prompt = f"""
L'utilisateur a fourni {len(contract_texts)} contrats. Analyse précédente :
{output}

Question : {user_question}

Réponds clairement, sans mention d'IA. Sois utile.
"""
            try:
                followup_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller humain."},
                        {"role": "user", "content": followup_prompt}
                    ]
                )
                answer = followup_response.choices[0].message.content
                st.markdown(answer, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ Erreur : {e}")

# 📬 Zone de contact
st.markdown("""
---
### 📫 Une question sur cette application ou l'intelligence qui l'alimente ?
👉 Contactez-nous par email : [contact@fideleconseiller.ch](mailto:contact@fideleconseiller.ch)
Nous vous répondrons sous 24h avec plaisir.
""")
