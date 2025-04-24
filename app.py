import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
from io import BytesIO
from PIL import Image
import pytesseract
import re

# Données de référence des cotisations (extraites de Priminfo, simulées ici)
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

# Configuration de la page
st.set_page_config(page_title="Assistant IA Assurance Santé", layout="centered")
st.title("🧠 Assistant IA – Analyse Contrats Santé")

st.markdown("""
Bienvenue dans votre assistant IA pour analyser et optimiser vos contrats santé :

- 📄 Lecture intelligente de votre contrat
- 🔁 Détection des doublons dans les prestations complémentaires
- 🧠 Analyse IA personnalisée
- 📊 Comparaison des prestations si plusieurs contrats
""")
# Saisie de la clé API
api_key = st.text_input("🔐 Entrez votre clé secrète OpenAI pour démarrer l'analyse", type="password")
if not api_key:
    st.warning("Merci d'entrer une clé pour lancer l'analyse.")
    st.stop()

try:
    client = OpenAI(api_key=api_key)
    client.models.list()
except Exception:
    st.error("Clé OpenAI invalide ou expirée. Veuillez vérifier.")
    st.stop()

# Objectif et situation personnelle
objectif = st.radio("🎯 Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"], index=2)
travail = st.radio("👤 Travaillez-vous au moins 8h par semaine ?", ["Oui", "Non"], index=0)

