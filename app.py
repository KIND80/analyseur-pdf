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
    explications = []
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
                explications.append(f"Doublon interne détecté : la ligne \"{l[:50]}...\" apparaît plusieurs fois dans un même contrat.")
            else:
                seen_internes.add(l)

    for i in range(len(seen_by_file)):
        for j in range(i + 1, len(seen_by_file)):
            doublons = seen_by_file[i].intersection(seen_by_file[j])
            for d in doublons:
                explications.append(f"Doublon entre contrat {i+1} et contrat {j+1} : \"{d[:50]}...\"")
            doublons_detectés.extend(doublons)

    return list(set(doublons_detectés + internes_detectés)), explications

# --- INTERFACE UTILISATEUR ---

st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🧠 Votre Assistant Assurance Santé IA")

st.markdown("""
### 👋 Bienvenue sur votre outil intelligent d'analyse d'assurance !

Cette application vous permet de :
- Lire et comprendre **clairement** vos contrats
- Détecter les **doublons** entre garanties
- Recevoir une **analyse IA personnalisée**
""")

api_key = st.text_input("🔐 Entrez votre clé OpenAI pour continuer", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

objectif = st.radio("🎯 Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("👤 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

uploaded_files = st.file_uploader("📄 Téléversez vos fichiers PDF ou images (JPEG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.markdown("---")
    textes = []
    for i, file in enumerate(uploaded_files):
        st.subheader(f"📘 Contrat {i+1}")
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

    note_globale = 2
    if any("complémentaire" in t.lower() for t in textes):
        note_globale += 3
    if any("hospitalisation" in t.lower() for t in textes):
        note_globale += 1

    st.markdown(f"""
    <div style='background-color:#f4f4f4;padding:1em;border-radius:10px;margin-top:1em;'>
    <strong>Note globale de votre couverture santé :</strong> {note_globale}/10<br>
    <small>Basé sur la présence d'une assurance de base, complémentaire et hospitalisation.</small>
    </div>
    """, unsafe_allow_html=True)

    doublons, explications = detect_doublons(textes)
    if doublons:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
        <h4>🔁 Doublons détectés</h4>
        <p>Nous avons détecté des éléments similaires présents dans plusieurs contrats ou répétés dans un même contrat.</p>
        <ul>""" + "".join(f"<li>{e}</li>" for e in explications) + """</ul>
        <p><strong>Conseil :</strong> Vérifiez si vous payez deux fois pour les mêmes garanties (ex. dentaire, hospitalisation).</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon détecté entre vos contrats")

    st.markdown("---")
    st.subheader("💬 Posez une question à l'assistant IA")
    user_q = st.text_area("Votre question")
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
    st.info("📩 Une question ? Contact : info@monfideleconseiller.ch")
