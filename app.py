import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from fpdf import FPDF
from io import BytesIO
from PIL import Image
import pytesseract
import re

# Données enrichies pour la comparaison
base_prestations = {
    "Assura": {"dentaire": 1500, "hospitalisation": "Mi-privée", "médecine": True, "checkup": False, "etranger": False},
    "Sympany": {"dentaire": 5000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Groupe Mutuel": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Visana": {"dentaire": 8000, "hospitalisation": "Flex", "médecine": True, "checkup": True, "etranger": True},
    "Concordia": {"dentaire": 2000, "hospitalisation": "LIBERO", "médecine": True, "checkup": True, "etranger": True},
    "SWICA": {"dentaire": 3000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Helsana": {"dentaire": 10000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "CSS": {"dentaire": 4000, "hospitalisation": "Privée", "médecine": True, "checkup": True, "etranger": True},
    "Sanitas": {"dentaire": 4000, "hospitalisation": "Top Liberty", "médecine": True, "checkup": True, "etranger": True},
}
def calculer_score_utilisateur(texte_pdf, preference):
    texte = texte_pdf.lower()
    score = {nom: 0 for nom in base_prestations}

    if "lamal" in texte:
        for nom in score:
            score[nom] += 2  # base présente

    if "complémentaire" in texte or "lca" in texte:
        for nom in score:
            score[nom] += 3

    if "hospitalisation" in texte or "privée" in texte or "mi-privée" in texte:
        for nom in score:
            score[nom] += 1

    if any(term in texte for term in ["dentaire", "lunettes", "orthodontie", "fitness"]):
        for nom in score:
            score[nom] += 1

    if "etranger" in texte or "à l’étranger" in texte:
        for nom in score:
            if base_prestations[nom].get("etranger"):
                score[nom] += 1

    if preference == "📉 Réduire les coûts":
        score["Assura"] += 2
    elif preference == "📈 Améliorer les prestations":
        for nom in score:
            score[nom] += 1

    return sorted(score.items(), key=lambda x: x[1], reverse=True)
def detect_doublons_prestations(contrats_textes):
    prestations_reconnues = [
        "dentaire", "orthodontie", "hospitalisation", "lunettes", "médecine naturelle", "médecine alternative",
        "check-up", "fitness", "chambre privée", "soins à l'étranger", "ophtalmologie", "psychothérapie"
    ]

    doublons = []
    contrat_prestations = []

    for texte in contrats_textes:
        texte_lower = texte.lower()
        prestations = [presta for presta in prestations_reconnues if presta in texte_lower]
        contrat_prestations.append(set(prestations))

    for i in range(len(contrat_prestations)):
        for j in range(i + 1, len(contrat_prestations)):
            commun = contrat_prestations[i].intersection(contrat_prestations[j])
            if commun:
                doublons.append({
                    "entre": f"Contrat {i+1} et Contrat {j+1}",
                    "prestations": list(commun)
                })

    return doublons
def generer_feedback_score(note, a_lamal):
    if not a_lamal:
        return """
<div style='background-color:#ffdddd;padding:1em;border-radius:10px;border-left:5px solid red;margin-top:1em;'>
<b>⚠️ Absence de LAMal détectée</b><br>
Vous ne semblez pas avoir d’assurance de base (LAMal), ce qui est pourtant obligatoire en Suisse. Veuillez vérifier auprès de votre assureur ou conseiller.
</div>
"""

    if note <= 3:
        return """
<div style='background-color:#ffe5e5;padding:1em;border-radius:10px;border-left:5px solid #e74c3c;margin-top:1em;'>
<b>Couverture faible :</b> Vous disposez du minimum légal. Pensez à compléter votre assurance avec des prestations complémentaires pour une meilleure protection.
</div>
"""
    elif note <= 5:
        return """
<div style='background-color:#fff3cd;padding:1em;border-radius:10px;border-left:5px solid #f1c40f;margin-top:1em;'>
<b>Couverture moyenne :</b> Vous êtes partiellement protégé. Des options peuvent encore être envisagées selon vos besoins spécifiques.
</div>
"""
    else:
        return """
<div style='background-color:#d4edda;padding:1em;border-radius:10px;border-left:5px solid #28a745;margin-top:1em;'>
<b>Bonne couverture :</b> Vous bénéficiez d’une assurance santé équilibrée incluant base + complémentaires + hospitalisation.
</div>
"""

    # Vérification LAMal
    a_lamal = any("lamal" in t.lower() or "base" in t.lower() for t in textes)
    note_globale = 0
    if a_lamal:
        note_globale += 2
    if any("complémentaire" in t.lower() or "lca" in t.lower() for t in textes):
        note_globale += 3
    if any("hospitalisation" in t.lower() for t in textes):
        note_globale += 1
    if any(mot in t.lower() for t in textes for mot in ["dentaire", "fitness", "lunettes", "étranger"]):
        note_globale += 1
    note_globale = min(7, note_globale)

    st.markdown(f"""
    <div style='background-color:#f4f4f4;padding:1em;border-radius:10px;margin-top:1em;'>
    <strong>🧾 Note globale de votre couverture santé :</strong> {note_globale}/10
    <br><small>Basé sur la présence de LAMal, complémentaire et hospitalisation.</small>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(generer_feedback_score(note_globale, a_lamal), unsafe_allow_html=True)

    doublons, explications = detect_doublons_contenu(textes)
    if explications:
        st.markdown("""
        <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
        <h4>🔁 Doublons détectés</h4>
        <ul>""" + "".join(f"<li>{e}</li>" for e in explications) + """</ul>
        <p><strong>Suggestion :</strong> Vérifiez vos prestations pour éviter de payer deux fois pour la même couverture (ex. dentaire, hospitalisation).</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Aucun doublon critique détecté.")

    # Assistant IA interactif
    st.markdown("---")
    st.subheader("💬 Posez une question à l'IA")
    user_q = st.text_area("Posez une question à propos de votre contrat ou vos droits")
    if st.button("Obtenir une réponse IA"):
        if user_q:
            try:
                rep = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un conseiller IA expert en assurance santé suisse, bienveillant, utile et précis."},
                        {"role": "user", "content": user_q}
                    ]
                )
                st.markdown(rep.choices[0].message.content)
            except Exception as e:
                st.error("Erreur IA : réponse non obtenue.")
        else:
            st.warning("Écrivez une question avant d'envoyer.")

    st.markdown("---")
    st.info("📩 Une question ? Écrivez-nous : info@monfideleconseiller.ch")
