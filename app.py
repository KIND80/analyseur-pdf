import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI

# 🔧 Configuration de la page
st.set_page_config(page_title="Analyse IA de contrat", layout="centered")
st.title("🧠 Analyse intelligente de contrat d'assurance")

# 🔐 Entrée de la clé API OpenAI
api_key = st.text_input("🔐 Entre ta clé OpenAI :", type="password")
if not api_key:
    st.warning("⚠️ Clé requise pour analyser le contrat.")
    st.stop()

# 🔌 Initialisation du client OpenAI
client = OpenAI(api_key=api_key)

# 📤 Upload du fichier PDF
uploaded_file = st.file_uploader("📄 Téléverse ton contrat PDF", type="pdf")

if uploaded_file:
    # 📖 Extraction du texte du PDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)

    # 🔎 Affichage du texte brut
    with st.expander("📘 Voir le texte extrait du contrat"):
        st.text_area("Contenu du contrat", text, height=300)

    st.subheader("🧠 Analyse IA :")

    with st.spinner("Analyse en cours avec ChatGPT..."):

        # 💬 Prompt structuré pour l’IA
        prompt = f"""
Tu es un expert en assurance santé.

Lis le texte du contrat suivant et génère une analyse **claire, synthétique et structurée** pour un utilisateur **non expert** :

1. 🔍 **Résumé clair** de la couverture principale du contrat
2. ❗️ **Exclusions ou limitations importantes** (en gras)
3. 💡 **Recommandations personnalisées** (ex: faire attention aux franchises élevées, aux exclusions, aux plafonds)
4. ⚖️ **Comparaison** rapide avec les caisses maladie les plus populaires en Suisse (si c’est une assurance suisse), telles que : CSS, Helsana, Groupe Mutuel, Assura.
   - Mentionne si ce contrat semble plus avantageux ou non.
5. ✨ Mets en forme : titres, puces, emojis, **gras** sur les points clés

Voici le texte extrait du contrat :
{text[:5000]}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # ou "gpt-4" si ton compte y a accès
                messages=[
                    {"role": "system", "content": "Tu es un assistant expert en assurance, très pédagogue."},
                    {"role": "user", "content": prompt}
                ]
            )
            output = response.choices[0].message.content

            # ✅ Affichage markdown avec mise en forme
            st.markdown(output, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("📝 *Cette analyse est générée automatiquement à partir du contrat fourni.*")

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
