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

# Base enrichie avec données Priminfo simulées
base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False, "etranger": False, "tarif": 494.8, "franchise": 2500},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True, "tarif": 563.3, "franchise": 2500},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True, "tarif": 536.6, "franchise": 2500},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True, "tarif": 544.2, "franchise": 2500},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True, "tarif": 559.5, "franchise": 2500},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True, "tarif": 614.1, "franchise": 2500},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True, "tarif": 529.9, "franchise": 2500},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True, "tarif": 516.9, "franchise": 2500},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True, "tarif": 582.6, "franchise": 2500}
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
        score = {k: v + (5 if base_prestations[k]["tarif"] <= 500 else 0) for k, v in score.items()}
    elif preference == "📈 Améliorer les prestations":
        score = {k: v + (2 if base_prestations[k]["dentaire"] > 5000 else 0) for k, v in score.items()}

    return sorted(score.items(), key=lambda x: x[1], reverse=True)

def detect_doublons(texts):
    prestations_keywords = [
        "dentaire", "orthodontie", "lunettes", "hospitalisation", "ambulance",
        "check-up", "médecine alternative", "médecine naturelle",
        "vaccins", "psychothérapie", "étranger", "soins à l’étranger"
    ]

    doublons_detectés = []
    explications = []

    prestations_par_contrat = []

    # Extraction des prestations utiles par contrat
    for texte in texts:
        lignes = texte.lower().split('\n')
        prestations = [
            l.strip() for l in lignes
            if any(kw in l for kw in prestations_keywords) and "accident" not in l
        ]
        prestations_par_contrat.append(prestations)

    # Doublons internes (dans un même contrat)
    for i, prestations in enumerate(prestations_par_contrat):
        deja_vus = set()
        for p in prestations:
            if p in deja_vus:
                doublons_detectés.append(p)
                explications.append(f"🔁 Doublon interne détecté dans le Contrat {i+1} : « {p[:60]}... »")
            else:
                deja_vus.add(p)

    # Doublons externes (entre plusieurs contrats)
    for i in range(len(prestations_par_contrat)):
        for j in range(i + 1, len(prestations_par_contrat)):
            communs = set(prestations_par_contrat[i]).intersection(prestations_par_contrat[j])
            for c in communs:
                doublons_detectés.append(c)
                explications.append(f"🔁 Doublon entre Contrat {i+1} et Contrat {j+1} : « {c[:60]}... »")

    return list(set(doublons_detectés)), explications
# --- INTERFACE UTILISATEUR ---

st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🧠 Assistant IA – Contrats Santé")

st.markdown("""
Bienvenue dans votre assistant intelligent pour l'analyse de vos contrats d'assurance santé !

💡 Ce service vous aide à :
- Comprendre votre contrat plus facilement
- Vérifier les doublons de garanties
- Comparer les prestations et tarifs
- Obtenir des recommandations personnalisées
""")

# Clé API OpenAI
api_key = st.text_input("🔐 Entrez votre clé OpenAI pour lancer l’analyse", type="password")
if not api_key:
    st.info("Veuillez entrer votre clé API pour continuer.")
    st.stop()

try:
    client = OpenAI(api_key=api_key)
    client.models.list()  # vérification simple
except Exception:
    st.error("❌ Clé invalide ou expirée. Merci de vérifier.")
    st.stop()

# Objectif utilisateur
objectif = st.radio("🎯 Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"], index=2)

