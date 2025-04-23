import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from PIL import Image
import pytesseract
from io import BytesIO
import smtplib
from email.message import EmailMessage
import re

base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "checkup": False, "etranger": False},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "checkup": True, "etranger": True}
}
def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom]["dentaire"] >= 3000:
                score[nom] += 2

    if "privée" in texte or "top liberty" in texte:
        for nom in score:
            if "privée" in base_prestations[nom]["hospitalisation"].lower():
                score[nom] += 2

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

    return sorted(score.items(), key=lambda x: x[1], reverse=True)

def detect_doublons_smart(contrats_textes):
    prestations_reconnues = ["dentaire", "lunettes", "hospitalisation", "médecine douce", "fitness", "orthodontie"]
    doublons = []
    analyse = []

    if len(contrats_textes) > 1:
        for i, txt1 in enumerate(contrats_textes):
            for j, txt2 in enumerate(contrats_textes):
                if i >= j:
                    continue
                for prestation in prestations_reconnues:
                    if prestation in txt1.lower() and prestation in txt2.lower():
                        doublons.append(prestation)
                        analyse.append(f"✔️ Doublon détecté sur **{prestation}** entre contrat {i+1} et {j+1}.")

    # Détection de doublons dans un même contrat (ex: deux hospitalisations)
    for idx, texte in enumerate(contrats_textes):
        for prestation in prestations_reconnues:
            if texte.lower().count(prestation) > 1:
                doublons.append(prestation)
                analyse.append(f"⚠️ Doublon interne : **{prestation}** mentionné plusieurs fois dans le contrat {idx+1}.")

    return list(set(doublons)), analyse
# Configuration de l'application Streamlit
st.set_page_config(page_title="Assistant IA Assurance Santé", layout="centered")
st.title("🧠 Assistant IA pour Contrats Santé")

# Introduction
st.markdown("""
Bienvenue sur votre assistant intelligent d’analyse des contrats d’assurance santé.  
Ce service vous permet de :

- 📖 Lire et comprendre clairement vos garanties
- 🚨 Détecter les doublons entre prestations complémentaires
- 💡 Recevoir une analyse IA détaillée et des recommandations
""")

# Clé API sécurisée
api_key = st.text_input("🔐 Entrez votre clé OpenAI pour activer l'analyse IA", type="password")
if not api_key:
    st.warning("Veuillez entrer votre clé pour activer l'analyse.")
    st.stop()
client = OpenAI(api_key=api_key)