# Téléversement des fichiers
uploaded_files = st.file_uploader("📄 Téléversez jusqu’à 3 contrats PDF ou photos (JPEG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)
if not uploaded_files:
    st.stop()

contract_texts = []
for i, file in enumerate(uploaded_files):
    file_type = file.type
    st.subheader(f"📘 Contrat {i+1}")
    if file_type.startswith("image"):
        st.image(file)
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
    else:
        buffer = BytesIO(file.read())
        doc = fitz.open(stream=buffer.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
    contract_texts.append(text)
# Détection des doublons
doublons_detectés, explications = detect_doublons(contract_texts)

# Affichage des doublons (si plusieurs contrats)
if len(contract_texts) > 1 and doublons_detectés:
    st.markdown("""
    <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
    <h4>🔁 Doublons détectés dans les prestations</h4>
    <p>Nous avons identifié des garanties similaires couvertes dans plusieurs contrats complémentaires.</p>
    <ul>
    """ + "".join([f"<li>{exp}</li>" for exp in explications]) + """
    </ul>
    <p><strong>Conseil :</strong> Comparez les prestations et envisagez une réorganisation pour éviter les surcoûts.</p>
    </div>
    """, unsafe_allow_html=True)
elif len(contract_texts) > 1:
    st.success("✅ Aucun doublon de prestation détecté entre vos contrats.")

# Analyse IA individuelle
notes = []
for idx, texte in enumerate(contract_texts):
    with st.spinner(f"🧠 Analyse IA du contrat {idx+1} en cours..."):
        prompt = f"""
Tu es un conseiller expert en assurance santé en Suisse. Analyse ce contrat en 3 sections :

1. **LAMal** : Est-elle présente ? Quelle est la prime ? Franchise ? Couverture accident ?
2. **LCA** : Quelles prestations complémentaires sont incluses ? Dentaire ? Médecines alternatives ? Lunettes ?
3. **Hospitalisation** : Type de chambre, liberté de choix du médecin ? Couverture spécifique ?

Fais un résumé en **puces**, indique les montants si disponibles, identifie les manques, évalue la couverture sur 10.

Texte à analyser :

{texte[:3000]}
"""
        try:
            res = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller en assurance bienveillant."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = res.choices[0].message.content
            st.markdown(analyse)

            # Calcul de la note globale
            score = 0
            if "lamal" in texte.lower():
                score += 2
            if any(kw in texte.lower() for kw in ["complémentaire", "lca"]):
                score += 3
            if any(kw in texte.lower() for kw in ["hospitalisation", "privée", "mi-privée"]):
                score += 1
            if any(kw in texte.lower() for kw in ["dentaire", "fitness", "lunettes", "étranger"]):
                score += 1
            notes.append(min(score, 7))
        except Exception as e:
            st.warning(f"⚠️ Erreur lors de l'analyse IA : {e}")
# Résumé de l'analyse finale
if notes:
    note_moyenne = sum(notes) // len(notes)
    couleur = "#27ae60" if note_moyenne >= 6 else "#f39c12" if note_moyenne >= 4 else "#c0392b"

    st.markdown(f"""
    <div style='background-color:#f4f4f4;padding:1.5em;border-left:6px solid {couleur};border-radius:10px;margin-top:1em;'>
    <h3 style='margin-bottom:0.5em;'>📊 Résumé global</h3>
    <p style='font-size:1.3em'><strong>Note finale de couverture :</strong> <span style='color:{couleur};'>{note_moyenne}/10</span></p>
    <p><strong>Justification :</strong> Note calculée selon la présence ou absence de LAMal, complémentaire et hospitalisation.</p>
    <p><strong>Conseil :</strong> Une couverture équilibrée comprend LAMal + LCA + Hospitalisation. Ajustez selon vos besoins.</p>
    </div>
    """, unsafe_allow_html=True)

# Message de fin clair
st.markdown("""
<div style='background-color:#e6f4ea;padding:1.2em;border-radius:10px;margin-top:2em;'>
<h4>✅ Analyse terminée avec succès</h4>
<ul>
<li>📋 Lecture automatique de votre/vos contrat(s)</li>
<li>🧠 Évaluation IA complète et neutre</li>
<li>📌 Vérification des prestations doublées (LCA, Hospitalisation)</li>
</ul>
<p><strong>Prochaine étape :</strong> Posez une question ou demandez conseil à notre IA ou à un conseiller humain.</p>
</div>
""", unsafe_allow_html=True)

# Affichage tableau comparatif si >1 contrat
if len(contract_texts) > 1:
    st.markdown("### 🧮 Comparatif entre vos contrats")
    for i, txt in enumerate(contract_texts):
        st.markdown(f"<div style='margin-top:1em;padding:1em;background:#f9f9f9;border-radius:10px;'>", unsafe_allow_html=True)
        st.markdown(f"#### Contrat {i+1}")
        lignes = [l for l in txt.split("\n") if len(l.strip()) > 10]
        st.markdown("<ul>" + "".join(f"<li>{l.strip()}</li>" for l in lignes[:10]) + "</ul>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
# Chat IA pour questions personnalisées
st.markdown("---")
st.subheader("💬 Posez une question à l'assistant IA")
user_q = st.text_area("Votre question ici", placeholder="Ex : Puis-je résilier ce contrat maintenant ?")

if st.button("Obtenir une réponse IA"):
    if user_q.strip():
        try:
            context_global = "\n\n".join([f"Contrat {i+1} : {txt[:1500]}" for i, txt in enumerate(contract_texts)])
            question_prompt = f"""
Tu es un assistant IA spécialisé en assurance santé suisse.
Voici un ou plusieurs extraits de contrats :

{context_global}

L'utilisateur te pose cette question : {user_q}

Si la question concerne une résiliation :
- Indique que la LAMal peut être résiliée chaque année avant le 30 novembre.
- Pour la LCA, explique que c’est souvent 3 ans, sauf si mention différente dans le contrat ou cas spéciaux (sinistre, prime, tranche d'âge).

Réponds avec pédagogie, en langage simple.
"""

            rep = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un assistant expert en assurance santé suisse, bienveillant et pédagogique."},
                    {"role": "user", "content": question_prompt}
                ]
            )
            st.markdown("#### 🧠 Réponse de l’assistant IA")
            st.markdown(rep.choices[0].message.content)
        except Exception as e:
            st.error("❌ Une erreur est survenue lors de la réponse IA.")
    else:
        st.warning("Veuillez entrer une question avant de soumettre.")

# Contact final
st.markdown("---")
st.markdown("📫 Pour toute question : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")
