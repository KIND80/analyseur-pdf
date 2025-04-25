import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from io import BytesIO
from PIL import Image
import pytesseract
import re
import smtplib
from email.message import EmailMessage

# --- Données de référence enrichies pour scoring ---
base_prestations = {
    "Assura": {
        "dentaire": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False,
        "etranger": False, "tarif": 494.8, "franchise": 2500
    },
    "Sanitas": {
        "dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 559.5, "franchise": 2500
    },
    "Visana": {
        "dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 614.1, "franchise": 2500
    },
    "CSS": {
        "dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 563.3, "franchise": 2500
    },
    "Groupe Mutuel": {
        "dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 582.6, "franchise": 2500
    },
    "Helsana": {
        "dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 529.9, "franchise": 2500
    },
    "SWICA": {
        "dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 544.2, "franchise": 2500
    },
    "Sympany": {
        "dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 516.9, "franchise": 2500
    },
    "Concordia": {
        "dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True,
        "etranger": True, "tarif": 536.6, "franchise": 2500
    }
}

# --- Configuration de l'app Streamlit ---
st.set_page_config(page_title="Assistant IA Assurance Santé", layout="centered")

st.title("🧠 Assistant IA - Analyse de vos contrats d’assurance santé")

st.markdown("""
Ce service vous aide à :
- Lire et comprendre **facilement** vos contrats
- Identifier les **doublons** de garanties
- Recevoir une **analyse IA claire et personnalisée**
""")
# Connexion sécurisée à l'API OpenAI via les secrets de Streamlit Cloud
client = OpenAI(api_key=st.secrets["openai_api_key"])

# Objectif de l'utilisateur
objectif = st.radio("🎯 Quel est votre objectif ?", [
    "📉 Réduire les coûts",
    "📈 Améliorer les prestations",
    "❓ Je ne sais pas encore"
])

