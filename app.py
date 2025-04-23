import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from PIL import Image
import pytesseract
from io import BytesIO
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
import re

# Base de prestations par caisse
base_prestations = {
    "Assura": {
        "orthodontie": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False,
        "etranger": False, "tarif": 250, "franchise": 2500, "mode": "standard"
    },
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Sanitas": {
        "dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True,
        "tarif": 390, "franchise": 300, "mode": "modèle HMO"
    }
}

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

# Interface
st.set_page_config(page_title="Assistant Assurance IA", layout="centered")
st.title("🧠 Assistant IA - Analyse de Contrats Santé")

api_key = st.text_input("🔐 Clé OpenAI", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

objectif = st.radio("🎯 Votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("👤 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

uploaded_files = st.file_uploader("📄 Téléversez vos fichiers PDF ou images", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)
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

        with st.spinner("🧠 Analyse IA du contrat en cours..."):
            prompt = f"""Analyse ce contrat en 3 parties distinctes :
1. LAMal (assurance de base obligatoire) : quelles couvertures ? Quelles limites ? Présente les montants.
2. LCA (complémentaire santé) : quelles prestations spécifiques ? Dentaire, lunettes, médecines alternatives, etc.
3. Hospitalisation : quel type d'hébergement ? Couverture cantonale, semi-privée ou privée ?

À la fin, donne une note sur 10 selon la couverture (ex : 2/10 si uniquement LAMal, 6/10 si LAMal+LCA+Hospitalisation).
{textes[i][:3000]}"""

            try:
                rep = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un expert en assurance santé suisse. Sois clair, neutre et professionnel."},
                        {"role": "user", "content": prompt}
                    ]
                )
                analyse = rep.choices[0].message.content
                st.markdown(analyse)
            except Exception as e:
                st.error("⚠️ Erreur IA : " + str(e))

    note = 0
    if any("lamal" in t.lower() for t in textes):
        note += 2
    if any("complémentaire" in t.lower() or "lca" in t.lower() for t in textes):
        note += 3
    if any("hospitalisation" in t.lower() or "privée" in t.lower() for t in textes):
        note += 1
    if any(word in t.lower() for t in textes for word in ["dentaire", "fitness", "lunettes", "médecine alternative", "étranger"]):
        note += 1
    note = min(note, 7)

    st.markdown(f"""
    <div style='background-color:#f0f4f7;padding:1em;border-radius:10px;margin-top:1em;'>
        <h4>📊 Résultat global</h4>
        <p><strong>Note IA :</strong> {note}/10</p>
        <p>{"✅ Bonne couverture santé." if note >= 6 else "⚠️ Couverture partielle détectée, des optimisations sont possibles."}</p>
    </div>
    """, unsafe_allow_html=True)

    doublons, explications = detect_doublons(textes)
    if doublons:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
            <h4>🔁 Doublons détectés</h4>
            <p>Des éléments redondants ont été repérés :</p>
            <ul>""" + "".join(f"<li>{e}</li>" for e in explications) + """</ul>
            <p><strong>Conseil :</strong> Vérifiez si vous êtes doublement couvert pour une même prestation (ex. dentaire, hospitalisation).</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon détecté entre les contrats analysés.")
    # Questions supplémentaires à l'IA
    st.markdown("---")
    st.subheader("💬 Posez une question à l'assistant IA")
    user_q = st.text_area("Votre question en lien avec vos contrats ou votre situation", height=150, placeholder="Exemple : Est-ce que ma couverture dentaire est suffisante ?")

    if st.button("Obtenir une réponse IA"):
        if user_q:
            try:
                context_prompt = "\n\n".join([f"Contrat {i+1} :\n{textes[i][:2000]}" for i in range(len(textes))])
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en assurance suisse, bienveillant et synthétique. Utilise uniquement les infos du contrat fourni si possible."},
                        {"role": "user", "content": f"{context_prompt}\n\nQuestion : {user_q}"}
                    ]
                )
                st.markdown("### 🤖 Réponse de l'assistant :")
                st.markdown(response.choices[0].message.content)
            except Exception as e:
                st.error(f"❌ Erreur de réponse IA : {e}")
        else:
            st.warning("Veuillez écrire une question avant de lancer la réponse.")

    # Fin
    st.markdown("---")
    st.info("📫 Une question ? Contactez-nous à info@monfideleconseiller.ch")
