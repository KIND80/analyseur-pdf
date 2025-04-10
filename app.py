import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
import base64
import smtplib
from email.message import EmailMessage
from io import BytesIO
from PIL import Image
import pytesseract
import re

# Données de référence
base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False, "etranger": False},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True}
}

def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        if "5000" in texte or "10000" in texte:
            for nom in score:
                if base_prestations[nom]["dentaire"] >= 5000:
                    score[nom] += 2
        elif "1500" in texte:
            score["Assura"] += 2

    if "privée" in texte or "top liberty" in texte:
        for nom in score:
            if "privée" in base_prestations[nom]["hospitalisation"].lower():
                score[nom] += 2

    if "médecine alternative" in texte or "médecine naturelle" in texte:
        for nom in score:
            if base_prestations[nom]["médecine"]:
                score[nom] += 1

    if "check-up" in texte or "bilan santé" in texte or "fitness" in texte:
        for nom in score:
            if base_prestations[nom]["checkup"]:
                score[nom] += 1

    if "étranger" in texte or "à l’étranger" in texte:
        for nom in score:
            if base_prestations[nom]["etranger"]:
                score[nom] += 2

    if preference == "📉 Réduire les coûts":
        score["Assura"] += 3
    elif preference == "📈 Améliorer les prestations":
        for nom in score:
            score[nom] += 1
    elif preference == "❓ Je ne sais pas encore":
        pass

    return sorted(score.items(), key=lambda x: x[1], reverse=True)

# UI config
st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🤖 Votre Assistant Assurance Santé Intelligent")

st.markdown("""
Téléversez jusqu'à **3 contrats PDF** ou **photos de votre contrat** pour :
- une **analyse simplifiée**
- un **scoring automatique**
- des **recommandations personnalisées**
""")

st.markdown("### 🔐 Vérification d'identité")
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

user_objective = st.radio("🎯 Quel est votre objectif principal ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"], index=2)

uploaded_files = st.file_uploader("📄 Téléversez vos contrats PDF ou photos (JPEG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    contract_texts = []
    for i, file in enumerate(uploaded_files):
        file_type = file.type

        if file_type in ["image/jpeg", "image/png"]:
            st.image(file, caption=f"Aperçu de l'image Contrat {i+1}", use_column_width=True)
            image = Image.open(file)
            text = pytesseract.image_to_string(image)
        else:
            buffer = BytesIO(file.read())
            doc = fitz.open(stream=buffer.read(), filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)

        contract_texts.append(text)

        st.markdown(f"#### 🤖 Analyse IA du Contrat {i+1}")
        prompt = f"Tu es un conseiller expert. Explique ce contrat d'assurance santé ci-dessous avec des mots simples, identifie les points clés, les doublons, et propose des recommandations personnalisées.\n\n{text[:3000]}"
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller en assurance bienveillant."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = response.choices[0].message.content
            st.markdown(analyse, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"⚠️ Erreur IA : {e}")

        msg = EmailMessage()
        msg['Subject'] = f"Analyse contrat santé - Contrat {i+1}"
        msg['From'] = "info@monfideleconseiller.ch"
        msg['To'] = "info@monfideleconseiller.ch"
        msg.set_content("Une analyse IA a été effectuée. Voir fichier en pièce jointe.")
        file.seek(0)
        msg.add_attachment(file.read(), maintype='application', subtype='pdf', filename=f"contrat_{i+1}.pdf")
        try:
            with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
                smtp.login("info@monfideleconseiller.ch", "D4d5d6d9d10@")
                smtp.send_message(msg)
        except Exception as e:
            st.warning(f"📧 Envoi email échoué : {e}")

    st.markdown("### 📊 Comparaison des caisses maladie")
    st.caption("Les scores ci-dessous sont calculés selon vos besoins et les garanties détectées.")
    for i, texte in enumerate(contract_texts):
        st.markdown(f"**Contrat {i+1}**")
        scores = calculer_score_utilisateur(texte, user_objective)
        best = scores[0][0]
        st.success(f"🏆 Recommandation : **{best}** semble le plus adapté à votre profil.")
        for nom, s in scores:
            st.markdown(f"{nom} :")
            st.progress(s / 10)
        st.markdown("---")

    st.success("🎉 Votre analyse est terminée ! N’hésitez pas à nous contacter si vous souhaitez un conseil personnalisé.")

    # Ajout bouton téléchargement PDF analyse IA
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for i, texte in enumerate(contract_texts):
        pdf.multi_cell(0, 10, f"Analyse du Contrat {i+1} :
{text[:1000]}
---")
    buffer = BytesIO()
    pdf.output(buffer)
    b64 = base64.b64encode(buffer.getvalue()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="analyse_contrat.pdf">📥 Télécharger l’analyse IA (PDF)</a>'
    st.markdown(href, unsafe_allow_html=True)

    # Formulaire de contact intégré
    st.markdown("""
    ---
    ### 📞 Demande de contact personnalisée
    Vous souhaitez qu’on vous rappelle ou qu’on vous aide à changer de caisse ?
    Remplissez ce mini formulaire :
    """)
    nom = st.text_input("Nom")
    email = st.text_input("Email")
    message = st.text_area("Votre message")
    if st.button("Envoyer la demande"):
        contact_msg = EmailMessage()
        contact_msg["Subject"] = "Demande contact depuis app IA"
        contact_msg["From"] = email
        contact_msg["To"] = "info@monfideleconseiller.ch"
        contact_msg.set_content(f"Nom: {nom}
Email: {email}
Message:
{message}")
        try:
            with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
                smtp.login("info@monfideleconseiller.ch", "D4d5d6d9d10@")
                smtp.send_message(contact_msg)
            st.success("📩 Votre message a été envoyé avec succès.")
        except Exception as e:
            st.error(f"Erreur d'envoi : {e}")

st.markdown("""
---
### 📫 Une question sur cette application ou l'intelligence qui l'alimente ?
👉 Contactez-nous par email : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)
""")
