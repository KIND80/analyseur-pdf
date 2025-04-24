# Bloc 1 : Imports et Données de référence
import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from PIL import Image
import pytesseract
from io import BytesIO
import re
from email.message import EmailMessage
import smtplib

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
# Bloc 2 : Calcul du score utilisateur et détection des doublons utiles

def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations.keys()}

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom].get("dentaire", 0) >= 3000:
                score[nom] += 2

    if "orthodontie" in texte or "orthodentie" in texte:
        for nom in score:
            if base_prestations[nom].get("orthodontie", 0) > 0:
                score[nom] += 1

    if "privée" in texte or "top liberty" in texte or "flex" in texte:
        for nom in score:
            if "privée" in base_prestations[nom]["hospitalisation"].lower() or "flex" in base_prestations[nom]["hospitalisation"].lower():
                score[nom] += 2

    if "médecine alternative" in texte or "naturelle" in texte:
        for nom in score:
            if base_prestations[nom]["médecine"]:
                score[nom] += 1

    if "check-up" in texte or "fitness" in texte:
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

def detect_doublons_prestations(texts):
    mots_cles = ["dentaire", "hospitalisation", "médecine", "lunettes", "check-up", "chambre privée", "étranger"]
    doublons = []
    details = []

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            for mot in mots_cles:
                if mot in texts[i].lower() and mot in texts[j].lower():
                    doublons.append(mot)
                    details.append(f"🔁 Prestation '{mot}' détectée à la fois dans le contrat {i+1} et {j+1}")

    return list(set(doublons)), details
# Bloc 3 : Interface utilisateur - Configuration et saisies

# Configuration Streamlit
st.set_page_config(page_title="Assistant IA Assurance Santé", layout="centered")
st.title("🧠 Assistant IA - Contrat Santé")

st.markdown("""
Bienvenue sur notre assistant intelligent d'analyse de contrat d'assurance santé. 
Téléversez votre/vos contrat(s) pour une analyse claire, détecter les doublons de prestations, 
et recevoir une recommandation personnalisée.
""")

# Étape 1 : Clé API OpenAI
api_key = st.text_input("🔐 Entrez votre clé OpenAI pour démarrer l’analyse", type="password")
if not api_key:
    st.warning("Merci d'entrer votre clé pour continuer.")
    st.stop()
client = OpenAI(api_key=api_key)

# Étape 2 : Objectif utilisateur
objectif = st.radio("🎯 Quel est votre objectif ?", 
                    ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"], 
                    index=2)

# Étape 3 : Situation personnelle
travail = st.radio("👤 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"])
st.markdown("ℹ️ Cette information est utilisée pour analyser si vous devez inclure l'accident dans la LAMal.")