# Situation professionnelle
travail = st.radio("💼 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

# Téléversement des contrats
uploaded_files = st.file_uploader(
    "📄 Téléversez vos contrats PDF ou photos lisibles (JPG/PNG)",
    type=["pdf", "jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("Veuillez téléverser au moins un contrat pour lancer l'analyse.")
    st.stop()
# Fonction de scoring utilisateur selon ses préférences et les prestations détectées
def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations}

    if "dentaire" in texte:
        for nom in score:
            if base_prestations[nom].get("dentaire", 0) >= 3000:
                score[nom] += 2

    if any(word in texte for word in ["privée", "top liberty", "libero", "flex"]):
        for nom in score:
            if base_prestations[nom].get("hospitalisation", "").lower() in ["privée", "top liberty", "libero", "flex"]:
                score[nom] += 2

    if "médecine alternative" in texte or "médecine naturelle" in texte:
        for nom in score:
            if base_prestations[nom]["médecine"]:
                score[nom] += 1

    if any(word in texte for word in ["check-up", "bilan santé", "fitness"]):
        for nom in score:
            if base_prestations[nom]["checkup"]:
                score[nom] += 1

    if any(word in texte for word in ["étranger", "à l’étranger", "international"]):
        for nom in score:
            if base_prestations[nom]["etranger"]:
                score[nom] += 2

    if preference == "📉 Réduire les coûts":
        sorted_by_tarif = sorted(base_prestations.items(), key=lambda x: x[1].get("tarif", 9999))
        if sorted_by_tarif:
            score[sorted_by_tarif[0][0]] += 3
    elif preference == "📈 Améliorer les prestations":
        for nom in score:
            score[nom] += 1

    return sorted(score.items(), key=lambda x: x[1], reverse=True)

# Détection des doublons entre prestations des contrats
def detect_doublons_par_prestation(textes):
    prestations_reconnues = [
        "dentaire", "orthodontie", "lunettes", "optique", "hospitalisation",
        "privée", "mi-privée", "check-up", "médecine alternative", "étranger", "ambulance"
    ]
    groupes_prestations = []
    explications = []

    for index, texte in enumerate(textes):
        texte_base = texte.lower()
        groupe = set()

        for mot in prestations_reconnues:
            if mot in texte_base:
                groupe.add(mot)

        groupes_prestations.append((index + 1, groupe))

    doublons_intercontrats = []
    for i in range(len(groupes_prestations)):
        for j in range(i + 1, len(groupes_prestations)):
            communs = groupes_prestations[i][1].intersection(groupes_prestations[j][1])
            for c in communs:
                explications.append(
                    f"🔁 Prestation « {c} » présente à la fois dans le contrat {groupes_prestations[i][0]} et le contrat {groupes_prestations[j][0]}"
                )
                doublons_intercontrats.append(c)

    return list(set(doublons_intercontrats)), explications
if uploaded_files:
    contract_texts = []

    for i, file in enumerate(uploaded_files):
        st.subheader(f"📄 Contrat {i+1}")

        if file.type.startswith("image"):
            st.image(file, caption="Aperçu du fichier image")
            image = Image.open(file)
            text = pytesseract.image_to_string(image)
        else:
            buffer = BytesIO(file.read())
            doc = fitz.open(stream=buffer.read(), filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)

        contract_texts.append(text)

    # Détection intelligente des doublons uniquement sur les prestations
    doublons_detectés, explications_doublons = detect_doublons_par_prestation(contract_texts)
    for i, texte in enumerate(contract_texts):
        with st.spinner("🧠 Analyse IA du contrat en cours..."):
            prompt = f"""
Tu es un expert en assurance santé suisse. Analyse ce contrat en 3 sections :
1. LAMal : quels soins sont couverts ? Montants annuels et franchises ?
2. LCA : quelles prestations complémentaires ? Limites ? Exemples (dentaire, lunettes, médecines douces…)
3. Hospitalisation : chambre, libre choix, etc.

Présente les résultats en bullet points, ajoute des remarques si absence de LAMal ou LCA.
Fais une synthèse finale avec une note sur 10 et un conseil.
Voici le contenu du contrat :
{texte[:3000]}
"""
            try:
                reponse = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant IA expert et pédagogue."},
                        {"role": "user", "content": prompt}
                    ]
                )
                resultat = reponse.choices[0].message.content
            except Exception as e:
                st.error(f"Erreur IA : {e}")
                resultat = ""

        # Détection manuelle basique
        has_lamal = "lamal" in texte.lower()
        has_lca = any(m in texte.lower() for m in ["complémentaire", "lca", "lunettes", "dentaire", "médecine alternative"])
        has_hospital = "hospitalisation" in texte.lower() or "chambre" in texte.lower()

        score = 0
        if has_lamal: score += 2
        if has_lca: score += 3
        if has_hospital: score += 1

        st.markdown("---")
        st.markdown(f"""
<div style='background-color:#eaf4ff;padding:1.5em;border-left: 5px solid #007BFF;border-radius:8px;margin-bottom:1em'>
<h3>🔎 Résumé global de l’analyse du contrat {i+1}</h3>
<ul>
    <li><strong>LAMal détectée :</strong> {"✅ Oui" if has_lamal else "<span style='color:red;'>❌ Non</span>"}</li>
    <li><strong>Complémentaire (LCA) détectée :</strong> {"✅ Oui" if has_lca else "<span style='color:red;'>❌ Non</span>"}</li>
    <li><strong>Hospitalisation :</strong> {"✅ Oui" if has_hospital else "<span style='color:red;'>❌ Non</span>"}</li>
</ul>
<p style='font-size: 1.2em;'><strong>Note globale :</strong> {score}/10</p>
<p><em>Conseil :</em> {"Pensez à compléter votre couverture avec une LCA adaptée." if score < 6 else "Votre couverture santé est équilibrée."}</p>
</div>
""", unsafe_allow_html=True)

        st.markdown(f"### 🧾 Détails de l’analyse IA du Contrat {i+1}")
        st.markdown(resultat)
    # Doublons
    if len(contract_texts) > 1 and doublons_detectés:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
        <h4>🔁 Doublons détectés entre les contrats</h4>
        <p>Des prestations similaires ont été repérées dans plusieurs contrats complémentaires :</p>
        <ul>
        """ + "".join([f"<li>{exp}</li>" for exp in explications_doublons]) + """
        </ul>
        <p><strong>Conseil :</strong> Supprimez les redondances pour éviter de payer deux fois pour les mêmes garanties.</p>
        </div>
        """, unsafe_allow_html=True)
    elif len(contract_texts) == 1 and doublons_detectés:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
        <h4>🔁 Doublons internes détectés</h4>
        <p>Certains éléments apparaissent plusieurs fois dans ce contrat, veuillez vérifier :</p>
        <ul>
        """ + "".join([f"<li>{exp}</li>" for exp in explications_doublons]) + """
        </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon significatif détecté entre les contrats analysés.")

    # Chat IA
    st.markdown("---")
    st.subheader("💬 Posez une question à l'assistant IA")
    question_utilisateur = st.text_area("Écrivez votre question ici (ex : Que couvre mon assurance pour les lunettes ?)")
    if st.button("Obtenir une réponse de l’IA"):
        if question_utilisateur:
            try:
                reponse_chat = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en assurance suisse. Donne des réponses claires et personnalisées selon les contrats analysés."},
                        {"role": "user", "content": f"Voici ce que contient mon contrat :\n{contract_texts[0][:2000]}\nEt voici ma question :\n{question_utilisateur}"}
                    ]
                )
                st.markdown("### 🧠 Réponse de l’assistant IA")
                st.markdown(reponse_chat.choices[0].message.content)
            except Exception as e:
                st.error(f"Erreur IA lors de la réponse : {e}")
        else:
            st.warning("Veuillez écrire une question avant de soumettre.")

    # Footer + email
    st.markdown("---")
    st.markdown("📫 Pour toute question : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")

    # Envoi des fichiers
    for i, file in enumerate(uploaded_files):
        try:
            file.seek(0)
            msg = EmailMessage()
            msg["Subject"] = f"Analyse contrat santé - Contrat {i+1}"
            msg["From"] = st.secrets["email_user"]
msg["To"] = st.secrets["email_user"]
msg.set_content("Une analyse IA a été effectuée. Voir fichier en pièce jointe.")
msg.add_attachment(file.read(), maintype='application', subtype='pdf', filename=f"contrat_{i+1}.pdf")

with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
    smtp.login(st.secrets["email_user"], st.secrets["email_password"])
    smtp.send_message(msg)
                smtp.send_message(msg)
        except Exception as e:
            st.warning(f"📨 Erreur lors de l'envoi de l'email pour le contrat {i+1} : {e}")