# Profil utilisateur
travail = st.radio("👤 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)
if travail == "Oui":
    st.info("ℹ️ Si vous êtes salarié, l’assurance accident est souvent déjà incluse par l’employeur. À vérifier dans votre LAMal.")

# Upload fichiers
uploaded_files = st.file_uploader("📄 Téléversez vos contrats PDF ou photos (JPEG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)
if not uploaded_files:
    st.warning("Veuillez téléverser au moins un document pour commencer l'analyse.")
    st.stop()
# --- ANALYSE DES CONTRATS ---

textes = []
for i, file in enumerate(uploaded_files):
    st.markdown(f"---\n### 📄 Contrat {i+1}")
    file_type = file.type

    if file_type.startswith("image/"):
        st.image(file, caption=f"Image Contrat {i+1}", use_column_width=True)
        image = Image.open(file)
        texte = pytesseract.image_to_string(image)
    else:
        buffer = BytesIO(file.read())
        doc = fitz.open(stream=buffer.read(), filetype="pdf")
        texte = "\n".join(page.get_text() for page in doc)

    textes.append(texte)

    with st.spinner("🔍 Analyse IA du contrat en cours..."):
        prompt = f"""Tu es un expert en assurance suisse.
Analyse ce contrat selon ces 3 axes :
1. LAMal : garanties de base, franchise, remboursement accident
2. LCA (complémentaire) : soins dentaire, optique, médecines alternatives, fitness, étranger
3. Hospitalisation : chambre commune, privée, libre choix, montant

Ensuite :
- Identifie les points faibles et manquants
- Estime une note globale sur 10
- Propose une recommandation neutre et claire selon l’objectif : {objectif}

Voici le texte du contrat :

{textes[i][:3000]}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller bienveillant spécialisé en assurance santé suisse."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = response.choices[0].message.content
            st.markdown(analyse, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"❌ Erreur IA : {e}")
# --- SCORING GLOBAL + DOUBLONS ---

note_globale = 2  # LAMal seule par défaut
if any("complémentaire" in t.lower() or "lca" in t.lower() for t in textes):
    note_globale += 3
if any("hospitalisation" in t.lower() or "privée" in t.lower() or "mi-privée" in t.lower() for t in textes):
    note_globale += 1
if any(any(m in t.lower() for m in ["dentaire", "lunettes", "étranger", "fitness"]) for t in textes):
    note_globale = min(7, note_globale + 1)

st.markdown(f"""
<div style='background-color:#f4f4f4;padding:1.5em;border-radius:10px;margin-top:1em;border-left:6px solid #0052cc;'>
  <h3 style='margin-bottom:0.5em;'>🧾 Résultat de votre couverture santé</h3>
  <p style='font-size:1.2em;'><strong>Note obtenue :</strong> {note_globale}/10</p>
  <p style='font-style:italic;'>Une note de 6/10 est conseillée pour être bien couvert (LAMal + LCA + hospitalisation).</p>
  <p>
    {"<strong style='color:#e74c3c;'>Couverture faible :</strong> pensez à compléter votre assurance." if note_globale <= 3 else 
     "<strong style='color:#f1c40f;'>Couverture moyenne :</strong> certaines options peuvent être optimisées." if note_globale <= 5 else 
     "<strong style='color:#2ecc71;'>Bonne couverture :</strong> votre contrat est équilibré."}
  </p>
</div>
""", unsafe_allow_html=True)

# --- DÉTECTION DE DOUBLONS ---
doublons, explications = detect_doublons(textes)
if doublons:
    st.markdown("""
    <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
    <h4>🔁 Doublons détectés</h4>
    <p>Des garanties similaires ont été identifiées dans vos contrats :</p>
    <ul>""" + "".join(f"<li>{e}</li>" for e in explications) + """</ul>
    <p><strong>Conseil :</strong> Vérifiez les prestations (dentaire, hospitalisation, etc.) pour éviter de payer en double.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.success("✅ Aucun doublon détecté entre ou dans vos contrats.")
# --- CHAT IA POUR QUESTIONS PERSONNALISÉES ---
st.markdown("---")
st.subheader("💬 Posez une question à notre assistant IA")
user_question = st.text_area("Posez une question sur vos contrats, prestations, remboursements…")

if st.button("Obtenir une réponse"):
    if user_question:
        try:
            reponse = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller expert en assurance santé suisse, bienveillant, pédagogique et synthétique."},
                    {"role": "user", "content": user_question}
                ]
            )
            st.markdown("### 🧠 Réponse de l’assistant IA")
            st.markdown(reponse.choices[0].message.content)
        except Exception as e:
            st.error("Erreur lors de la réponse IA")
    else:
        st.warning("Veuillez poser une question avant de cliquer.")

# --- MESSAGE DE FIN D’ANALYSE ---
st.markdown("---")
st.markdown("""
<div style='background-color:#e6f4ea;padding:1.2em;border-radius:10px;'>
  <h4>🎉 Analyse terminée avec succès</h4>
  <p>✅ Vous avez obtenu une évaluation claire de vos couvertures santé.<br>
  📌 Vous pouvez maintenant :</p>
  <ul>
    <li>Optimiser votre contrat en fonction de votre profil</li>
    <li>Éviter les doublons inutiles</li>
    <li>Comparer avec d'autres assureurs (sur comparis.ch, priminfo, etc.)</li>
  </ul>
  <p>ℹ️ Pour toute aide : <a href='mailto:info@monfideleconseiller.ch'>info@monfideleconseiller.ch</a></p>
</div>
""", unsafe_allow_html=True)
