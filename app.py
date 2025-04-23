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
                explications.append(f"🔁 Doublon interne : la ligne \"{l[:50]}...\" apparaît plusieurs fois dans un contrat.")
            else:
                seen_internes.add(l)

    for i in range(len(seen_by_file)):
        for j in range(i + 1, len(seen_by_file)):
            doublons = seen_by_file[i].intersection(seen_by_file[j])
            for d in doublons:
                explications.append(f"🔁 Doublon entre Contrat {i+1} et {j+1} : \"{d[:50]}...\"")
            doublons_detectés.extend(doublons)

    return list(set(doublons_detectés + internes_detectés)), explications


# --- INTERFACE UTILISATEUR ---

st.set_page_config(page_title="Comparateur IA Santé", layout="centered")
st.title("🧠 Assistant IA Assurance Santé")

st.markdown("""
### 👋 Bienvenue !

Analysez vos contrats pour :
- ✅ Lire clairement vos garanties
- 🔁 Identifier les doublons internes et externes
- 💬 Poser vos questions à notre assistant IA
""")

api_key = st.text_input("🔐 Clé OpenAI", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

objectif = st.radio("🎯 Objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("🧍‍♂️ Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

uploaded_files = st.file_uploader("📄 Téléversez vos fichiers PDF ou images (max 3)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

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

        with st.spinner("🔍 Analyse en cours..."):
            prompt = f"""Analyse ce contrat en 3 blocs :
1. LAMal : couverture de base
2. LCA : assurance complémentaire
3. Hospitalisation : type de chambre, libre choix hôpital

Explique simplement. Résume les garanties et indique une note finale.
Texte à analyser :
{textes[i][:3000]}
"""
            try:
                res = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller santé bienveillant et clair."},
                        {"role": "user", "content": prompt}
                    ]
                )
                analyse = res.choices[0].message.content
                st.markdown(analyse)
            except Exception as e:
                st.error(f"Erreur IA : {e}")

    # Note globale
    note = 2
    if any("complémentaire" in t.lower() for t in textes):
        note += 3
    if any("hospitalisation" in t.lower() for t in textes):
        note += 1

    st.markdown(f"""
    <div style='background-color:#eaf4ea;padding:1em;border-left: 6px solid #27ae60;border-radius: 10px;'>
    <strong>✅ Note globale :</strong> {note}/10
    <br><small>6/10 est recommandé pour une bonne couverture (LAMal + LCA + Hospitalisation).</small>
    </div>
    """, unsafe_allow_html=True)

    # Doublons
    doublons, explications = detect_doublons(textes)
    if doublons:
        st.markdown("""
        <div style='background-color:#fff3cd;padding:1em;border-left: 6px solid #f39c12;border-radius: 10px;'>
        <h4>🔁 Doublons détectés</h4>
        <p>Des répétitions ont été trouvées :</p><ul>
        """ + "".join([f"<li>{e}</li>" for e in explications]) + "</ul></div>", unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon détecté")

    # Chat IA
    st.markdown("---")
    st.subheader("💬 Poser une question à l'assistant IA")
    q = st.text_area("Votre question ici")
    if st.button("Obtenir une réponse") and q:
        try:
            r = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un assistant clair et spécialisé en assurance suisse."},
                    {"role": "user", "content": q}
                ]
            )
            st.markdown("### Réponse :")
            st.markdown(r.choices[0].message.content)
        except:
            st.error("❌ Erreur dans la réponse IA.")
