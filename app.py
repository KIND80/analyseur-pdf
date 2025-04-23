L'outil de création de fichiers est temporairement indisponible, donc je vais te partager le code complet en plusieurs blocs ici pour que tu puisses copier-coller facilement.

Voici le **bloc 1/5** :

```python
# PARTIE 1/5
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
import pandas as pd

# Données enrichies à partir de Priminfo pour comparaison prix LAMal
prix_lamal = {
    "Assura": {300: 614.1, 500: 603.3, 1000: 576.2, 1500: 549.0, 2000: 522.0, 2500: 494.8},
    "CSS": {300: 682.6, 500: 671.8, 1000: 644.7, 1500: 617.5, 2000: 590.5, 2500: 563.3},
    "Concordia": {300: 657.9, 500: 646.9, 1000: 619.3, 1500: 591.7, 2000: 564.2, 2500: 536.6},
    "Helsana": {300: 649.2, 500: 638.4, 1000: 611.2, 1500: 584.1, 2000: 557.0, 2500: 529.9},
    "Sanitas": {300: 678.9, 500: 668.1, 1000: 640.9, 1500: 613.8, 2000: 586.7, 2500: 559.5},
    "Visana": {300: 734.0, 500: 727.8, 1000: 695.9, 1500: 668.6, 2000: 641.4, 2500: 614.1},
    # Ajouter plus de caisses si besoin
}

# Prestations standards enrichies
base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "checkup": False, "etranger": False},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "checkup": True, "etranger": True}
}
# PARTIE 2/5

def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom].get("dentaire", 0) >= 4000:
                score[nom] += 2

    if "privée" in texte or "top liberty" in texte:
        for nom in score:
            if "privée" in base_prestations[nom].get("hospitalisation", "").lower():
                score[nom] += 2

    if "check-up" in texte or "bilan santé" in texte or "fitness" in texte:
        for nom in score:
            if base_prestations[nom].get("checkup", False):
                score[nom] += 1

    if "étranger" in texte or "à l’étranger" in texte:
        for nom in score:
            if base_prestations[nom].get("etranger", False):
                score[nom] += 1

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
                explications.append(f"Doublon interne détecté : \"{l[:50]}...\" dans un même contrat.")
            else:
                seen_internes.add(l)

    for i in range(len(seen_by_file)):
        for j in range(i + 1, len(seen_by_file)):
            doublons = seen_by_file[i].intersection(seen_by_file[j])
            for d in doublons:
                explications.append(f"Doublon entre contrat {i+1} et contrat {j+1} : \"{d[:50]}...\"")
            doublons_detectés.extend(doublons)

    return list(set(doublons_detectés + internes_detectés)), explications
# PARTIE 3/5

st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🧠 Assistant IA – Analyse de vos assurances santé")

st.markdown("""
Bienvenue sur votre outil intelligent d’analyse d’assurance !

**Fonctionnalités :**
- 📑 Lecture claire de vos contrats
- 🔁 Détection des doublons internes et entre contrats
- 🧠 Analyse IA structurée : LAMal, complémentaire, hospitalisation
- 📊 Recommandation basée sur vos préférences
""")

api_key = st.text_input("🔐 Entrez votre clé OpenAI :", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

objectif = st.radio("🎯 Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("👤 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)
st.markdown("ℹ️ Si vous travaillez 8h/semaine ou plus, l'accident est déjà couvert par l'employeur. Vous pouvez retirer cette option dans la LAMal.")

uploaded_files = st.file_uploader("📄 Téléversez vos contrats PDF ou images (JPEG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.markdown("### 🔍 Résultat de l'analyse IA")
    textes = []
    for i, file in enumerate(uploaded_files):
        st.markdown(f"#### 📘 Contrat {i+1}")
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
            prompt = f"""Tu es un conseiller IA expert. Analyse ce contrat santé en 3 parties :

1. LAMal : garanties et franchise, couverture accident.
2. LCA (complémentaire) : remboursements supplémentaires (dentaire, médecines alternatives, etc.).
3. Hospitalisation : type de chambre, libre choix, etc.

Précise si :
- Il y a des doublons dans les garanties (ex. 2x hospitalisation).
- Le contrat est uniquement LAMal.
- Il manque des prestations importantes.
- Le niveau de couverture (note sur 10) et si l'utilisateur pourrait économiser selon son objectif.

Voici le texte à analyser :
{textes[i][:3000]}"""

            try:
                completion = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant IA expert, bienveillant et très clair."},
                        {"role": "user", "content": prompt}
                    ]
                )
                analyse = completion.choices[0].message.content
                st.markdown(analyse)
            except Exception as e:
                st.error(f"Erreur IA : {e}")
    # Calcul de la note globale
    note = 2  # par défaut si LAMal uniquement
    texte_full = " ".join(textes).lower()
    if any(mot in texte_full for mot in ["complémentaire", "lca"]):
        note += 3
    if any(mot in texte_full for mot in ["hospitalisation", "chambre privée", "mi-privée"]):
        note += 1
    if any(mot in texte_full for mot in ["lunettes", "dentaire", "orthodontie", "fitness", "bilan", "étranger"]):
        note = min(7, note + 1)

    st.markdown(f"""
    <div style='background-color:#f4f4f4;padding:1.2em;border-radius:10px;margin-top:1.5em;border-left:5px solid #007ACC;'>
        <h4 style='margin:0;'>🧾 Résumé de votre couverture santé</h4>
        <p><strong>Note IA :</strong> {note}/10</p>
        <p style='font-style:italic;'>Une bonne couverture comprend la LAMal + une complémentaire + hospitalisation.</p>
        <p>
            {"<b style='color:#c0392b;'>Couverture faible</b> : uniquement base. Compléter recommandé." if note <= 3 else
             "<b style='color:#f39c12;'>Couverture moyenne</b> : partiellement couvert." if note <= 5 else
             "<b style='color:#27ae60;'>Bonne couverture</b> : équilibre entre coût et sécurité."}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Détection de doublons
    doublons, explications = detect_doublons(textes)
    if doublons:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1.5em;'>
        <h4>🔁 Doublons détectés</h4>
        <p>Nous avons identifié des redondances entre plusieurs contrats ou à l’intérieur d’un même contrat :</p>
        <ul>""" + "".join(f"<li>{e}</li>" for e in explications) + """</ul>
        <p><strong>Conseil :</strong> Supprimez les doublons pour éviter de payer deux fois pour les mêmes garanties.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon détecté entre vos contrats.")

    # Recommandation coût basée sur priminfo
    if objectif == "📉 Réduire les coûts":
        st.markdown("""
        <div style='background-color:#e6f4ea;padding:1em;border-radius:10px;margin-top:2em;'>
        <h4>💡 Optimisation des coûts (simulation)</h4>
        <p>En fonction des données disponibles (priminfo), certaines caisses offrent des modèles HMO ou Telmed à coût réduit.</p>
        <p><strong>Conseil :</strong> Comparez avec CSS, Assura, KPT, Vivao, et Sana24 selon votre région.</p>
        </div>
        """, unsafe_allow_html=True)
    # Chat IA intégré
    st.markdown("---")
    st.subheader("💬 Posez une question à notre assistant IA")
    user_q = st.text_area("✍️ Votre question ici (par exemple : Que couvre mon contrat pour les soins dentaires ?)")
    if st.button("Obtenir une réponse IA"):
        if user_q.strip():
            try:
                discussion_context = "Voici le contrat de l’utilisateur :\n" + "\n".join(textes)
                rep = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en assurance santé suisse, tu analyses les contrats en toute neutralité. Utilise le contenu du contrat pour répondre."},
                        {"role": "user", "content": discussion_context},
                        {"role": "user", "content": user_q}
                    ]
                )
                st.markdown("### 🤖 Réponse IA")
                st.markdown(rep.choices[0].message.content)
            except Exception as e:
                st.error(f"❌ Une erreur est survenue : {e}")
        else:
            st.warning("Veuillez entrer une question avant de demander une réponse.")

    # Fin
    st.markdown("---")
    st.markdown("### 📩 Une question sur l'application ?")
    st.markdown("Contactez-nous à : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")

