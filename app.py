import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
from io import BytesIO
from PIL import Image
import pytesseract
import re
import smtplib
from email.message import EmailMessage

# Configuration de la page Streamlit
st.set_page_config(page_title="Assistant IA Assurance Santé", layout="centered")

# Titre principal
st.title("🧠 Assistant IA - Analyse de vos contrats d’assurance santé")

# Description introductive
st.markdown("""
Ce service vous aide à :
- Lire et comprendre **facilement** vos contrats
- Identifier les **doublons** de garanties complémentaires
- Recevoir une **analyse IA claire et personnalisée**
- Poser vos questions à un expert IA assurance
""")

# Message d'avertissement IA
st.info("""
⚠️ **Note** : Cette analyse IA est basée sur des données enrichies et des technologies avancées. 
Elle reste une version bêta. Des erreurs peuvent survenir.

👉 Pour une confirmation ou un conseil personnalisé, contactez-nous : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)
""")

# Bouton WhatsApp flottant via HTML/CSS
st.markdown("""
<style>
.whatsapp-float {
    position: fixed;
    width: 60px;
    height: 60px;
    bottom: 40px;
    right: 20px;
    background-color: #25D366;
    color: white;
    border-radius: 50px;
    text-align: center;
    font-size: 30px;
    z-index: 100;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
}
.whatsapp-icon {
    margin-top: 13px;
}
</style>
<a href="https://wa.me/41797896193" target="_blank">
    <div class="whatsapp-float">
        <div class="whatsapp-icon">💬</div>
    </div>
</a>
""", unsafe_allow_html=True)

# Clé API sécurisée
client = OpenAI(api_key=st.secrets["openai_api_key"])
# Objectif de l'utilisateur
objectif = st.radio("🎯 Quel est votre objectif principal ?", [
    "📉 Réduire les coûts",
    "📈 Améliorer les prestations",
    "❓ Je ne sais pas encore"
])

# Statut professionnel
travail = st.radio("💼 Travaillez-vous au moins 8h/semaine ?", ["Oui", "Non"], index=0)

# Téléversement des fichiers
uploaded_files = st.file_uploader(
    "📂 Téléversez vos contrats (PDF ou images JPG/PNG)",
    type=["pdf", "jpg", "jpeg", "png"],
    accept_multiple_files=True
)
if not uploaded_files:
    st.warning("📤 Merci de téléverser au moins un contrat pour démarrer l’analyse.")
    st.stop()
# Initialisation de la liste des textes extraits
contract_texts = []

# Extraction OCR ou texte selon type de fichier
for i, file in enumerate(uploaded_files):
    st.subheader(f"📑 Contrat {i+1}")
    if file.type.startswith("image"):
        st.image(file, caption=f"Aperçu de l’image {file.name}")
        image = Image.open(file)
        config_ocr = '--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=config_ocr, lang='fra+eng')
    else:
        buffer = BytesIO(file.read())
        doc = fitz.open(stream=buffer.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)

    contract_texts.append(text)
