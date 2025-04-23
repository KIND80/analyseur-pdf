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

# Données de référence des cotisations (complètes avec d'autres caisses)
base_prestations = {
    "Assura": {
        "orthodontie": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False, 
        "etranger": False, "tarif": 250, "franchise": 2500, "mode": "standard"
    },
    "Sympany": {
        "dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True
    },
    "Groupe Mutuel": {
        "dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True
    },
    "Visana": {
        "dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True
    },
    "Concordia": {
        "dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True
    },
    "SWICA": {
        "dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True
    },
    "Helsana": {
        "dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True
    },
    "CSS": {
        "dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True
    },
    "Sanitas": {
        "dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True, 
        "tarif": 390, "franchise": 300, "mode": "modèle HMO"
    }
}

def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        if "5000" in texte or "10000" in texte:
            for nom in score:
                if base_prestations[nom].get("dentaire", 0) >= 5000:
                    score[nom] += 2
        elif "1500" in texte:
            score["Assura"] += 2

    if "privée" in texte or "top liberty" in texte:
        for nom in score:
            if "privée" in base_prestations[nom].get("hospitalisation", "").lower():
                score[nom] += 2

    if "médecine alternative" in texte or "médecine naturelle" in texte:
        for nom in score:
            if base_prestations[nom].get("médecine", False):
                score[nom] += 1

    if "check-up" in texte or "bilan santé" in texte or "fitness" in texte:
        for nom in score:
            if base_prestations[nom].get("checkup", False):
                score[nom] += 1

    if "étranger" in texte or "à l’étranger" in texte:
        for nom in score:
            if base_prestations[nom].get("etranger", False):
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
    internes_detectés = []
    exclusions = [
        "case postale", "axa", "css", "visana", "sympany", "groupe mutuel",
        "concordia", "helsana", "sanitas", "date", "adresse", "contrat",
        "prévoyance", "edition", "police", "rabais", "document", "pdf",
        "conditions", "durée", "n°", "octobre", "janvier"
    ]
    seen_by_file = []

    for texte in texts:
        lignes = [l.strip() for l in texte.lower().split('\n') if len(l.strip()) > 15 and not any(exclu in l for exclu in exclusions)]
        seen_by_file.append(set(lignes))

        # Vérification de doublons internes dans un même contrat
        seen_internes = set()
        for l in lignes:
            if l in seen_internes:
                internes_detectés.append(l)
            else:
                seen_internes.add(l)

    for i in range(len(seen_by_file)):
        for j in range(i + 1, len(seen_by_file)):
            doublons = seen_by_file[i].intersection(seen_by_file[j])
            doublons_detectés.extend(doublons)

    # On retourne les doublons externes + internes
    return list(set(doublons_detectés + internes_detectés))

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
<h4 style='margin-top: 0;'>Analyse IA du Contrat {i+1}</h4>""", unsafe_allow_html=True)

        # prompt pour l'analyse de l'IA
        prompt = f"""Tu es un conseiller expert en assurance santé. Analyse ce contrat en trois parties distinctes :

1. **LAMal (assurance de base obligatoire)** : quelles couvertures essentielles sont présentes ? Indique les montants annuels de prise en charge et les éventuelles franchises.
2. **LCA (assurance complémentaire)** : quelles options ou prestations supplémentaires sont incluses ? Détaille les limites de remboursement (CHF/an ou par traitement) si présentes.
3. **Hospitalisation** : type d'hébergement, libre choix de l'établissement, montant couvert par séjour ou par année.

Voici le texte à analyser :

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
                st.markdown("""<div style='background-color:#fff3cd;border-left: 6px solid #ffa502;padding: 1em;border-radius: 10px;margin-top:1em;'>
                    <h4>⚠️ Doublons détectés</h4><p>Nous avons détecté certaines redondances dans vos contrats.</p></div>""", unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"⚠️ Erreur IA : {e}")