# Étape 4 : Téléversement des contrats
uploaded_files = st.file_uploader("📄 Téléversez vos fichiers PDF ou images (JPEG, PNG)", 
                                  type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Veuillez importer un ou plusieurs contrats pour lancer l’analyse.")
    st.stop()
# Bloc 4 : Traitement des contrats + analyse IA + scoring et affichage

contract_texts = []
for i, file in enumerate(uploaded_files):
    st.markdown(f"---\n### 📘 Contrat {i+1}")
    file_type = file.type

    if file_type.startswith("image"):
        st.image(file, caption="Aperçu image", use_column_width=True)
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
    else:
        buffer = BytesIO(file.read())
        doc = fitz.open(stream=buffer.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)

    contract_texts.append(text)

    with st.spinner("🔍 Analyse IA du contrat en cours..."):
        prompt = f"""
Tu es un expert en assurance santé. Analyse le contrat en 3 parties :
1. LAMal (base) : quelles garanties ? montant ? franchise ?
2. Complémentaire (LCA) : quels ajouts ? lunettes, dentaire, médecines, check-up ?
3. Hospitalisation : type (commune, privée), montant, choix médecin.

Détaille chaque point avec des puces, mets les montants ou limites en **gras**, 
et précise s’il manque la LAMal (⚠️ obligatoire).

Voici le texte du contrat : 
{text[:3000]}
"""
        try:
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un assistant expert en assurance santé suisse."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = completion.choices[0].message.content
        except Exception as e:
            st.error(f"❌ Erreur durant l’analyse IA : {e}")
            analyse = ""

    st.markdown("### 📄 Résultat de l’analyse IA", unsafe_allow_html=True)
    st.markdown(analyse, unsafe_allow_html=True)

    # Score global basé sur présence des modules
    note = 0
    if "lamal" in text.lower():
        note += 2
    else:
        st.warning("⚠️ Aucun élément LAMal détecté. Cela pourrait être problématique.")
    if any(k in text.lower() for k in ["complémentaire", "lca", "lunettes", "dentaire"]):
        note += 3
    if any(k in text.lower() for k in ["hospitalisation", "privée", "mi-privée"]):
        note += 2
    if any(k in text.lower() for k in ["étranger", "check-up", "fitness"]):
        note += 1
    note = min(7, note)

    st.markdown(f"""
    <div style='background-color:#f8f9fa;padding:1em;border-radius:10px;border-left:6px solid #007bff;margin-top:1em;'>
    <h4>📊 Résumé de l’analyse du contrat {i+1}</h4>
    <ul>
        <li><strong>Note globale : {note}/10</strong></li>
        <li><strong>LAMal détectée :</strong> {"✅" if "lamal" in text.lower() else "❌ Non trouvée"}</li>
        <li><strong>Complémentaire (LCA) :</strong> {"✅" if "complémentaire" in text.lower() or "lca" in text.lower() else "❌ Non trouvée"}</li>
        <li><strong>Hospitalisation :</strong> {"✅" if "hospitalisation" in text.lower() else "❌ Non trouvée"}</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

# Analyse des doublons entre contrats
if len(contract_texts) > 1:
    doublons, explications = detect_doublons(contract_texts)
    if doublons:
        st.markdown("""
        <div style='background-color:#fff3cd;padding:1em;border-left:6px solid #ffc107;margin-top:1em;border-radius:10px;'>
        <h4>🔁 Doublons de prestations détectés</h4>
        <p>Des prestations similaires (dentaire, hospitalisation...) semblent présentes dans plusieurs contrats.</p>
        <ul>
        """ + "".join(f"<li>{e}</li>" for e in explications) + """
        </ul>
        <p><strong>Conseil :</strong> Vérifiez si vous êtes couvert plusieurs fois pour le même besoin.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon de prestations détecté entre les contrats.")
# Bloc 5 : Chat IA + Feedback final + Contact

st.markdown("---")
st.markdown("### 💬 Posez vos questions à notre assistant IA")

question_utilisateur = st.text_area("✍️ Entrez ici votre question sur votre contrat ou vos garanties")

if st.button("Obtenir une réponse de l'IA") and question_utilisateur:
    try:
        reponse = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en assurance santé suisse. Donne des réponses simples, fiables et utiles."},
                {"role": "user", "content": question_utilisateur}
            ]
        )
        st.markdown("### 🤖 Réponse IA :", unsafe_allow_html=True)
        st.markdown(reponse.choices[0].message.content, unsafe_allow_html=True)
    except Exception as e:
        st.error("❌ Une erreur est survenue lors de la réponse IA.")
elif not question_utilisateur:
    st.info("💡 Entrez votre question ci-dessus pour démarrer une discussion avec l'assistant IA.")

st.markdown("---")
st.markdown("""
<div style='background-color:#e6f4ea;padding:1.2em;border-radius:10px;'>
    <h4>✅ Analyse terminée avec succès</h4>
    <p>Merci d’avoir utilisé notre assistant IA pour analyser vos contrats santé.</p>
    <ul>
        <li>📋 Vous avez reçu une lecture automatisée claire de votre police</li>
        <li>🧠 Une note finale personnalisée a été générée</li>
        <li>🔁 Des doublons éventuels de prestations ont été identifiés</li>
    </ul>
    <p>👉 Prochaines étapes possibles :</p>
    <ul>
        <li>💬 Poser vos questions ci-dessus via le chat IA</li>
        <li>📩 Contacter notre équipe pour une recommandation personnalisée</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 📫 Besoin d’aide ou d’un conseil humain ?")
st.markdown("Contactez-nous par email : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")