def detect_doublons_par_prestation(textes):
    prestations_reconnues = [
        "dentaire", "orthodontie", "lunettes", "optique",
        "hospitalisation", "privée", "mi-privée", "chambre",
        "check-up", "bilan santé", "médecine alternative",
        "ambulance", "transport", "sauvetage", "étranger"
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
            for prestation in communs:
                explications.append(
                    f"🔁 Prestation « {prestation} » présente à la fois dans le contrat {groupes_prestations[i][0]} et le contrat {groupes_prestations[j][0]}"
                )
                doublons_intercontrats.append(prestation)

    return list(set(doublons_intercontrats)), explications
# --- Analyse IA pour chaque contrat ---
doublons_detectés, explications_doublons = detect_doublons_par_prestation(contract_texts)

for i, texte in enumerate(contract_texts):
    with st.spinner("🧠 Analyse IA du contrat en cours..."):
        prompt = f"""
Tu es un expert en assurance santé suisse. Analyse ce contrat en 3 sections :
1. LAMal : quels soins sont couverts ? Montants annuels et franchises ?
2. LCA : quelles prestations complémentaires ? Exemples (dentaire, lunettes, médecines douces, etc.) ? Limites ?
3. Hospitalisation : type de chambre, choix du médecin ou de l’hôpital, montant maximal remboursé ?

- Présente les garanties **en bullet points clairs**.
- Si une section est absente (ex : pas de LAMal), mentionne-le clairement.
- Fais une synthèse finale avec une **note sur 10** et une **recommandation personnalisée**.
- Sois bienveillant, pédagogique, et évite le jargon.

Voici le contenu du contrat :
{texte[:3000]}
"""
        try:
            reponse = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Tu es un assistant IA expert, bienveillant et pédagogue."},
                    {"role": "user", "content": prompt}
                ]
            )
            resultat = reponse.choices[0].message.content
        except Exception as e:
            st.error(f"Erreur IA : {e}")
            resultat = ""

    st.markdown(f"### 🧾 Détails de l’analyse IA du Contrat {i+1}")
    st.markdown(resultat)

    # Résumé synthétique
    has_lamal = "lamal" in texte.lower()
    has_lca = any(m in texte.lower() for m in ["complémentaire", "lca", "lunettes", "dentaire", "médecine alternative", "orthodontie"])
    has_hospital = "hospitalisation" in texte.lower() or "chambre" in texte.lower()

    score = 0
    if has_lamal: score += 2
    if has_lca: score += 3
    if has_hospital: score += 1

    st.markdown("---")
    st.markdown(f"""
<div style='background-color:#eaf4ff;padding:1.5em;border-left: 5px solid #007BFF;border-radius:8px;margin-bottom:1em'>
<h3>🔍 Résumé global de l’analyse du contrat {i+1}</h3>
<ul>
    <li><strong>LAMal détectée :</strong> {"✅ Oui" if has_lamal else "<span style='color:red;'>❌ Non</span>"}</li>
    <li><strong>Complémentaire (LCA) détectée :</strong> {"✅ Oui" if has_lca else "<span style='color:red;'>❌ Non</span>"}</li>
    <li><strong>Hospitalisation :</strong> {"✅ Oui" if has_hospital else "<span style='color:red;'>❌ Non</span>"}</li>
</ul>
<p style='font-size: 1.3em;'><strong>Note finale :</strong> {score}/10</p>
<p><em>Conseil IA :</em> {"Pensez à compléter votre protection avec une complémentaire ou une meilleure hospitalisation." if score < 6 else "Votre couverture santé semble équilibrée selon les informations lues."}</p>
</div>
""", unsafe_allow_html=True)
# --- Analyse des doublons (après avoir analysé tous les contrats) ---
doublons_detectés, explications_doublons = detect_doublons_par_prestation(contract_texts)

if len(contract_texts) > 1 and doublons_detectés:
    st.markdown("""
    <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
    <h4>🔁 Doublons détectés entre les contrats</h4>
    <p>Des <strong>prestations complémentaires similaires</strong> (LCA) ont été identifiées dans plusieurs contrats :</p>
    <ul>
    """ + "".join([f"<li>{exp}</li>" for exp in explications_doublons]) + """
    </ul>
    <p><strong>Recommandation :</strong> Comparez les plafonds et durées de remboursement. Supprimez les redondances pour éviter de payer deux fois pour le même type de garantie.</p>
    </div>
    """, unsafe_allow_html=True)

elif len(contract_texts) == 1 and doublons_detectés:
    st.markdown("""
    <div style='background-color:#fff3cd;border-left:6px solid #ffa502;padding:1em;border-radius:10px;margin-top:1em;'>
    <h4>♻️ Doublons internes détectés</h4>
    <p>Certains éléments semblent répétés <strong>au sein d’un même contrat</strong>. Cela peut indiquer :</p>
    <ul>
        <li>Des garanties similaires mentionnées plusieurs fois</li>
        <li>Un risque de confusion ou mauvaise interprétation</li>
    </ul>
    <p><strong>Conseil :</strong> Vérifiez si des prestations sont vraiment distinctes ou si certaines font double emploi (ex. deux couvertures dentaire).</p>
    <ul>
    """ + "".join([f"<li>{exp}</li>" for exp in explications_doublons]) + """
    </ul>
    </div>
    """, unsafe_allow_html=True)

