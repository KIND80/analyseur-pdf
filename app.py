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

    return list(set(doublons_detectés + internes_detectés))

# --- INTERFACE UTILISATEUR ---

st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("Votre Assistant Assurance Santé IA")

st.markdown("""
Ce service vous aide à :
- Lire et comprendre vos contrats
- Identifier les **doublons de garanties**
- Recevoir des recommandations **personnalisées**
""")

api_key = st.text_input("Clé API OpenAI", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

objectif = st.radio("Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

uploaded_files = st.file_uploader("Ajoutez vos fichiers PDF ou images", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    textes = []
    for i, file in enumerate(uploaded_files):
        st.subheader(f"Contrat {i+1}")
        if file.type.startswith("image"):
            st.image(file)
            image = Image.open(file)
            texte = pytesseract.image_to_string(image)
        else:
            buffer = BytesIO(file.read())
            doc = fitz.open(stream=buffer.read(), filetype="pdf")
            texte = "\n".join(page.get_text() for page in doc)
        textes.append(texte)

        with st.spinner("Analyse IA en cours..."):
            prompt = f"""Analyse ce contrat en 3 parties :
1. LAMal (base obligatoire)
2. LCA (complémentaire)
3. Hospitalisation
Explique simplement, liste les garanties, note la couverture sur 10.
{textes[i][:3000]}
"""
            try:
                completion = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller en assurance bienveillant."},
                        {"role": "user", "content": prompt}
                    ]
                )
                analyse = completion.choices[0].message.content
                st.markdown(analyse)
            except Exception as e:
                st.error("Erreur IA")

    # Résumé global et détection de doublons
    note_globale = 2
    if any("complémentaire" in t.lower() for t in textes):
        note_globale += 3
    if any("hospitalisation" in t.lower() for t in textes):
        note_globale += 1

    st.markdown(f"**Note globale :** {note_globale}/10")

    doublons = detect_doublons(textes)
    if doublons:
        st.warning("Doublons détectés entre les fichiers ou dans un même contrat :")
        st.markdown("\n".join([f"- {d}" for d in doublons]))
    else:
        st.success("Aucun doublon détecté")

    # Chat avec l'IA
    st.markdown("---")
    st.subheader("Questions complémentaires ?")
    user_q = st.text_area("Posez votre question")
    if st.button("Obtenir une réponse"):
        if user_q:
            try:
                rep = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en assurance suisse, bienveillant."},
                        {"role": "user", "content": user_q}
                    ]
                )
                st.markdown(rep.choices[0].message.content)
            except:
                st.error("Erreur dans la réponse IA")

    st.markdown("---")
    st.info("Une question ? Contact : info@monfideleconseiller.ch")
