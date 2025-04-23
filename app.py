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

# --- Données de base pour analyse des caisses ---
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

# --- Scoring personnalisé ---
def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom].get("dentaire", 0) >= 5000:
                score[nom] += 2
        if "1500" in texte:
            score["Assura"] += 1

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

    if "étranger" in texte:
        for nom in score:
            if base_prestations[nom]["etranger"]:
                score[nom] += 2

    if preference == "📉 Réduire les coûts":
        score["Assura"] += 3
    elif preference == "📈 Améliorer les prestations":
        for nom in score:
            score[nom] += 1

    return sorted(score.items(), key=lambda x: x[1], reverse=True)
# --- Détection avancée des doublons ---
def detect_doublons_prestations(texts):
    prestations_keywords = ["dentaire", "orthodontie", "lunettes", "hospitalisation", "médecine", "check-up", "étranger"]
    exclusions = ["accident", "conditions", "édition", "adresse", "famille", "police", "document", "date", "case postale"]
    seen_by_file = []
    doublons_detectés = []
    explications = []

    for idx, texte in enumerate(texts):
        lignes = [l.strip().lower() for l in texte.split('\n') if len(l.strip()) > 10]
        prestations = [l for l in lignes if any(k in l for k in prestations_keywords) and not any(e in l for e in exclusions)]
        seen_by_file.append(set(prestations))

        # Doublons internes
        uniques = set()
        for p in prestations:
            if p in uniques:
                explications.append(f"🔁 Doublon interne dans Contrat {idx+1} : « {p[:60]}... »")
                doublons_detectés.append(p)
            else:
                uniques.add(p)

    # Doublons entre contrats
    for i in range(len(seen_by_file)):
        for j in range(i + 1, len(seen_by_file)):
            communs = seen_by_file[i].intersection(seen_by_file[j])
            for doublon in communs:
                explications.append(f"🔁 Doublon entre Contrat {i+1} et Contrat {j+1} : « {doublon[:60]}... »")
                doublons_detectés.append(doublon)

    return list(set(doublons_detectés)), explications
# --- UI principale ---
st.set_page_config(page_title="Comparateur IA de contrats santé", layout="centered")
st.title("🧠 Assistant Intelligent de Contrats Santé")

st.markdown("""
Ce service vous aide à :
- 📖 Lire clairement vos contrats d'assurance
- 🔎 Détecter les doublons de garanties
- 🤖 Obtenir une analyse intelligente personnalisée
""")

# Étape 1 : Authentification
api_key = st.text_input("🔐 Entrez votre clé OpenAI :", type="password")
if not api_key:
    st.stop()
client = OpenAI(api_key=api_key)

# Étape 2 : Objectif
objectif = st.radio("🎯 Votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"], index=2)

# Étape 3 : Situation
travail = st.radio("👤 Travaillez-vous 8h+/semaine ?", ["Oui", "Non"], index=0)

# Étape 4 : Téléversement des contrats
uploaded_files = st.file_uploader("📄 Téléversez vos fichiers PDF ou photos (max 3)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if not uploaded_files:
    st.info("📂 Veuillez téléverser au moins un contrat.")
    st.stop()

textes_contracts = []
for i, file in enumerate(uploaded_files):
    st.markdown(f"### 📘 Contrat {i+1}")
    if file.type.startswith("image"):
        st.image(file)
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
    else:
        buffer = BytesIO(file.read())
        doc = fitz.open(stream=buffer.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
    textes_contracts.append(text)
    with st.spinner("🧠 Analyse IA en cours..."):
        prompt = f"""Tu es un conseiller expert en assurance santé.
Analyse ce contrat en 3 parties :
1. LAMal : indique si présente ou absente, franchise et remboursement.
2. LCA : prestations complémentaires (dentaire, médecines alternatives, étranger…).
3. Hospitalisation : type de chambre et prestations.

Explique simplement, note la couverture globale sur 10. Voici le texte :

{text[:3000]}"""
        try:
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller assurance bienveillant et synthétique."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = completion.choices[0].message.content
            st.markdown(analyse)

            note = 0
            has_lamal = any(kw in text.lower() for kw in ["lamal", "assurance de base", "obligatoire", "franchise"])
            has_lca = any(kw in text.lower() for kw in ["complémentaire", "dentaire", "lunettes", "médecine alternative"])
            has_hosp = any(kw in text.lower() for kw in ["hospitalisation", "mi-privée", "privée", "chambre"])

            if has_lamal: note += 2
            if has_lca: note += 3
            if has_hosp: note += 2
            if "étranger" in text.lower() or "lunettes" in text.lower(): note += 1
            if note >= 7 and not has_lamal:
                note = 3  # Pas de LAMal = faible couverture malgré les complémentaires

            st.markdown(f"""
<div style='background-color:#eef2f7;padding:1em;border-radius:10px;margin-top:1em;'>
<strong>Note finale :</strong> {note}/10<br>
{"<span style='color:red;'>⚠️ LAMal absente !</span><br>" if not has_lamal else ""}
<span style='font-size:0.9em;'>Une couverture optimale commence à 6/10, incluant LAMal + complémentaire + hospitalisation.</span>
</div>
""", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Erreur d’analyse IA : {e}")
        # Doublons sur les prestations LCA uniquement
        prestations_clés = ["dentaire", "hospitalisation", "lunettes", "alternative", "étranger"]
        resume_prestations = []

        for txt in contract_texts:
            resume_prestations.append({k: any(k in txt.lower() for k in [k]) for k in prestations_clés})

        doublons_detectés = []
        for i in range(len(resume_prestations)):
            for j in range(i + 1, len(resume_prestations)):
                communs = [k for k in prestations_clés if resume_prestations[i][k] and resume_prestations[j][k]]
                if communs:
                    doublons_detectés.append((i + 1, j + 1, communs))

        if doublons_detectés:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("### 🔁 Doublons détectés entre vos contrats :", unsafe_allow_html=True)
            for d in doublons_detectés:
                st.markdown(f"- Contrat {d[0]} et Contrat {d[1]} : **{', '.join(d[2]).capitalize()}**", unsafe_allow_html=True)
            st.info("💡 Pensez à regrouper vos prestations similaires dans une seule assurance complémentaire pour éviter de payer deux fois.")
        else:
            st.success("✅ Aucun doublon détecté sur les prestations complémentaires.")

        # Chat final avec IA
        st.markdown("---")
        st.markdown("### 💬 Posez une question à notre assistant IA")
        question_utilisateur = st.text_area("✍️ Votre question ici (ex : Que puis-je supprimer ? Quelle est ma meilleure couverture ?)")
        if st.button("Obtenir une réponse"):
            if question_utilisateur.strip():
                try:
                    reponse = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Tu es un conseiller en assurance suisse, clair et bienveillant. Tu réponds en fonction du contenu du contrat analysé."},
                            {"role": "user", "content": question_utilisateur}
                        ]
                    )
                    st.markdown("#### 🤖 Réponse IA :", unsafe_allow_html=True)
                    st.markdown(reponse.choices[0].message.content)
                except Exception as e:
                    st.error(f"Erreur lors de la réponse IA : {e}")
            else:
                st.warning("⚠️ Veuillez saisir une question.")

        # Fin
        st.markdown("---")
        st.info("📩 Une question ? Contactez-nous à info@monfideleconseiller.ch")