else:
    st.success("✅ Aucun doublon significatif détecté entre les contrats analysés.")

    # Interaction IA
    st.markdown("---")
    st.subheader("💬 Posez une question à l'assistant IA")
    question_utilisateur = st.text_area(
        "Écrivez votre question ici (ex : Que couvre mon assurance pour les lunettes ?)"
    )

    if st.button("Obtenir une réponse de l’IA"):
        if question_utilisateur:
            try:
                reponse_chat = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en assurance suisse. Donne des réponses claires, pédagogiques et personnalisées selon les contrats analysés."},
                        {"role": "user", "content": f"Voici ce que contient mon contrat :\n{contract_texts[0][:2000]}\nEt voici ma question :\n{question_utilisateur}"}
                    ]
                )
                st.markdown("### 🧠 Réponse de l’assistant IA")
                st.markdown(reponse_chat.choices[0].message.content)
            except Exception as e:
                st.error(f"Erreur IA lors de la réponse : {e}")
        else:
            st.warning("Veuillez écrire une question avant de soumettre.")
    # Pied de page
    st.markdown("---")
    st.markdown("📫 Pour toute question ou besoin d’assistance humaine : [info@monfideleconseiller.ch](mailto:info@monfideleconseiller.ch)")

    st.markdown("""
    <div style='background-color:#fff3cd;padding:1em;border-left:6px solid #ffc107;border-radius:8px;margin-top:1em;'>
    <strong>ℹ️ Remarque :</strong> Cet outil est une version <strong>bêta</strong>. L’analyse IA repose sur des données contractuelles et des bases internes enrichies, mais il est possible qu’elle ne soit pas parfaite. Nous vous recommandons de consulter un expert pour une validation finale.<br><br>
    👤 Contact recommandé : <strong>Mon Fidèle Conseiller</strong> via <a href="mailto:info@monfideleconseiller.ch">info@monfideleconseiller.ch</a>.
    </div>
    """, unsafe_allow_html=True)
    # Envoi des fichiers analysés par mail
    for i, file in enumerate(uploaded_files):
        try:
            file.seek(0)
            msg = EmailMessage()
            msg["Subject"] = f"Analyse contrat santé - Contrat {i+1}"
            msg["From"] = st.secrets["email_user"]
            msg["To"] = st.secrets["email_user"]
            msg.set_content("Une analyse IA d’un contrat d’assurance a été effectuée. Voir fichier joint.")
            msg.add_attachment(file.read(), maintype='application', subtype='pdf', filename=f"contrat_{i+1}.pdf")

            with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
                smtp.login(st.secrets["email_user"], st.secrets["email_password"])
                smtp.send_message(msg)
        except Exception as e:
            st.warning(f"📨 Erreur lors de l'envoi de l'email pour le contrat {i+1} : {e}")
