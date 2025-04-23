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
# 💡 Ces données pourraient être croisées avec des comparateurs comme comparis.ch ou mes-complementaires.ch pour enrichir l'analyse (prix, franchises, modèles alternatifs, etc.)
base_prestations = {
    "Assura": {"orthodontie": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False, "etranger": False, "tarif": 250, "franchise": 2500, "mode": "standard"},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True, "tarif": 390, "franchise": 300, "mode": "modèle HMO"}
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

def detect_doublons(texts):
    doublons_detectés = []
    seen_phrases = set()
    for i, texte in enumerate(texts):
        lignes = [l.strip() for l in texte.lower().split('
') if l.strip()]
        for ligne in lignes:
            if ligne in seen_phrases:
                doublons_detectés.append(ligne)
            else:
                seen_phrases.add(ligne)
    return list(set(doublons_detectés))

# UI config
st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🤖 Votre Assistant Assurance Santé Intelligent")

st.markdown("""
Ce service a été conçu pour **simplifier la lecture de votre contrat d’assurance santé**, **détecter automatiquement les doublons** entre plusieurs polices et **vous fournir une analyse critique, neutre et structurée**.

Téléversez jusqu'à **3 contrats PDF** ou **photos lisibles** pour bénéficier de :
- Une **lecture intelligente assistée par IA**
- Une **vérification de doublons entre contrats**
- Un **résumé clair de vos couvertures** (LAMal, complémentaire, hospitalisation)
- Des **recommandations personnalisées selon vos besoins**
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

st.markdown("### 👤 Situation personnelle")
travail = st.radio("Travaillez-vous au moins 8h par semaine ?", ["Oui", "Non"], index=0)
st.markdown("ℹ️ Cela permet de savoir si la couverture accident doit être incluse dans la LAMal.")

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

        with st.spinner("🔍 Analyse intelligente du contrat en cours..."):
            st.markdown("<div style='background-color:#f0f9ff;padding:1em;border-radius:10px;margin-top:1em;'>🕵️‍♂️ L’intelligence artificielle analyse maintenant votre contrat, cela peut prendre quelques instants...</div>", unsafe_allow_html=True)
        st.markdown(f"""
<div style='background-color:#f9f9f9;padding: 1em 1.5em;border-radius: 10px;margin-top: 2em;'>
<h4 style='margin-top: 0;'>Analyse IA du Contrat {i+1}</h4>
""", unsafe_allow_html=True)
        # prompt déplacé dans le bloc st.spinner
        prompt = f"""Tu es un conseiller expert en assurance santé. Analyse ce contrat en trois parties distinctes :

1. **LAMal (assurance de base obligatoire)** : quelles couvertures essentielles sont présentes ? Indique les montants annuels de prise en charge et les éventuelles franchises.
2. **LCA (assurance complémentaire)** : quelles options ou prestations supplémentaires sont incluses ? Détaille les limites de remboursement (CHF/an ou par traitement) si présentes.
3. **Hospitalisation** : type d'hébergement, libre choix de l'établissement, montant couvert par séjour ou par année.

Pour chaque section :
- Donne une explication simple

Si aucun élément de LCA n'est détecté dans le contrat, précise que l’utilisateur n’a probablement qu’une assurance de base LAMal. Explique que cela est légalement suffisant mais peu couvrant : par exemple, la LAMal rembourse l’ambulance partiellement (jusqu’à 500 CHF/an), ne couvre pas la chambre privée, ni les médecines alternatives. Conseille d’envisager une LCA adaptée selon ses besoins.
- Liste les garanties et montants associés si disponibles
- Identifie les limites ou doublons
- Fais une recommandation claire adaptée au besoin utilisateur

Voici le texte à analyser :

À la fin de l'analyse, indique une note globale de la couverture santé sur 10 (ex : 6/10 minimum recommandé pour LAMal + LCA + Hospitalisation).

{text[:3000]}"""
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
st.markdown("</div>", unsafe_allow_html=True)
            note = 2  # LAMal par défaut
            if any(word in text.lower() for word in ["complémentaire", "lca"]):
                note += 3
            if any(word in text.lower() for word in ["hospitalisation", "privée", "mi-privée"]):
                note += 1
            if any(word in text.lower() for word in ["dentaire", "fitness", "lunettes", "étranger"]):
                note = min(7, note + 1)
            st.markdown(f"""
<div style='background-color:#f4f4f4;padding: 1.5em;border-radius: 10px;margin-top:1em;border-left: 6px solid #0052cc;'>
    <h3 style='margin-bottom:0.5em;'>Résultat de votre couverture santé</h3>
    <p style='font-size: 1.2em;'><strong>Note obtenue :</strong> {note}/10</p>
    <p style='font-style: italic;'>Une note de 6/10 est recommandée pour une couverture équilibrée incluant assurance de base, complémentaire et hospitalisation.</p>
    <p style='margin-top:1em;'>
        {"<strong style='color:#c0392b;'>Couverture faible :</strong> vous disposez du minimum légal, pensez à compléter votre assurance." if note <= 3 else ("<strong style='color:#f39c12;'>Couverture moyenne :</strong> vous êtes partiellement protégé, certaines options peuvent être envisagées." if note <= 5 else "<strong style='color:#27ae60;'>Bonne couverture :</strong> vous bénéficiez d’une assurance santé équilibrée.")}
    </p>
</div>
""", unsafe_allow_html=True)
            doublons = detect_doublons(contract_texts)
            if doublons:
                st.error("🛑 Doublons potentiels détectés entre vos contrats :")
                st.markdown("<ul style='color:#c0392b;'>" + ''.join([f"<li>{d}</li>" for d in doublons]) + "</ul>", unsafe_allow_html=True)
            else:
                st.success("✅ Aucun doublon détecté dans ce contrat.")
            st.markdown("</div>", unsafe_allow_html=True)
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

    

    st.markdown(
    "<div style='background-color:#e6f4ea;padding:1em;border-radius:10px;'>"
    "<h4>Analyse terminée avec succès</h4>"
    "<p>Vous venez de recevoir une explication claire de votre contrat d’assurance santé, basée sur l’IA. Voici ce que vous pouvez faire maintenant :</p>"
    "<ul>"
    "<li>Consulter les détails de l’analyse ci-dessus</li>"
    "<li>Poser une question complémentaire à l’assistant IA</li>"
    "<li>Demander une recommandation ou un accompagnement personnalisé</li>"
    "</ul>"
    "<p>Nous restons à votre disposition pour toute aide complémentaire.</p>"
    "</div>",
    unsafe_allow_html=True
)

    # Téléchargement désactivé car 'buffer.getvalue()' n'est pas défini ici sans PDF généré.
# Pour réintégrer cette partie, il faut générer le PDF avec FPDF comme avant (sans erreur f-string).

    # Chat interactif intégré
    st.markdown("---")
    st.markdown("### 💬 Posez une question à notre assistant IA")
    question_utilisateur = st.text_area("✍️ Votre question ici")
    if st.button("Obtenir une réponse"):
        if question_utilisateur:
            try:
                reponse = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller expert en assurance santé, clair et bienveillant. Sois synthétique et utile."},
                        {"role": "user", "content": question_utilisateur}
                    ]
                )
                st.markdown("### 🤖 Réponse de l'assistant :")
                st.markdown(reponse.choices[0].message.content, unsafe_allow_html=True)
            except Exception as e:
                st.error("❌ Une erreur est survenue lors de la réponse IA.")
        else:
            st.warning("Veuillez saisir une question avant de cliquer.")

st.markdown("---")
st.markdown("### 📫 Une question sur cette application ou l'intelligence qui l'alimente ?")
st.markdown("Contactez-nous par email : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")
