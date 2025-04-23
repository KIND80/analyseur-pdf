import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from io import BytesIO
from PIL import Image
import pytesseract
import re

# Mise à jour de la base des prestations
base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "checkup": False, "etranger": False},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "checkup": True, "etranger": True}
}

def calculer_score_utilisateur(texte, preference):
    texte = texte.lower()
    score = {nom: 0 for nom in base_prestations.keys()}
    has_lamal = "lamal" in texte or "base" in texte

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom]["dentaire"] >= 3000:
                score[nom] += 2

    if "privée" in texte:
        for nom in score:
            if "privée" in base_prestations[nom]["hospitalisation"].lower():
                score[nom] += 2

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

    return sorted(score.items(), key=lambda x: x[1], reverse=True), has_lamal

def detect_doublons_prestations(textes):
    prestations_cle = ["dentaire", "orthodontie", "hospitalisation", "médecine alternative", "lunettes"]
    all_lines = []
    prest_detect = []

    for texte in textes:
        lignes = texte.lower().split('\n')
        prestations = [l for l in lignes if any(p in l for p in prestations_cle)]
        all_lines.append(set(prestations))

    # Comparaison entre contrats
    doublons = set()
    for i in range(len(all_lines)):
        for j in range(i + 1, len(all_lines)):
            doublons.update(all_lines[i].intersection(all_lines[j]))

    return list(doublons)
# --- UI de l'application ---
st.set_page_config(page_title="Analyseur IA - Contrats Santé", layout="centered")
st.title("🧠 Assistant IA pour vos Contrats Santé")

st.markdown("""
Bienvenue dans votre assistant santé intelligent, conçu pour :
- **Détecter les doublons de prestations complémentaires**
- **Analyser la couverture LAMal, LCA et Hospitalisation**
- **Fournir une explication claire, pédagogique et personnalisée**
""")

api_key = st.text_input("Entrez votre clé secrète pour commencer l’analyse :", type="password")
if not api_key:
    st.stop()

try:
    client = OpenAI(api_key=api_key)
    client.models.list()
    st.success("Clé validée. Analyse prête.")
except Exception:
    st.error("Clé invalide. Merci de vérifier.")
    st.stop()

objectif = st.radio("Quel est votre objectif ?", ["📉 Réduire les coûts", "📈 Améliorer les prestations", "❓ Je ne sais pas encore"])
travail = st.radio("Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)
uploaded_files = st.file_uploader("📄 Importez jusqu'à 3 fichiers (PDF / images)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if not uploaded_files:
    st.stop()

st.markdown("---")
contract_texts = []
for i, file in enumerate(uploaded_files):
    st.subheader(f"📄 Contrat {i+1}")
    if file.type.startswith("image"):
        st.image(file, caption="Aperçu du document")
        image = Image.open(file)
        texte = pytesseract.image_to_string(image)
    else:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        texte = "\n".join([page.get_text() for page in doc])
    contract_texts.append(texte)
    with st.spinner("🤖 Analyse IA en cours..."):
        prompt = f"""
Tu es un expert en assurance santé suisse. Voici un contrat à analyser.

Analyse les éléments suivants de façon structurée et pédagogique :
1. **LAMal** : couverture de base, montants, franchises, éléments manquants.
2. **LCA (complémentaire)** : prestations supplémentaires, médecine alternative, remboursement lunettes/dentaire, etc.
3. **Hospitalisation** : type de chambre, liberté de choix, montants.

Indique s'il manque la LAMal (et donc que l’assurance est incomplète).
Explique clairement les garanties détectées sous forme de points, en mettant en évidence les montants importants.
Puis, fournis une note globale sur 10 avec ton raisonnement.

Texte : {texte[:3000]}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un conseiller expert et bienveillant en assurance santé suisse."},
                    {"role": "user", "content": prompt}
                ]
            )
            analyse = response.choices[0].message.content
            st.markdown(analyse, unsafe_allow_html=True)
        except Exception as e:
            st.error("Erreur d’analyse IA")

# -- Score automatique et remarques
note = 0
for txt in contract_texts:
    txt_lower = txt.lower()
    if any(k in txt_lower for k in ["lamal", "base", "obligatoire"]):
        note += 2
    if any(k in txt_lower for k in ["complémentaire", "lca"]):
        note += 3
    if any(k in txt_lower for k in ["hospitalisation", "privée", "demi-privée"]):
        note += 1
    if any(k in txt_lower for k in ["dentaire", "lunettes", "fitness", "médecine alternative"]):
        note += 1

note = min(note, 10)

st.markdown(f"""
<div style='background-color:#f4f4f4;padding:1em;border-radius:10px;margin-top:1em;'>
<h4>🧾 Résultat global de votre couverture</h4>
<p><strong>Note finale :</strong> {note}/10</p>
<p>{'❗️Absence de LAMal détectée : pensez à vérifier votre couverture de base obligatoire.' if note < 3 else '✅ Une couverture est détectée, vérifiez les détails ci-dessus.'}</p>
</div>
""", unsafe_allow_html=True)

# -- Doublons réels sur prestations uniquement
prestations_clés = ["dentaire", "lunettes", "hospitalisation", "médecine", "orthodontie"]
doublons_presta = {}
for p in prestations_clés:
    count = sum(p in c.lower() for c in contract_texts)
    if count > 1:
        doublons_presta[p] = count

if doublons_presta:
    st.markdown("""
<div style='background-color:#fff3cd;border-left: 6px solid #ffa502;padding: 1em;border-radius: 10px;margin-top:1em;'>
<h4>⚠️ Doublons de garanties complémentaires détectés</h4>
<p>Les prestations suivantes apparaissent plusieurs fois :</p>
<ul>""" + "".join(f"<li><strong>{k}</strong> : présente dans {v} contrats</li>" for k, v in doublons_presta.items()) + """</ul>
<p><strong>Recommandation :</strong> Réduisez ou regroupez les couvertures similaires pour éviter de payer en double.</p>
</div>
""", unsafe_allow_html=True)
else:
    st.success("✅ Aucune redondance majeure de prestations complémentaires détectée.")

# -- Chat IA final
st.markdown("---")
st.subheader("💬 Posez vos questions sur vos contrats")
q = st.text_area("Question libre à l’IA")
if st.button("Envoyer"):
    if q:
        try:
            reponse = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu réponds comme un conseiller assurance santé bienveillant et précis."},
                    {"role": "user", "content": q}
                ]
            )
            st.markdown(f"**Réponse IA :**\n\n{reponse.choices[0].message.content}")
        except Exception:
            st.error("Erreur lors de la réponse IA.")