# --- Bouton WhatsApp flottant toujours visible ---
st.markdown("""
<style>
#whatsapp {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1000;
}

#whatsapp a {
    display: inline-block;
    background-color: #25D366;
    color: white;
    font-size: 20px;
    padding: 12px 15px;
    border-radius: 50px;
    text-decoration: none;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}

#whatsapp a:hover {
    background-color: #128C7E;
}
</style>

<div id="whatsapp">
    <a href="https://wa.me/41797896193" target="_blank">💬 WhatsApp</a>
</div>
""", unsafe_allow_html=True)
# --- Données LCA structurées pour enrichir l'analyse IA ---
base_lca_prestations = {
    "Global Niveau 1": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": None,
        "promotion_sante": "30 CHF/an (0-18 ans uniquement)",
        "medecine_alternative": "70 CHF/séance, max 6000 CHF/an",
        "transport_sauvetage": "60% jusqu’à 1000 CHF",
        "hospitalisation": "Chambre commune",
        "medicaments": "70% jusqu’à 800 CHF (hors-liste)",
        "moyens_auxiliaires": "70 CHF/séance jusqu’à 6000 CHF",
        "dentaire": None,
        "orthodontie": None
    },
    "Global Niveau 2": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": None,
        "promotion_sante": "30 CHF/an (0-18 ans uniquement)",
        "medecine_alternative": "70 CHF/séance, max 6000 CHF/an",
        "transport_sauvetage": "80% jusqu’à 1000 CHF",
        "hospitalisation": "Chambre commune",
        "medicaments": "90% jusqu’à 800 CHF (hors-liste)",
        "moyens_auxiliaires": "70 CHF/séance jusqu’à 6000 CHF",
        "dentaire": None,
        "orthodontie": None
    },
    "Global Niveau 3": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": None,
        "promotion_sante": "30 CHF/an (0-18 ans uniquement)",
        "medecine_alternative": "70 CHF/séance, max 3000 CHF/an",
        "transport_sauvetage": "80% jusqu’à 2500 CHF",
        "hospitalisation": "Mi-privée",
        "medicaments": "90% illimité (hors-liste)",
        "moyens_auxiliaires": "70 CHF/séance jusqu’à 6000 CHF",
        "dentaire": None,
        "orthodontie": None
    },
    "Global Niveau 4": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": None,
        "promotion_sante": "30 CHF/an (0-18 ans uniquement)",
        "medecine_alternative": "70 CHF/séance, max 6000 CHF/an",
        "transport_sauvetage": "80% jusqu’à 5000 CHF",
        "hospitalisation": "Privée",
        "medicaments": "90% illimité (hors-liste)",
        "moyens_auxiliaires": "70 CHF/séance jusqu’à 6000 CHF",
        "dentaire": None,
        "orthodontie": None
    }
}
base_lca_prestations.update({
    "Global Mi-Privé": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": "90% illimité",
        "promotion_sante": "30 CHF/an",
        "medecine_alternative": "70 CHF/séance, max 6000 CHF/an",
        "transport_sauvetage": "80% jusqu’à 5000 CHF",
        "hospitalisation": "Mi-privée (90%)",
        "medicaments": "90% illimité",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Global Privé": {
        "lunettes": None,
        "etranger": "100000 CHF/an (MUNDO)",
        "checkup": "100% illimité",
        "promotion_sante": "30 CHF/an",
        "medecine_alternative": "70 CHF/séance, max 6000 CHF/an",
        "transport_sauvetage": "80% jusqu’à 5000 CHF",
        "hospitalisation": "Privée (90%)",
        "medicaments": "90% illimité",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Global Classic Plus": {
        "lunettes": "150 CHF/3 ans",
        "etranger": None,
        "checkup": "90% tous les 3 ans",
        "promotion_sante": "50% jusqu’à 200 CHF",
        "medecine_alternative": "80% jusqu’à 10000 CHF",
        "transport_sauvetage": "5000 CHF/an",
        "hospitalisation": "Commune Suisse",
        "medicaments": "90% illimité",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    }
})
base_lca_prestations.update({
    "Helsana Top": {
        "lunettes": "90% jusqu’à 150 CHF/an",
        "etranger": "100000 CHF",
        "checkup": "100% max 8 semaines/an",
        "promotion_sante": None,
        "medecine_alternative": "75% jusqu’à 5000 CHF (avec prescription)",
        "transport_sauvetage": None,
        "hospitalisation": "90% jusqu’à 1000 CHF",
        "medicaments": "75% jusqu’à 10000 CHF",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Completa": {
        "lunettes": None,
        "etranger": None,
        "checkup": "90% jusqu’à 300 CHF/an",
        "promotion_sante": "100% illimité",
        "medecine_alternative": "75% jusqu’à 5000 CHF (avec prescription)",
        "transport_sauvetage": "100000 CHF",
        "hospitalisation": "90% jusqu’à 1000 CHF",
        "medicaments": "90% jusqu’à 1500 CHF",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Completa Extra": {
        "lunettes": None,
        "etranger": None,
        "checkup": None,
        "promotion_sante": None,
        "medecine_alternative": "90% jusqu’à 1000 CHF (surplus)",
        "transport_sauvetage": "100% transport, 20000 CHF sauvetage",
        "hospitalisation": "50% jusqu’à 300 CHF/an",
        "medicaments": "90% jusqu’à 500 CHF (surplus)",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    }
})
base_lca_prestations.update({
    "Medna": {
        "lunettes": None,
        "etranger": None,
        "checkup": None,
        "promotion_sante": None,
        "medecine_alternative": "80 CHF/séance, illimité, franchise 200 CHF",
        "transport_sauvetage": None,
        "hospitalisation": None,
        "medicaments": "80% jusqu’à 2000 CHF (Swissmedic)",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Visana": {
        "lunettes": None,
        "etranger": None,
        "checkup": "90% jusqu’à 200 CHF/an enfants, 300 CHF/3 ans adultes",
        "promotion_sante": "100% max 8 semaines/an",
        "medecine_alternative": None,
        "transport_sauvetage": "90% jusqu’à 4000 CHF",
        "hospitalisation": "90% jusqu’à 20000 CHF",
        "medicaments": "90% jusqu’à 1000 CHF",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Diversa": {
        "lunettes": None,
        "etranger": None,
        "checkup": None,
        "promotion_sante": None,
        "medecine_alternative": None,
        "transport_sauvetage": "Illimité transport, 20000 CHF sauvetage",
        "hospitalisation": {
            "Care": "15000 CHF",
            "Plus": "20000 CHF",
            "Premium": "25000 CHF",
            "Diversa": "10000 CHF"
        },
        "medicaments": None,
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    }
})
base_lca_prestations.update({
    "Natura": {
        "lunettes": None,
        "etranger": None,
        "checkup": None,
        "promotion_sante": "90% jusqu’à 500 CHF/an, 50%/200 CHF/sport (max 500 CHF)",
        "medecine_alternative": {
            "Natura": "75% jusqu’à 4000 CHF/an",
            "Natura Plus": "75% jusqu’à 6000 CHF/an"
        },
        "transport_sauvetage": None,
        "hospitalisation": None,
        "medicaments": None,
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Santé Vital": {
        "lunettes": None,
        "etranger": None,
        "checkup": "100% jusqu’à 300 CHF/3 ans",
        "promotion_sante": "100% illimité",
        "medecine_alternative": "80% jusqu’à 500 CHF",
        "transport_sauvetage": None,
        "hospitalisation": "100% illimité / 90% illimité / 50% jusqu’à 10000 CHF avant 20 ans",
        "medicaments": None,
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Sympany Plus": {
        "lunettes": "270 CHF <18 ans, 300 CHF/an adultes",
        "etranger": None,
        "checkup": "100% illimité",
        "promotion_sante": "50% jusqu’à 3000 CHF / 6000 CHF avec Natura",
        "medecine_alternative": None,
        "transport_sauvetage": "100% illimité",
        "hospitalisation": None,
        "medicaments": None,
        "moyens_auxiliaires": "50%/250 CHF pour contrôle, 90% dents de sagesse",
        "dentaire": "70% jusqu’à 10000 CHF jusqu’à 25 ans",
        "orthodontie": None
    },
    "Sympany Premium": {
        "lunettes": "420 CHF <18 ans, 600 CHF/an adultes",
        "etranger": None,
        "checkup": "100% jusqu’à 600 CHF/3 ans",
        "promotion_sante": "80% jusqu’à 1500 CHF",
        "medecine_alternative": "400 CHF/sport jusqu’à 800 CHF",
        "transport_sauvetage": None,
        "hospitalisation": "70% jusqu’à 15000 CHF jusqu’à 25 ans",
        "medicaments": None,
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    },
    "Assura Completa Extra": {
        "lunettes": None,
        "etranger": "100 CHF/an, cumulable jusqu’à 500 CHF",
        "checkup": None,
        "promotion_sante": None,
        "medecine_alternative": "100% transport, 20000 CHF sauvetage",
        "transport_sauvetage": None,
        "hospitalisation": "Division commune en Suisse, plafond 50000 CHF total",
        "medicaments": "1000 CHF/an avec franchise 500 CHF",
        "moyens_auxiliaires": None,
        "dentaire": None,
        "orthodontie": None
    }
})
# --- Bouton WhatsApp flottant ---
whatsapp_html = """
<style>
#whatsapp-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;
}
#whatsapp-btn img {
    width: 60px;
    height: 60px;
}
</style>
<div id="whatsapp-btn">
    <a href="https://wa.me/41797896193" target="_blank" title="Discuter sur WhatsApp">
        <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" alt="WhatsApp Chat">
    </a>
</div>
"""

st.markdown(whatsapp_html, unsafe_allow_html=True)
# --- Avertissement version bêta ---
st.markdown("""
<div style='
    background-color:#fff3cd;
    color:#856404;
    border-left:6px solid #ffcc00;
    padding:1.5em;
    border-radius:10px;
    margin-top:2em;
    font-size:1.05em;