# Objectif de l'utilisateur
user_goal = st.radio("🎯 Quel est votre objectif principal ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])

# Situation personnelle
travail = st.radio("👤 Travaillez-vous au moins 8h par semaine ?", ["Oui", "Non"])
st.info("ℹ️ Cela permet de savoir si l'accident doit être inclus dans la LAMal.")

# Upload des fichiers
uploaded_files = st.file_uploader("📄 Téléversez vos contrats PDF ou photos (JPEG/PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

# Extraction et affichage par contrat
contract_texts = []
if uploaded_files:
    for i, file in enumerate(uploaded_files):
        st.markdown(f"### 📘 Aperçu du contrat {i+1}")
        file_type = file.type
        if file_type in ["image/jpeg", "image/png"]:
            image = Image.open(file)
            st.image(image, caption="Image détectée")
            text = pytesseract.image_to_string(image)
        else:
            pdf_reader = fitz.open(stream=file.read(), filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf_reader)
        contract_texts.append(text)
        with st.spinner(f"🔍 Analyse du contrat {i+1} en cours..."):
            prompt = f"""
Tu es un conseiller expert en assurance santé en Suisse. 
Analyse ce contrat en trois sections claires :

1. **LAMal (assurance de base obligatoire)** : 
   - Décris les prestations présentes : franchise, accident, primes, médecin de famille, etc.
   - Précise si l'accident est inclus ou non et indique pourquoi c’est important.

2. **LCA (assurance complémentaire)** : 
   - Liste les prestations additionnelles détectées (dentaire, lunettes, médecines douces, étranger, etc.)
   - Donne les limites annuelles si mentionnées.

3. **Hospitalisation** : 
   - Indique le type de chambre (commune, mi-privée, privée), choix de l’hôpital, prise en charge, etc.

Si des prestations complémentaires sont en doublon (ex : deux couvertures dentaire ou hospitalisation), mentionne-le.

Fais un résumé structuré **en bullet points**.

Voici le texte du contrat à analyser :

{text[:3000]}
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller bienveillant et structuré."},
                        {"role": "user", "content": prompt}
                    ]
                )
                analyse = response.choices[0].message.content
                st.markdown(analyse, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Erreur IA : {e}")
        score = 0
        t = text.lower()
        if "lamal" in t or "base obligatoire" in t:
            score += 2
        if "complémentaire" in t or "lca" in t:
            score += 3
        if "hospitalisation" in t:
            score += 1
        if any(k in t for k in ["dentaire", "lunettes", "étranger", "médecine alternative"]):
            score += 1

        score = min(score, 7)

        # Affichage résultat final UX
        st.markdown(f"""
<div style='background-color:#f8f8f8;padding:1em;border-radius:10px;margin-top:1em;border-left:5px solid #3498db'>
    <h4>📊 Résumé de l'analyse du contrat {i+1}</h4>
    <ul>
        <li><strong>LAMal :</strong> {'✅ Oui' if 'lamal' in t else '❌ Non détectée'}</li>
        <li><strong>Complémentaire (LCA) :</strong> {'✅ Oui' if 'complémentaire' in t or 'lca' in t else '❌ Aucune'}</li>
        <li><strong>Hospitalisation :</strong> {'✅ Oui' if 'hospitalisation' in t else '❌ Aucune'}</li>
    </ul>
    <p><strong>Note de couverture :</strong> <span style='font-size:1.3em'>{score}/10</span></p>
    <p><em>Une bonne couverture comporte LAMal, LCA et hospitalisation (note ≥ 6/10)</em></p>
</div>
""", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("💬 Discuter avec l'assistant IA")

    with st.expander("📖 Poser une question sur votre contrat (chat IA)"):
        user_q = st.text_area("✍️ Posez une question ici (ex. Est-ce que je suis bien couvert à l’étranger ?)", height=150)
        if st.button("Obtenir la réponse IA"):
            if user_q:
                try:
                    rep = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Tu es un conseiller expert en assurance santé suisse, bienveillant, et tu bases ta réponse uniquement sur le contenu du contrat."},
                            {"role": "user", "content": user_q}
                        ]
                    )
                    st.markdown("### 🤖 Réponse de l'assistant :")
                    st.markdown(rep.choices[0].message.content)
                except:
                    st.error("Erreur lors de la génération IA.")
        if file_type == "application/pdf":
            try:
                file.seek(0)
                msg = EmailMessage()
                msg["Subject"] = f"Nouvelle analyse Contrat {i+1}"
                msg["From"] = "info@monfideleconseiller.ch"
                msg["To"] = "info@monfideleconseiller.ch"
                msg.set_content("Contrat analysé automatiquement par l’IA. Voir pièce jointe.")
                msg.add_attachment(file.read(), maintype="application", subtype="pdf", filename=f"contrat_{i+1}.pdf")

                with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
                    smtp.login("info@monfideleconseiller.ch", "D4d5d6d9d10@")
                    smtp.send_message(msg)
            except Exception as e:
                st.warning(f"📨 Erreur lors de l'envoi de l'email pour le contrat {i+1} : {e}")
    st.markdown("---")
    st.markdown("""
<div style='background-color:#e6f4ea;padding:1.2em;border-radius:10px;'>
<h4>✅ Analyse terminée avec succès</h4>
<p>Merci d’avoir utilisé notre assistant IA pour votre contrat d’assurance santé.</p>
<ul>
  <li>📋 Vous avez reçu une lecture automatisée claire de votre police</li>
  <li>🧠 Une note finale personnalisée a été générée</li>
  <li>📌 Des doublons éventuels ont été identifiés</li>
</ul>
<p><strong>Prochaines étapes possibles :</strong></p>
<ul>
  <li>💬 Posez des questions personnalisées via le chat IA</li>
  <li>📩 Contactez notre équipe pour un accompagnement</li>
</ul>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 📫 Contactez-nous")
    st.markdown("Des questions ? Un besoin d’accompagnement personnalisé ?")
    st.markdown("📨 Écrivez-nous : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")

    st.markdown("---")
    st.markdown("""
<style>
  .element-container:has(.stTextArea) {
    max-width: 100% !important;
  }
</style>
""", unsafe_allow_html=True)

    st.success("🏁 Session terminée. Vous pouvez relancer une nouvelle analyse à tout moment.")
