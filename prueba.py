import streamlit as st
import base64
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date
import json
import time
import io
import smtplib
from email.mime.text import MIMEText
import random
import secrets as secrets_module
import urllib.parse
import requests
import speech_recognition as sr
from gtts import gTTS
from audio_recorder_streamlit import audio_recorder
import os
import logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURACIÓN DE LLAVES Y FIREBASE ---
API_KEY_FREE = st.secrets["GEMINI_API_KEY"]

@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        firebase_credentials = json.loads(st.secrets["FIREBASE_KEY"])
        cred = credentials.Certificate(firebase_credentials)
        firebase_admin.initialize_app(cred)
    return firestore.client()

@st.cache_resource
def init_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

db = init_firebase()

# Orden de modelos: el último exitoso se intenta primero
MODELOS_GEMINI = ['gemini-2.0-flash-lite', 'gemini-2.0-flash', 'gemini-1.5-flash-8b']

# --- 2. CONFIGURACIÓN DE PÁGINA Y DISEÑO CSS ---
icono_pagina = "logo.png" if os.path.exists("logo.png") else "🎙️"
st.set_page_config(page_title="Voxis AI", page_icon=icono_pagina, layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

    /* BASE */
    html, body, .stApp { background-color:#0A0E1A !important; font-family:'Inter',sans-serif !important; }
    [data-testid="stHeader"]  { display:none !important; }
    [data-testid="stToolbar"] { display:none !important; }
    footer { display:none !important; }
    .block-container { padding-top:0 !important; margin-top:-45px !important; padding-bottom:80px !important; max-width:480px !important; }

    /* TYPOGRAPHY */
    p, span, label { color:#C9D0E0 !important; font-family:'Inter',sans-serif !important; }
    h1,h2,h3 { color:#FFFFFF !important; font-family:'Inter',sans-serif !important; margin-top:0 !important; margin-bottom:0.2rem !important; }
    hr { margin:0.4rem 0 !important; border-color:#1E2A45 !important; }
    .stCaption { color:#7A84A0 !important; }

    /* PILL TABS */
    div[data-baseweb="tab-list"] {
        background:#12192E !important; border-radius:100px !important;
        padding:4px !important; gap:2px !important;
        border:none !important; border-bottom:none !important; margin:8px 0 12px 0 !important;
    }
    div[data-baseweb="tab-highlight"] { display:none !important; }
    div[data-baseweb="tab-border"]    { display:none !important; }
    button[data-baseweb="tab"] {
        background:transparent !important; border:none !important; border-radius:100px !important;
        color:#7A84A0 !important; font-size:0.82rem !important; font-weight:600 !important;
        padding:7px 14px !important; transition:all 0.25s ease !important; flex:1 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background:linear-gradient(135deg,#FF7F50,#E05020) !important;
        color:#FFFFFF !important; box-shadow:0 2px 12px rgba(255,127,80,0.45) !important;
    }
    button[data-baseweb="tab"] p { color:inherit !important; font-size:0.82rem !important; font-weight:600 !important; margin:0 !important; }

    /* BUTTONS */
    .stButton>button, .stFormSubmitButton>button {
        background:linear-gradient(135deg,#FF7F50,#E0693E);
        color:white; border-radius:12px; border:none; font-weight:700; font-size:0.95rem;
        padding:10px 20px; transition:all 0.2s ease; font-family:'Inter',sans-serif;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        background:linear-gradient(135deg,#E0693E,#C0552A); color:white;
        transform:translateY(-1px); box-shadow:0 6px 20px rgba(255,127,80,0.4);
    }

    /* CARDS */
    .modern-card { background:#131929; border-radius:16px; padding:20px; box-shadow:0 4px 20px rgba(0,0,0,0.4); margin-bottom:14px; border:1px solid #1E2A45; }

    /* AUDIO RECORDER */
    div[data-testid="stAudioRecorder"] {
        display:flex !important; justify-content:center !important;
        transform:scale(1.8) !important; margin:10px auto !important;
        filter:drop-shadow(0 0 24px rgba(255,127,80,0.65)) !important;
    }
    [data-testid="stCustomComponentV1"] { background:#0A0E1A !important; border:none !important; overflow:hidden !important; }
    /* Clip audio recorder to circle using wrapper */
    .mic-glow-wrapper [data-testid="stCustomComponentV1"] {
        width:72px !important; height:72px !important;
        min-width:72px !important; min-height:72px !important;
        border-radius:50% !important; overflow:hidden !important;
        margin:0 auto !important;
    }
    .mic-glow-wrapper [data-testid="stCustomComponentV1"] iframe {
        width:72px !important; height:72px !important;
        border-radius:50% !important;
    }
    iframe[title="audio_recorder.audio_recorder"] { background:#0A0E1A !important; border:none !important; }

    /* MIC GLOW */
    .mic-glow-section { text-align:center; padding:16px 0 8px 0; }
    .mic-label { font-size:0.95rem; color:#CBD5E0; margin-bottom:8px; }
    .mic-glow-wrapper { position:relative; width:200px; height:120px; margin:0 auto; display:flex; align-items:center; justify-content:center; }
    .mic-glow-wrapper::before {
        content:''; position:absolute; width:140px; height:140px;
        background:radial-gradient(circle,rgba(255,100,50,0.5) 0%,rgba(255,127,80,0.2) 45%,transparent 70%);
        border-radius:50%; animation:mic-pulse 2.5s ease-in-out infinite;
        pointer-events:none; top:-10px; left:30px;
    }
    @keyframes mic-pulse { 0%,100%{ transform:scale(1); opacity:0.9; } 50%{ transform:scale(1.3); opacity:0.3; } }
    .mic-sublabel { font-size:0.82rem; color:#7A84A0; margin-top:8px; }

    /* LESSON CARDS */
    .lesson-card-active { background:#1A2845; border-left:3px solid #FF7F50; border-radius:10px; padding:12px 16px; margin:5px 0; color:#FFFFFF; font-weight:600; }
    .lesson-card-done   { background:#0E1520; border-radius:10px; padding:12px 16px; margin:5px 0; color:#3A4560; }
    .lesson-card-locked { background:#0A1018; border-radius:10px; padding:12px 16px; margin:5px 0; color:#2A3040; }

    /* PLAN CARDS */
    .plan-card-free { background:#111827; border:1px solid #374151; border-radius:16px; padding:18px 20px; margin:10px 0; }
    .plan-card-std  { background:#1A2540; border:2px solid #FF7F50; border-radius:16px; padding:18px 20px; margin:10px 0; box-shadow:0 0 16px rgba(255,127,80,0.15); }
    .plan-card-pro  { background:#1A2030; border:2px solid #FFB347; border-radius:16px; padding:18px 20px; margin:10px 0; box-shadow:0 0 16px rgba(255,179,71,0.15); }

    /* METRICS / ALERTS / INPUTS / SELECT */
    div[data-testid="stMetric"] { text-align:center !important; background:#131929; border-radius:10px; padding:10px; border:1px solid #1E2A45; }
    div[data-testid="stMetricValue"] { display:flex; justify-content:center; color:#FF7F50 !important; font-weight:bold; }
    .stAlert { border-radius:10px !important; border-left:4px solid #FF7F50 !important; background:#131929 !important; }
    .stTextInput>div>div>input { background:#1E2A45 !important; color:#E8EAF0 !important; border-radius:10px !important; border:1px solid #2E3F5C !important; }
    .stSelectbox>div>div { background:#1E2A45 !important; border-color:#2E3F5C !important; }
    .stSelectbox svg { fill:#C9D0E0 !important; }
    .stSelectbox [data-baseweb="select"] span { color:#E8EAF0 !important; }
    div[data-testid="stSelectbox"] div { color:#E8EAF0 !important; }
    [data-baseweb="option"] { background:#1E2A45 !important; color:#E8EAF0 !important; }
    [data-baseweb="menu"]   { background:#1E2A45 !important; }
    .stRadio label, .stCheckbox label { color:#C9D0E0 !important; }
    .stProgress>div>div>div { background:linear-gradient(90deg,#FF7F50,#FF9E7E) !important; border-radius:10px; }
    .stProgress>div>div { background:#1E2A45 !important; border-radius:10px; }

    /* EXPANDERS */
    details { background:#131929 !important; border-color:#1E2A45 !important; border-radius:10px !important; }
    summary { color:#C9D0E0 !important; }
    [data-testid="stExpanderToggleIcon"] { display:none !important; }
    details summary>div>div:first-child { width:0 !important; overflow:hidden !important; font-size:0 !important; }

    /* GOOGLE BTN */
    .google-btn { display:flex; align-items:center; justify-content:center; gap:10px; background:#1E2A45; color:#E8EAF0 !important; padding:12px 20px; border-radius:10px; text-decoration:none; border:1px solid #2E3F5C; font-weight:600; font-size:0.95rem; transition:all 0.2s ease; margin-bottom:10px; width:100%; cursor:pointer; box-sizing:border-box; }
    .google-btn:hover { background:#2E3F5C; border-color:#FF7F50; color:white !important; }

    /* MISC */
    .divider-text { text-align:center; color:#7A84A0; margin:8px 0; font-size:0.85rem; }
    [data-testid="stColumn"] [data-testid="stMarkdownContainer"] p { word-break:break-word; overflow-wrap:break-word; white-space:normal; }
    button[data-testid="stPopoverButton"] span:not(:first-child) { display:none !important; }
    button[data-testid="stPopoverButton"] [data-testid="stMarkdownContainer"] { display:none !important; }
    /* Hide material icon text in expander/popover */
    .material-symbols-rounded { font-size:0 !important; width:0 !important; overflow:hidden !important; }
    /* Streamlit expander toggle arrow text */
    [data-testid="stExpander"] summary > div > div:first-child svg { display:none !important; }
    [data-testid="stExpander"] details > summary > div > div:first-child { display:none !important; }
    /* Force hide expand_more / expand_less chars in buttons */
    button[data-testid="stPopoverButton"] > div:last-child { display:none !important; }
    button[data-testid="stPopoverButton"] { overflow:hidden !important; max-width:46px !important; min-width:0 !important; padding:4px 8px !important; border-radius:8px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DICCIONARIO MULTILINGÜE COMPLETO ---
UI_TEXT = {
    "Español": {"native_lang": "🗣️ Idioma Nativo:", "record_btn": "🎙️ Grabar (Max {}s)", "login_sub": "Identifícate para comenzar.", "email": "Correo:", "names": "Nombres:", "lastnames": "Apellidos:", "wa": "WhatsApp:", "plan_select": "Elige tu plan inicial:", "btn_login": "Entrar / Registrarse", "btn_google": "Continuar con Google", "greeting": "Hola", "plan_label": "Plan actual", "trainings": "Entrenamientos", "logout": "Cerrar Sesión", "tab_train": "🎤 Entrenamiento", "tab_upgrade": "⭐ Mejorar Plan", "tab_agent": "🤖 Ruta de Estudio IA", "up_title": "Desbloquea tu potencial 🚀", "up_sub": "(Pronto: Pagos directos)", "up_mkt_title": "🚀 Máxima Velocidad e Inteligencia", "up_mkt_desc": "Al subir a un nivel de paga, tu cuenta se migra a servidores dedicados con modelos de IA más avanzados.", "up_tagline": "Elige el plan perfecto para ti", "up_popular": "⭐ MÁS POPULAR", "up_premium": "👑 PREMIUM", "up_cur_badge": "Plan actual", "up_active": "✓ Tu plan actual", "up_subscribe": "Suscribirse", "up_footer": "🔒 Pagos seguros · Cancela cuando quieras", "learn_prompt": "🌐 Idioma a entrenar:", "record": "Presiona el micro para hablar en", "write": "O escribe en", "btn_send": "Enviar 🚀", "listening": "Escuchando...", "analyzing": "Analizando...", "score": "Puntaje", "correction": "Corrección:", "pronunciation": "Pronunciación:", "tip": "Tip:", "err_char": "Límite: {} caracteres.", "err_audio": "No pudimos escuchar bien. Intenta hablar más claro o escribe tu respuesta.", "limit_reached": "🔒 Límite diario alcanzado.", "repeat": "Frase ya procesada.", "desc_free": "Plan FREE ($0): 5 frases/día", "desc_standard": "Plan STANDARD ($3/mes): 20 frases/día", "desc_pro": "Plan PRO ($8/mes): 100 frases/día", "welcome_title": "¡Bienvenido, {}!", "welcome_ask": "¿Qué idioma quieres practicar hoy?", "btn_continue": "Continuar👉", "diag_title": "🎯 ¡Casi listos!", "diag_prompt": "Responde en **{}**: ¿Por qué quieres aprender este idioma?", "diag_analyzing": "Evaluando nivel...", "diag_success": "¡Genial! Tu nivel en {} es: {}", "change_lang": "🔄 Cambiar Idioma", "settings": "⚙️ Ajustes", "hero_title": "🎙️ Presiona para hablar", "hero_desc": "Di cualquier cosa. La IA te corregirá al instante.", "progress": "📊 Progreso", "lang_name": {"Inglés": "Inglés", "Español": "Español", "Francés": "Francés", "Alemán": "Alemán", "Italiano": "Italiano", "Portugués": "Portugués", "Mandarín": "Mandarín", "Japonés": "Japonés", "Coreano": "Coreano", "Ruso": "Ruso"}, "choose_mode": "Elige tu modo de estudio:", "mode_fund": "🧱 Fundamentos", "mode_fund_desc": "Juega, aprende y escucha tus primeras palabras.", "lesson_txt": "Nivel", "btn_gen_lesson": "📚 Iniciar Reto de Hoy", "btn_next": "📚 Siguiente ⏭️", "mode_real": "🎭 Situaciones Reales", "mode_real_desc": "Pierde el miedo hablando en escenarios prácticos de la vida diaria.", "prep_lesson": "Generando reto interactivo...", "lesson_passed": "🎉 ¡Reto superado! Haz clic en 'Siguiente' para avanzar.", "role_passed": "🎉 ¡Excelente trabajo! Haz clic en 'Siguiente' para otro Role-play.", "topics": ["Saludos", "Pronombres", "Verbos básicos", "Números", "Colores", "Comida", "Familia", "Días y Meses", "Ropa", "Cuerpo", "Animales", "Profesiones", "Clima", "Hogar", "Emociones", "Verbos de acción", "Transporte", "Ciudad", "La Hora", "Rutina"], "tc_check": "Acepto los Términos, Condiciones y Política de Privacidad", "tc_error": "⚠️ Debes aceptar los Términos y Condiciones para continuar.", "tc_title": "📜 Ver Términos y Condiciones", "tc_text": "**Voxis AI - Términos Básicos (Placeholder)**<br>1. Al registrarte aceptas el uso de cookies de sesión para la aplicación.<br>2. Los datos de audio no se comparten; se procesan a través de servidores seguros de Google AI.<br>3. Las cuentas Free están sujetas a límites diarios de cuota.<br>*(El documento legal final se agregará en la versión web pública).*", "otp_sent_msg": "📧 Hemos enviado un código a **{}**", "otp_label": "Código de verificación de 4 dígitos:", "btn_verify": "Verificar Código", "btn_cancel": "Cancelar / Volver", "otp_error": "❌ Código incorrecto. Intenta de nuevo.", "email_error": "❌ Error al enviar el correo. Verifica que tu dirección exista.", "email_subject": "Tu código de acceso a Voxis AI", "email_body": "¡Hola!\n\nTu código de acceso seguro para entrar a Voxis AI es: {}\n\nSi no solicitaste esto, puedes ignorar este correo."},
    "Inglés": {"native_lang": "🗣️ Native Language:", "record_btn": "🎙️ Record (Max {}s)", "login_sub": "Log in to start.", "email": "Email:", "names": "First Name:", "lastnames": "Last Name:", "wa": "WhatsApp:", "plan_select": "Choose starting plan:", "btn_login": "Login / Register", "btn_google": "Продолжить через Google", "btn_google": "Google로 계속", "btn_google": "Googleで続ける", "btn_google": "使用Google继续", "btn_google": "Continuar com Google", "btn_google": "Continua con Google", "btn_google": "Mit Google fortfahren", "btn_google": "Continuer avec Google", "btn_google": "Continue with Google", "greeting": "Hello", "plan_label": "Current Plan", "trainings": "Trainings", "logout": "Log Out", "tab_train": "🎤 Training", "tab_upgrade": "⭐ Upgrade Plan", "tab_agent": "🤖 AI Study Path", "up_title": "Unlock your potential 🚀", "up_sub": "(Soon: Direct payments)", "up_mkt_title": "🚀 Maximum Speed and Intelligence", "up_mkt_desc": "By upgrading to a paid tier, your account is migrated to dedicated servers with more advanced AI models.", "up_tagline": "Choose the perfect plan for you", "up_popular": "⭐ MOST POPULAR", "up_premium": "👑 PREMIUM", "up_cur_badge": "Current plan", "up_active": "✓ Your current plan", "up_subscribe": "Subscribe", "up_footer": "🔒 Secure payments · Cancel anytime", "learn_prompt": "🌐 Language to train:", "record": "Tap mic to speak in", "write": "Or type in", "btn_send": "Send 🚀", "listening": "Listening...", "analyzing": "Analyzing...", "score": "Score", "correction": "Correction:", "pronunciation": "Pronunciation:", "tip": "Tip:", "err_char": "Limit: {} chars.", "err_audio": "Could not hear you well. Please speak louder or type.", "limit_reached": "🔒 Daily limit reached.", "repeat": "Phrase already processed.", "desc_free": "FREE Plan ($0): 5 phrases/day", "desc_standard": "STANDARD Plan ($3/mo): 20 phrases/day", "desc_pro": "PRO Plan ($8/mo): 100 phrases/day", "welcome_title": "Welcome, {}!", "welcome_ask": "What language do you want to practice?", "btn_continue": "Continue👉", "diag_title": "🎯 Almost ready!", "diag_prompt": "Answer in **{}**: Why do you want to learn this language?", "diag_analyzing": "Evaluating level...", "diag_success": "Great! Your level in {} is: {}", "change_lang": "🔄 Change Language", "settings": "⚙️ Settings", "hero_title": "🎙️ Tap to speak", "hero_desc": "Say anything. The AI will correct you instantly.", "progress": "📊 Progress", "lang_name": {"Inglés": "English", "Español": "Spanish", "Francés": "French", "Alemán": "German", "Italiano": "Italian", "Portugués": "Portuguese", "Mandarín": "Mandarin", "Japonés": "Japanese", "Coreano": "Korean", "Ruso": "Russian"}, "choose_mode": "Choose your study mode:", "mode_fund": "🧱 Fundamentals", "mode_fund_desc": "Play, learn and listen to your first words.", "lesson_txt": "Level", "btn_gen_lesson": "📚 Start Today's Challenge", "btn_next": "📚 Next ⏭️", "mode_real": "🎭 Real Scenarios", "mode_real_desc": "Lose the fear by speaking in practical daily scenarios.", "prep_lesson": "Generating interactive challenge...", "lesson_passed": "🎉 Challenge passed! Click 'Next' to advance.", "role_passed": "🎉 Excellent work! Click 'Next' for another Role-play.", "topics": ["Greetings", "Pronouns", "Basic Verbs", "Numbers", "Colors", "Food", "Family", "Days & Months", "Clothes", "Body", "Animals", "Professions", "Weather", "Home", "Emotions", "Action Verbs", "Transportation", "City", "Time", "Routine"], "tc_check": "I accept the Terms, Conditions, and Privacy Policy", "tc_error": "⚠️ You must accept the Terms and Conditions to continue.", "tc_title": "📜 View Terms and Conditions", "tc_text": "**Voxis AI - Basic Terms (Placeholder)**<br>1. By registering, you accept the use of session cookies.<br>2. Audio data is not shared; it is processed via secure Google AI servers.<br>3. Free accounts are subject to daily quota limits.<br>*(The final legal document will be added in the public web version).*", "otp_sent_msg": "📧 We sent a code to **{}**", "otp_label": "4-digit verification code:", "btn_verify": "Verify Code", "btn_cancel": "Cancel / Go back", "otp_error": "❌ Incorrect code. Try again.", "email_error": "❌ Error sending email. Check the address.", "email_subject": "Your Voxis AI Access Code", "email_body": "Hello!\n\nYour secure access code for Voxis AI is: {}\n\nIf you didn't request this, please ignore this email."},
    "Francés": {"native_lang": "🗣️ Langue Maternelle:", "record_btn": "🎙️ Enregistrer (Max {}s)", "login_sub": "Connectez-vous.", "email": "E-mail:", "names": "Prénoms:", "lastnames": "Noms:", "wa": "WhatsApp:", "plan_select": "Forfait:", "btn_login": "Connexion / Inscription", "greeting": "Bonjour", "plan_label": "Forfait", "trainings": "Formations", "logout": "Déconnexion", "tab_train": "🎤 Entraînement", "tab_upgrade": "⭐ Améliorer Forfait", "tab_agent": "🤖 Parcours IA", "up_title": "Libérez votre potentiel 🚀", "up_sub": "(Bientôt: Paiements)", "up_mkt_title": "🚀 Vitesse et Intelligence Maximales", "up_mkt_desc": "En passant à un niveau payant, votre compte est migré vers des serveurs dédiés.", "up_tagline": "Choisissez le plan parfait", "up_popular": "⭐ LE PLUS POPULAIRE", "up_premium": "👑 PREMIUM", "up_cur_badge": "Plan actuel", "up_active": "✓ Votre plan actuel", "up_subscribe": "S'abonner", "up_footer": "🔒 Paiements sécurisés · Annulez quand vous voulez", "learn_prompt": "🌐 Langue à former:", "record": "Parlez en", "write": "Ou tapez en", "btn_send": "Envoyer 🚀", "listening": "Écoute...", "analyzing": "Analyse...", "score": "Score", "correction": "Correction:", "pronunciation": "Prononciation:", "tip": "Conseil:", "err_char": "Limite: {} car.", "err_audio": "Nous n'avons pas bien entendu. Parlez plus fort.", "limit_reached": "🔒 Limite atteinte.", "repeat": "Phrase déjà traitée.", "desc_free": "Plan FREE (0$): 5/jour", "desc_standard": "Plan STANDARD (3$/mes): 20/jour", "desc_pro": "Plan PRO (8$/mes): 100/jour", "welcome_title": "Bienvenue, {}!", "welcome_ask": "Quelle langue pratiquer?", "btn_continue": "Continuer👉", "diag_title": "🎯 Presque prêt!", "diag_prompt": "Répondez en **{}**: Pourquoi apprendre cette langue?", "diag_analyzing": "Évaluation...", "diag_success": "Super! Niveau en {} : {}", "change_lang": "🔄 Changer de Langue", "settings": "⚙️ Paramètres", "hero_title": "🎙️ Appuyez pour parler", "hero_desc": "Dites n'importe quoi. L'IA corrigera instantanément.", "progress": "📊 Progrès", "lang_name": {"Inglés": "Anglais", "Español": "Espagnol", "Francés": "Français", "Alemán": "Allemand", "Italiano": "Italien", "Portugués": "Portugais", "Mandarín": "Mandarin", "Japonés": "Japonais", "Coreano": "Coréen", "Ruso": "Russe"}, "choose_mode": "Choisissez votre mode :", "mode_fund": "🧱 Fondamentaux", "mode_fund_desc": "Jouez, apprenez et écoutez vos premiers mots.", "lesson_txt": "Niveau", "btn_gen_lesson": "📚 Démarrer le défi", "btn_next": "📚 Suivant ⏭️", "mode_real": "🎭 Scénarios Réels", "mode_real_desc": "Perdez la peur en parlant dans des scénarios quotidiens.", "prep_lesson": "Génération du défi...", "lesson_passed": "🎉 Défi réussi! Cliquez sur 'Suivant'.", "role_passed": "🎉 Excellent travail! Cliquez sur 'Suivant'.", "topics": ["Salutations", "Pronoms", "Verbos", "Nombres", "Couleurs", "Nourriture", "Famille", "Jours", "Vêtements", "Corps", "Animaux", "Professions", "Météo", "Maison", "Émotions", "Verbes", "Transport", "Ville", "Heure", "Routine"], "tc_check": "J'accepte les conditions générales", "tc_error": "⚠️ Vous devez accepter les conditions.", "tc_title": "📜 Voir les conditions", "tc_text": "**Voxis AI - Conditions**<br>1. Vous acceptez l'utilisation de cookies.<br>2. L'audio est traité via Google AI.<br>3. Les quotas s'appliquent.<br>", "otp_sent_msg": "📧 Code envoyé à **{}**", "otp_label": "Code de vérification:", "btn_verify": "Vérifier", "btn_cancel": "Annuler", "otp_error": "❌ Code incorrect.", "email_error": "❌ Erreur d'e-mail.", "email_subject": "Code d'accès Voxis AI", "email_body": "Bonjour,\n\nVotre code d'accès est : {}"},
    "Alemán": {"native_lang": "🗣️ Muttersprache:", "record_btn": "🎙️ Aufnehmen (Max {}s)", "login_sub": "Melden Sie sich an.", "email": "E-Mail:", "names": "Vorname:", "lastnames": "Nachname:", "wa": "WhatsApp:", "plan_select": "Plan wählen:", "btn_login": "Anmelden / Registrieren", "greeting": "Hallo", "plan_label": "Plan", "trainings": "Trainings", "logout": "Abmelden", "tab_train": "🎤 Training", "tab_upgrade": "⭐ Upgrade", "tab_agent": "🤖 KI-Lernpfad", "up_title": "Potenzial ausschöpfen 🚀", "up_sub": "(Bald: Zahlungen)", "up_mkt_title": "🚀 Maximale Geschwindigkeit", "up_mkt_desc": "Durch ein Upgrade wird Ihr Konto auf dedizierte Server migriert.", "up_tagline": "Wählen Sie den perfekten Plan", "up_popular": "⭐ BELIEBTESTE", "up_premium": "👑 PREMIUM", "up_cur_badge": "Aktueller Plan", "up_active": "✓ Ihr aktueller Plan", "up_subscribe": "Abonnieren", "up_footer": "🔒 Sichere Zahlungen · Jederzeit kündigen", "learn_prompt": "🌐 Sprache:", "record": "Sprechen in", "write": "Oder tippen in", "btn_send": "Senden 🚀", "listening": "Zuhören...", "analyzing": "Analysieren...", "score": "Punktzahl", "correction": "Korrektur:", "pronunciation": "Aussprache:", "tip": "Tipp:", "err_char": "Limit: {} Zeichen.", "err_audio": "Wir konnten Sie nicht hören.", "limit_reached": "🔒 Tageslimit erreicht.", "repeat": "Satz verarbeitet.", "desc_free": "FREE-Plan (0$): 5/Tag", "desc_standard": "STANDARD-Plan (3$/Mo): 20/Tag", "desc_pro": "PRO-Plan (8$/Mo): 100/Tag", "welcome_title": "Willkommen, {}!", "welcome_ask": "Welche Sprache üben?", "btn_continue": "Weiter 👉", "diag_title": "🎯 Fast fertig!", "diag_prompt": "Antworte auf **{}**: Warum diese Sprache lernen?", "diag_analyzing": "Bewertung...", "diag_success": "Großartig! Niveau in {} : {}", "change_lang": "🔄 Sprache ändern", "settings": "⚙️ Einstellungen", "hero_title": "🎙️ Tippen zum Sprechen", "hero_desc": "Sag irgendwas. Die KI korrigiert dich sofort.", "progress": "📊 Fortschritt", "lang_name": {"Inglés": "Englisch", "Español": "Spanisch", "Francés": "Französisch", "Alemán": "Deutsch", "Italiano": "Italienisch", "Portugués": "Portugiesisch", "Mandarín": "Mandarin", "Japonés": "Japanisch", "Coreano": "Koreanisch", "Ruso": "Russisch"}, "choose_mode": "Lernmodus wählen:", "mode_fund": "🧱 Grundlagen", "mode_fund_desc": "Spielen, lernen und hören Sie Ihre ersten Wörter.", "lesson_txt": "Level", "btn_gen_lesson": "📚 Herausforderung starten", "btn_next": "📚 Nächste ⏭️", "mode_real": "🎭 Echte Szenarien", "mode_real_desc": "Sprechen Sie ohne Angst in täglichen Szenarien.", "prep_lesson": "Interaktive Herausforderung wird erstellt...", "lesson_passed": "🎉 Bestanden! Klick 'Nächste', um fortzufahren.", "role_passed": "🎉 Hervorragende Arbeit! Klick 'Nächste'.", "topics": ["Begrüßungen", "Pronomen", "Verben", "Zahlen", "Farben", "Essen", "Familie", "Tage", "Kleidung", "Körper", "Tiere", "Berufe", "Wetter", "Zuhause", "Emotionen", "Aktionsverben", "Transport", "Stadt", "Zeit", "Routine"], "tc_check": "Ich akzeptiere die AGB", "tc_error": "⚠️ Sie müssen die Bedingungen akzeptieren.", "tc_title": "📜 AGB anzeigen", "tc_text": "**Voxis AI - Bedingungen**<br>1. Mit der Registrierung akzeptieren Sie Cookies.<br>", "otp_sent_msg": "📧 Code gesendet an **{}**", "otp_label": "Bestätigungscode:", "btn_verify": "Überprüfen", "btn_cancel": "Abbrechen", "otp_error": "❌ Falscher Code.", "email_error": "❌ E-Mail-Fehler.", "email_subject": "Voxis AI Zugangscode", "email_body": "Hallo!\n\nDein Zugangscode ist: {}"},
    "Italiano": {"native_lang": "🗣️ Lingua Madre:", "record_btn": "🎙️ Registra (Max {}s)", "login_sub": "Accedi per iniziare.", "email": "Email:", "names": "Nome:", "lastnames": "Cognome:", "wa": "WhatsApp:", "plan_select": "Scegli piano:", "btn_login": "Accedi / Registrati", "greeting": "Ciao", "plan_label": "Piano", "trainings": "Allenamenti", "logout": "Esci", "tab_train": "🎤 Allenamento", "tab_upgrade": "⭐ Migliora", "tab_agent": "🤖 Percorso IA", "up_title": "Sblocca potenziale 🚀", "up_sub": "(Presto: Pagamenti)", "up_mkt_title": "🚀 Massima Velocità", "up_mkt_desc": "Passando a un livello a pagamento, il tuo account viene migrato su server dedicati.", "up_tagline": "Scegli il piano perfetto", "up_popular": "⭐ PIÙ POPOLARE", "up_premium": "👑 PREMIUM", "up_cur_badge": "Piano attuale", "up_active": "✓ Il tuo piano attuale", "up_subscribe": "Abbonati", "up_footer": "🔒 Pagamenti sicuri · Annulla quando vuoi", "learn_prompt": "🌐 Lingua:", "record": "Parla in", "write": "O scrivi in", "btn_send": "Invia🚀", "listening": "Ascoltando...", "analyzing": "Analizzando...", "score": "Punteggio", "correction": "Correzione:", "pronunciation": "Pronuncia:", "tip": "Suggerimento:", "err_char": "Limite: {} car.", "err_audio": "Non ti abbiamo sentito bene. Parla più forte.", "limit_reached": "🔒 Limite raggiunto.", "repeat": "Già elaborata.", "desc_free": "Piano FREE ($0): 5/giorno", "desc_standard": "Piano STANDARD ($3/mes): 20/giorno", "desc_pro": "Piano PRO ($8/mes): 100/giorno", "welcome_title": "Benvenuto, {}!", "welcome_ask": "Che lingua vuoi praticare?", "btn_continue": "Continua 👉", "diag_title": "🎯 Quasi pronti!", "diag_prompt": "Rispondi in **{}**: Perché vuoi imparare?", "diag_analyzing": "Valutazione...", "diag_success": "Ottimo! Livello in {} : {}", "change_lang": "🔄 Cambia Lingua", "settings": "⚙️ Impostazioni", "hero_title": "🎙️ Tocca per parlare", "hero_desc": "Dì qualsiasi cosa. L'IA ti correggerà all'istante.", "progress": "📊 Progresso", "lang_name": {"Inglés": "Inglese", "Español": "Spagnolo", "Francés": "Francese", "Alemán": "Tedesco", "Italiano": "Italiano", "Portugués": "Portoghese", "Mandarín": "Mandarino", "Japonés": "Giapponese", "Coreano": "Coreano", "Ruso": "Russo"}, "choose_mode": "Scegli la modalità:", "mode_fund": "🧱 Fondamenti", "mode_fund_desc": "Gioca, impara e ascolta le tue prime parole.", "lesson_txt": "Livello", "btn_gen_lesson": "📚 Inizia Sfida", "btn_next": "📚 Avanti ⏭️", "mode_real": "🎭 Scenari Reali", "mode_real_desc": "Parla senza paura in scenari quotidiani.", "prep_lesson": "Generazione sfida...", "lesson_passed": "🎉 Superato! Clicca 'Avanti'.", "role_passed": "🎉 Ottimo lavoro! Clicca 'Avanti'.", "topics": ["Saluti", "Pronomi", "Verbi", "Numeri", "Colori", "Cibo", "Famiglia", "Giorni", "Vestiti", "Corpo", "Animali", "Professioni", "Meteo", "Casa", "Emozioni", "Verbi", "Trasporto", "Città", "Ora", "Routine"], "tc_check": "Accetto i Termini", "tc_error": "⚠️ Devi accettare i Termini.", "tc_title": "📜 Visualizza Termini", "tc_text": "**Voxis AI - Termini**<br>1. Registrandoti accetti i cookie.", "otp_sent_msg": "📧 Codice inviato a **{}**", "otp_label": "Codice di verifica:", "btn_verify": "Verifica", "btn_cancel": "Annulla", "otp_error": "❌ Codice errato.", "email_error": "❌ Errore email.", "email_subject": "Codice di accesso", "email_body": "Ciao!\n\nIl tuo codice è: {}"},
    "Portugués": {"native_lang": "🗣️ Língua Nativa:", "record_btn": "🎙️ Gravar (Max {}s)", "login_sub": "Faça login.", "email": "E-mail:", "names": "Nome:", "lastnames": "Sobrenome:", "wa": "WhatsApp:", "plan_select": "Escolha o plano:", "btn_login": "Entrar / Registrar", "greeting": "Olá", "plan_label": "Plano", "trainings": "Treinos", "logout": "Sair", "tab_train": "🎤 Treino", "tab_upgrade": "⭐ Melhorar Plano", "tab_agent": "🤖 Trilha IA", "up_title": "Desbloqueie potencial 🚀", "up_sub": "(Em breve: Pagamentos)", "up_mkt_title": "🚀 Máxima Velocidade", "up_mkt_desc": "Ao atualizar, sua conta é migrada para servidores dedicados.", "up_tagline": "Escolha o plano perfeito", "up_popular": "⭐ MAIS POPULAR", "up_premium": "👑 PREMIUM", "up_cur_badge": "Plano atual", "up_active": "✓ Seu plano atual", "up_subscribe": "Assinar", "up_footer": "🔒 Pagamentos seguros · Cancele quando quiser", "learn_prompt": "🌐 Idioma:", "record": "Fale em", "write": "Ou digite em", "btn_send": "Enviar 🚀", "listening": "Ouvindo...", "analyzing": "Analisando...", "score": "Pontuação", "correction": "Correção:", "pronunciation": "Pronúncia:", "tip": "Dica:", "err_char": "Limite: {} car.", "err_audio": "Não conseguimos ouvir bem. Fale mais alto.", "limit_reached": "🔒 Limite atingido.", "repeat": "Frase processada.", "desc_free": "Plano FREE ($0): 5/dia", "desc_standard": "Plano STANDARD ($3/mes): 20/dia", "desc_pro": "Plano PRO ($8/mes): 100/dia", "welcome_title": "Bem-vindo, {}!", "welcome_ask": "Qual idioma praticar?", "btn_continue": "Continuar 👉", "diag_title": "🎯 Quase pronto!", "diag_prompt": "Responda em **{}**: Por que aprender este idioma?", "diag_analyzing": "Avaliando...", "diag_success": "Ótimo! Nível em {} : {}", "change_lang": "🔄 Mudar Idioma", "settings": "⚙️ Configurações", "hero_title": "🎙️ Toque para falar", "hero_desc": "Diga qualquer coisa. A IA vai te corrigir instantaneamente.", "progress": "📊 Progresso", "lang_name": {"Inglés": "Inglês", "Español": "Espanhol", "Francés": "Francês", "Alemán": "Alemão", "Italiano": "Italiano", "Portugués": "Português", "Mandarín": "Mandarim", "Japonés": "Japonês", "Coreano": "Coreano", "Ruso": "Russo"}, "choose_mode": "Escolha seu modo:", "mode_fund": "🧱 Fundamentos", "mode_fund_desc": "Jogue, aprenda e ouça.", "lesson_txt": "Nível", "btn_gen_lesson": "📚 Iniciar Desafio", "btn_next": "📚 Próximo ⏭️", "mode_real": "🎭 Cenários Reais", "mode_real_desc": "Perca o medo falando em cenários diários.", "prep_lesson": "Gerando desafio...", "lesson_passed": "🎉 Sucesso! Clique em 'Próximo'.", "role_passed": "🎉 Excelente! Clique em 'Próximo'.", "topics": ["Saudações", "Pronomes", "Verbos", "Números", "Cores", "Comida", "Família", "Dias", "Roupas", "Corpo", "Animais", "Profissões", "Clima", "Casa", "Emoções", "Ação", "Transporte", "Cidade", "Hora", "Rotina"], "tc_check": "Aceito os Termos", "tc_error": "⚠️ Aceite os Termos.", "tc_title": "📜 Ver Termos", "tc_text": "**Termos**<br>1. Aceito cookies.", "otp_sent_msg": "📧 Código enviado a **{}**", "otp_label": "Código:", "btn_verify": "Verificar", "btn_cancel": "Cancelar", "otp_error": "❌ Código incorreto.", "email_error": "❌ Erro.", "email_subject": "Código Voxis", "email_body": "Seu código é: {}"},
    "Mandarín": {"native_lang": "🗣️ 母语:", "record_btn": "🎙️ 录音 (最多{}秒)", "login_sub": "登录以开始。", "email": "电子邮件:", "names": "名:", "lastnames": "姓:", "wa": "WhatsApp:", "plan_select": "选择计划:", "btn_login": "登录 / 注册", "greeting": "你好", "plan_label": "计划", "trainings": "训练", "logout": "登出", "tab_train": "🎤 训练", "tab_upgrade": "⭐ 升级", "tab_agent": "🤖 AI 路径", "up_title": "释放潜力🚀", "up_sub": "(即将推出)", "up_mkt_title": "🚀极速与智能", "up_mkt_desc": "升级到付费层后，您的帐户将迁移到配备更高级 AI 模型的专用服务器。", "up_tagline": "选择适合您的方案", "up_popular": "⭐ 最受欢迎", "up_premium": "👑 高级", "up_cur_badge": "当前方案", "up_active": "✓ 您的当前方案", "up_subscribe": "订阅", "up_footer": "🔒 安全支付 · 随时取消", "learn_prompt": "🌐 语言:", "record": "用此语言说话:", "write": "或输入:", "btn_send": "发送 🚀", "listening": "倾听中...", "analyzing": "分析中...", "score": "分数", "correction": "纠正:", "pronunciation": "发音:", "tip": "提示:", "err_char": "限制: {} 字符。", "err_audio": "听不清楚，请大声说话。", "limit_reached": "🔒 达到限额。", "repeat": "已处理。", "desc_free": "FREE ($0): 5句/天", "desc_standard": "STANDARD ($3/月): 20句/天", "desc_pro": "PRO ($8/月): 100句/天", "welcome_title": "欢迎, {}!", "welcome_ask": "想练习什么语言？", "btn_continue": "继续 👉", "diag_title": "🎯 差不多了！", "diag_prompt": "请用 **{}** 回答：为什么想学？", "diag_analyzing": "评估中...", "diag_success": "太棒了！{}级别: {}", "change_lang": "🔄更改语言", "settings": "⚙️ 设置", "hero_title": "🎙️ 点击说话", "hero_desc": "随便说什么，AI会立即纠正你。", "progress": "📊 进度", "lang_name": {"Inglés": "英语", "Español": "西班牙语", "Francés": "法语", "Alemán": "德语", "Italiano": "意大利语", "Portugués": "葡萄牙语", "Mandarín": "中文", "Japonés": "日语", "Coreano": "韩语", "Ruso": "俄语"}, "choose_mode": "选择模式:", "mode_fund": "🧱 基础知识", "mode_fund_desc": "边玩边学。", "lesson_txt": "水平", "btn_gen_lesson": "📚 开始挑战", "btn_next": "📚 下一步 ⏭️", "mode_real": "🎭 真实场景", "mode_real_desc": "在日常实用场景中开口说。", "prep_lesson": "正在生成挑战...", "lesson_passed": "🎉 成功！点击下一步。", "role_passed": "🎉 干得好！点击下一步。", "topics": ["问候", "代词", "动词", "数字", "颜色", "食物", "家庭", "日期", "衣服", "身体", "动物", "职业", "天气", "家居", "情绪", "动作", "交通", "城市", "时间", "日常"], "tc_check": "我接受条款", "tc_error": "⚠️ 必须接受条款。", "tc_title": "📜 查看条款", "tc_text": "**条款**<br>1. 接受cookie。", "otp_sent_msg": "📧 代码已发送至 **{}**", "otp_label": "验证码:", "btn_verify": "验证", "btn_cancel": "取消", "otp_error": "❌ 代码错误。", "email_error": "❌ 邮件发送失败。", "email_subject": "访问代码", "email_body": "您的代码是: {}"},
    "Japonés": {"native_lang": "🗣️ 母国語:", "record_btn": "🎙️ 録音 (最大{}秒)", "login_sub": "ログイン", "email": "Eメール:", "names": "名:", "lastnames": "姓:", "wa": "WhatsApp:", "plan_select": "プラン:", "btn_login": "ログイン / 登録", "greeting": "こんにちは", "plan_label": "プラン", "trainings": "トレ", "logout": "ログアウト", "tab_train": "🎤練習", "tab_upgrade": "⭐ アップ", "tab_agent": "🤖 AIパス", "up_title": "可能性を解き放つ🚀", "up_sub": "(まもなく)", "up_mkt_title": "🚀 スピード", "up_mkt_desc": "専用サーバーに移行。", "up_tagline": "完璧なプランを選択", "up_popular": "⭐ 最人気", "up_premium": "👑 プレミアム", "up_cur_badge": "現在のプラン", "up_active": "✓ 現在のプラン", "up_subscribe": "登録する", "up_footer": "🔒 安全な支払い · いつでもキャンセル", "learn_prompt": "🌐 言語:", "record": "話す:", "write": "入力:", "btn_send": "送信 🚀", "listening": "聞いています...", "analyzing": "分析中...", "score": "スコア", "correction": "訂正:", "pronunciation": "発音:", "tip": "ヒント:", "err_char": "制限: {} 文字", "err_audio": "よく聞こえませんでした。", "limit_reached": "🔒 制限到達。", "repeat": "処理済み。", "desc_free": "FREE ($0): 5回", "desc_standard": "STANDARD ($3/月): 20回", "desc_pro": "PRO ($8/月): 100回", "welcome_title": "ようこそ, {}!", "welcome_ask": "どの言語？", "btn_continue": "続ける👉", "diag_title": "🎯 完了！", "diag_prompt": "**{}** で回答:なぜ？", "diag_analyzing": "評価中...", "diag_success": "素晴らしい！ {} レベル: {}", "change_lang": "🔄 言語変更", "settings": "⚙️ 設定", "hero_title": "🎙️ タップして話す", "hero_desc": "何でも言ってください。AIがすぐに修正します。", "progress": "📊 進捗", "lang_name": {"Inglés": "英語", "Español": "スペイン語", "Francés": "フランス語", "Alemán": "ドイツ語", "Italiano": "イタリア語", "Portugués": "ポルトガル語", "Mandarín": "中国語", "Japonés": "日本語", "Coreano": "韓国語", "Ruso": "ロシア語"}, "choose_mode": "モード:", "mode_fund": "🧱 基礎", "mode_fund_desc": "遊びながら学ぶ", "lesson_txt": "レベル", "btn_gen_lesson": "📚開始", "btn_next": "📚 次へ ⏭️", "mode_real": "🎭 リアル", "mode_real_desc": "日常シナリオ", "prep_lesson": "生成中...", "lesson_passed": "🎉クリア！次へ", "role_passed": "🎉 素晴らしい！次へ", "topics": ["挨拶", "代名詞", "動詞", "数字", "色", "食べ物", "家族", "日付", "服", "体", "動物", "職業", "天気", "家", "感情", "動作", "交通", "都市", "時間", "日常"], "tc_check": "同意します", "tc_error": "⚠️同意が必要", "tc_title": "📜 規約", "tc_text": "**規約**<br>同意", "otp_sent_msg": "📧 **{}** に送信", "otp_label": "コード:", "btn_verify": "確認", "btn_cancel": "キャンセル", "otp_error": "❌間違い", "email_error": "❌ エラー", "email_subject": "コード", "email_body": "コード: {}"},
    "Coreano": {"native_lang": "🗣️ 모국어:", "record_btn": "🎙️ 녹음 (최대 {}초)", "login_sub": "로그인", "email": "이메일:", "names": "이름:", "lastnames": "성:", "wa": "WhatsApp:", "plan_select": "플랜:", "btn_login": "로그인 / 가입", "greeting": "안녕하세요", "plan_label": "플랜", "trainings": "훈련", "logout": "로그아웃", "tab_train": "🎤 훈련", "tab_upgrade": "⭐ 업그레이드", "tab_agent": "🤖 AI 경로", "up_title": "잠재력🚀", "up_sub": "(곧)", "up_mkt_title": "🚀 속도", "up_mkt_desc": "서버 마이그레이션.", "up_tagline": "완벽한 플랜을 선택하세요", "up_popular": "⭐ 가장 인기", "up_premium": "👑 프리미엄", "up_cur_badge": "현재 플랜", "up_active": "✓ 현재 플랜", "up_subscribe": "구독", "up_footer": "🔒 안전한 결제 · 언제든지 취소", "learn_prompt": "🌐 언어:", "record": "말하기:", "write": "입력:", "btn_send": "보내기 🚀", "listening": "듣는 중...", "analyzing": "분석 중...", "score": "점수", "correction": "교정:", "pronunciation": "발음:", "tip": "팁:", "err_char": "제한: {} 자", "err_audio": "잘 들리지 않습니다.", "limit_reached": "🔒 한도 초과.", "repeat": "처리됨.", "desc_free": "FREE ($0): 5번", "desc_standard": "STANDARD ($3/월): 20번", "desc_pro": "PRO ($8/월): 100번", "welcome_title": "환영합니다, {}!", "welcome_ask": "어떤 언어?", "btn_continue": "계속 👉", "diag_title": "🎯 완료!", "diag_prompt": "**{}**로 대답: 왜?", "diag_analyzing": "평가 중...", "diag_success": "멋져요! {} 레벨: {}", "change_lang": "🔄 언어 변경", "settings": "⚙️ 설정", "hero_title": "🎙️ 탭하여 말하기", "hero_desc": "아무거나 말해보세요. AI가 즉시 수정해 드립니다.", "progress": "📊 진행", "lang_name": {"Inglés": "영어", "Español": "스페인어", "Francés": "프랑스어", "Alemán": "독일어", "Italiano": "이탈리아어", "Portugués": "포르투갈어", "Mandarín": "중국어", "Japonés": "일본어", "Coreano": "한국어", "Ruso": "러시아어"}, "choose_mode": "모드:", "mode_fund": "🧱기초", "mode_fund_desc": "놀면서 배우기", "lesson_txt": "레벨", "btn_gen_lesson": "📚시작", "btn_next": "📚 다음 ⏭️", "mode_real": "🎭 상황", "mode_real_desc": "실제 상황", "prep_lesson": "생성 중...", "lesson_passed": "🎉 통과! 다음", "role_passed": "🎉 훌륭합니다! 다음", "topics": ["인사말", "대명사", "동사", "숫자", "색상", "음식", "가족", "날짜", "옷", "신체", "동물", "직업", "날씨", "집", "감정", "동작", "교통", "도시", "시간", "일상"], "tc_check": "동의합니다", "tc_error": "⚠️동의 필요", "tc_title": "📜 약관", "tc_text": "**약관**<br>동의", "otp_sent_msg": "📧 **{}** 로 보냄", "otp_label": "코드:", "btn_verify": "확인", "btn_cancel": "취소", "otp_error": "❌ 오류", "email_error": "❌ 에러", "email_subject": "코드", "email_body": "코드: {}"},
    "Ruso": {"native_lang": "🗣️ Родной язык:", "record_btn": "🎙️ Запись (Макс. {}с)", "login_sub": "Войдите.", "email": "Почта:", "names": "Имя:", "lastnames": "Фамилия:", "wa": "WhatsApp:", "plan_select": "План:", "btn_login": "Вход / Регистрация", "greeting": "Привет", "plan_label": "План", "trainings": "Тренировки", "logout": "Выйти", "tab_train": "🎤 Тренировка", "tab_upgrade": "⭐ Улучшить", "tab_agent": "🤖 Путь ИИ", "up_title": "Раскройте потенциал 🚀", "up_sub": "(Скоро)", "up_mkt_title": "🚀 Скорость", "up_mkt_desc": "Выделенные серверы.", "up_tagline": "Выберите идеальный план", "up_popular": "⭐ САМЫЙ ПОПУЛЯРНЫЙ", "up_premium": "👑 ПРЕМИУМ", "up_cur_badge": "Текущий план", "up_active": "✓ Ваш текущий план", "up_subscribe": "Подписаться", "up_footer": "🔒 Безопасная оплата · Отменить в любое время", "learn_prompt": "🌐 Язык:", "record": "Говорить", "write": "Или введите", "btn_send": "Отправить🚀", "listening": "Слушаю...", "analyzing": "Анализ...", "score": "Оценка", "correction": "Исправление:", "pronunciation": "Произношение:", "tip": "Совет:", "err_char": "Лимит: {} симв.", "err_audio": "Вас плохо слышно.", "limit_reached": "🔒 Лимит достигнут.", "repeat": "Обработано.", "desc_free": "FREE ($0): 5", "desc_standard": "STANDARD ($3/мес): 20", "desc_pro": "PRO ($8/мес): 100", "welcome_title": "Добро пожаловать, {}!", "welcome_ask": "Какой язык?", "btn_continue": "Продолжить 👉", "diag_title": "🎯 Почти!", "diag_prompt": "**{}**: Почему?", "diag_analyzing": "Оценка...", "diag_success": "Отлично!Уровень {} : {}", "change_lang": "🔄 Сменить язык", "settings": "⚙️ Настройки", "hero_title": "🎙️ Нажмите, чтобы говорить", "hero_desc": "Скажите что-нибудь. ИИ сразу же исправит вас.", "progress": "📊 Прогресс", "lang_name": {"Inglés": "Английский", "Español": "Испанский", "Francés": "Французский", "Alemán": "Немецкий", "Italiano": "Итальянский", "Portugués": "Португальский", "Mandarín": "Китайский", "Japonés": "Японский", "Coreano": "Корейский", "Ruso": "Русский"}, "choose_mode": "Режим:", "mode_fund": "🧱 Основы", "mode_fund_desc": "Играйте и учите.", "lesson_txt": "Уровень", "btn_gen_lesson": "📚 Начать", "btn_next": "📚 Далее ⏭️", "mode_real": "🎭 Сценарии", "mode_real_desc": "Говорите без страха.", "prep_lesson": "Генерация...", "lesson_passed": "🎉 Пройдено!Далее.", "role_passed": "🎉 Отлично!Далее.", "topics": ["Приветствия", "Местоимения", "Глаголы", "Числа", "Цвета", "Еда", "Семья", "Дни", "Одежда", "Тело", "Животные", "Профессии", "Погода", "Дом", "Эмоции", "Действия", "Транспорт", "Город", "Время", "Рутина"], "tc_check": "Я принимаю Условия", "tc_error": "⚠️ Примите условия.", "tc_title": "📜 Условия", "tc_text": "**Условия**<br>Принимаю.", "otp_sent_msg": "📧 Отправлен на **{}**", "otp_label": "Код:", "btn_verify": "Подтвердить", "btn_cancel": "Отмена", "otp_error": "❌ Неверно.", "email_error": "❌ Ошибка.", "email_subject": "Код", "email_body": "Код: {}"}
}

IDIOMAS_APRENDER = {
    "Inglés": {"stt": "en-US", "tts": "en"}, "Español": {"stt": "es-ES", "tts": "es"},
    "Francés": {"stt": "fr-FR", "tts": "fr"}, "Alemán": {"stt": "de-DE", "tts": "de"}, 
    "Italiano": {"stt": "it-IT", "tts": "it"}, "Portugués": {"stt": "pt-BR", "tts": "pt"},
    "Mandarín": {"stt": "zh-CN", "tts": "zh-CN"}, "Japonés": {"stt": "ja-JP", "tts": "ja"},
    "Coreano": {"stt": "ko-KR", "tts": "ko"}, "Ruso": {"stt": "ru-RU", "tts": "ru"}
}

# --- 4. INTERFAZ Y LÓGICA ---
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "Español"

# Lógica para procesar el cambio de idioma nativo desde el Top Bar
def update_native_lang():
    if "top_lang_selector" in st.session_state:
        val = st.session_state.top_lang_selector
        # Extraer el nombre del idioma sin el emoji
        val_limpio = val.replace("🌐 ", "").strip()
        old_lang = st.session_state.ui_lang
        for orig, trad in UI_TEXT[old_lang]["lang_name"].items():
            if trad == val_limpio and orig in UI_TEXT:
                st.session_state.ui_lang = orig
                break

idioma_nativo = st.session_state.ui_lang
t = UI_TEXT[idioma_nativo]

for key in ["ultima_frase", "ultimo_audio", "audio_diagnostico", "usuario_db", "idioma_activo", "otp_sent", "otp_code", "temp_data"]:
    if key not in st.session_state:
        st.session_state[key] = None if "audio" in key or key == "usuario_db" or key == "idioma_activo" else ("" if "ultima" in key or key=="otp_code" else (False if key=="otp_sent" else {}))

if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = secrets_module.token_urlsafe(16)

if "last_native_lang" not in st.session_state:
    st.session_state.last_native_lang = idioma_nativo
elif st.session_state.last_native_lang != idioma_nativo:
    for key in list(st.session_state.keys()):
        if key.startswith("reto_") or key.startswith("audio_reto_"):
            st.session_state[key] = ""
    st.session_state.last_native_lang = idioma_nativo

if st.session_state.usuario_db is None and "user_session" in st.query_params:
    correo_recuperado = st.query_params["user_session"]
    doc_recuperado = db.collection("usuarios").document(correo_recuperado).get()
    if doc_recuperado.exists:
        st.session_state.usuario_db = doc_recuperado.to_dict()

if st.session_state.idioma_activo is None and "lang_session" in st.query_params:
    st.session_state.idioma_activo = st.query_params["lang_session"]

# --- FUNCIONES DE BACKEND ---
def enviar_otp(correo_destino, codigo, dict_idioma):
    try:
        remitente = st.secrets["EMAIL_USER"]
        password = st.secrets["EMAIL_PASS"]
        msg = MIMEText(dict_idioma["email_body"].format(codigo))
        msg['Subject'] = dict_idioma["email_subject"]
        msg['From'] = remitente
        msg['To'] = correo_destino
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.sendmail(remitente, correo_destino, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error enviando correo: {e}")
        return False

def iniciar_sesion(correo, nombres, apellidos, whatsapp, plan_texto):
    p_upper = plan_texto.upper()
    if "FREE" in p_upper: plan_db = "Free"
    elif "STANDARD" in p_upper: plan_db = "Standard"
    else: plan_db = "Pro"
    doc_ref = db.collection("usuarios").document(correo)
    doc = doc_ref.get()
    if doc.exists:
        hoy = date.today().strftime("%Y-%m-%d")
        datos = doc.to_dict()
        if datos.get("plan") != plan_db:
            datos["plan"] = plan_db
            doc_ref.update({"plan": plan_db})
        if datos.get("ultima_fecha_uso") != hoy:
            datos["frases_usadas_hoy"] = 0
            datos["ultima_fecha_uso"] = hoy
            doc_ref.set(datos, merge=True)
        if "niveles" not in datos:
            datos["niveles"] = {}
            doc_ref.update({"niveles": {}})
        st.query_params["user_session"] = correo 
        return datos, "Welcome back!"
    else:
        nuevo = {"correo": correo, "nombres": nombres, "apellidos": apellidos, "whatsapp": whatsapp, "plan": plan_db, "frases_usadas_hoy": 0, "ultima_fecha_uso": str(date.today()), "niveles": {}}
        doc_ref.set(nuevo)
        st.query_params["user_session"] = correo 
        return nuevo, "Account created!"

def procesar_con_gemini(texto, idioma_aprender, idioma_nativo):
    prompt = f"Actúa como preparador experto de {idioma_aprender}. El estudiante habla nativamente {idioma_nativo}. Analiza la siguiente frase y devuelve SOLO JSON: {{'correccion': 'ESCRIBE AQUÍ SOLAMENTE LA FRASE CORREGIDA EN {idioma_aprender}. NADA EN {idioma_nativo}', 'pronunciacion': '...', 'tips': 'Explica en {idioma_nativo}', 'puntuacion': '1-10'}}. En 'pronunciacion', usa fonética para {idioma_nativo}. Frase a evaluar: '{texto}'"
    client = init_gemini()
    ultimo = st.session_state.get("ultimo_modelo_exitoso", MODELOS_GEMINI[0])
    orden = [ultimo] + [m for m in MODELOS_GEMINI if m != ultimo]
    for mod in orden:
        try:
            response = client.models.generate_content(model=mod, contents=prompt)
            res_text = response.text.replace('```json\n', '').replace('```', '').strip()
            st.session_state["ultimo_modelo_exitoso"] = mod
            return json.loads(res_text)
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["429", "quota", "resource_exhausted"]):
                logger.warning(f"Modelo {mod} en cuota, cambiando...")
            else:
                logger.warning(f"Error en modelo {mod}: {e}")
            continue
    return {"error": "Servidores ocupados. Intenta de nuevo en un momento."}

def evaluar_nivel(texto_diagnostico, idioma_aprender, idioma_nativo):
    prompt = f"El usuario intenta aprender {idioma_aprender} y su idioma nativo es {idioma_nativo}. Analiza este texto: '{texto_diagnostico}'. REGLA ESTRICTA: Si el texto está escrito en {idioma_nativo} en lugar de {idioma_aprender}, responde 'A1'. Si está escrito en {idioma_aprender}, determina su nivel CEFR (A1, A2, B1, B2, C1, C2). Responde ÚNICAMENTE con el nivel."
    try:
        client = init_gemini()
        response = client.models.generate_content(model=MODELOS_GEMINI[0], contents=prompt)
        return response.text.strip()[:2]
    except Exception as e:
        logger.warning(f"Error evaluando nivel: {e}")
        return "A1"

# --- GOOGLE OAUTH HELPERS ---
REDIRECT_URI = "https://voxis-ai-69dy6myrud64ntbk6rz2ig.streamlit.app/"

def get_google_auth_url(state):
    params = {
        "client_id": st.secrets.get("GOOGLE_CLIENT_ID", ""),
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account"
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)

def exchange_google_code(code):
    try:
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": st.secrets.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": st.secrets.get("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }, timeout=10)
        token_data = resp.json()
        if "access_token" not in token_data:
            logger.warning(f"OAuth error: {token_data}")
            return None
        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=10
        )
        return user_resp.json()
    except Exception as e:
        logger.warning(f"Error en Google OAuth: {e}")
        return None


# --- TOP BAR APP (Logo HTML forzado a 120px) ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return None

# Logo SVG soundwave bars — darkmode, sin dependencia del PNG
st.markdown(
    '<div style="text-align:center; padding: 48px 0 6px 0;">'
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="24" viewBox="0 0 32 24" '
    'style="vertical-align:middle; margin-right:6px;">'
    '<rect x="0"  y="10" width="4" height="7"  rx="2" fill="#FF7F50"/>'
    '<rect x="6"  y="5"  width="4" height="14" rx="2" fill="#FFB347"/>'
    '<rect x="12" y="0"  width="4" height="24" rx="2" fill="#FF7F50"/>'
    '<rect x="18" y="5"  width="4" height="14" rx="2" fill="#FFB347"/>'
    '<rect x="24" y="10" width="4" height="7"  rx="2" fill="#FF7F50"/>'
    '</svg>'
    '<span style="font-size:1.55rem; font-weight:800; color:#FFFFFF; '
    'letter-spacing:-0.5px; vertical-align:middle;">'
    '<span style="background:linear-gradient(135deg,#FF7F50,#FFB347);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
    'background-clip:text;">Voxis AI</span></span><br>'
    '<span style="font-size:0.72rem; color:#7A84A0; letter-spacing:1.5px; text-transform:uppercase;">'
    'Your 24/7 AI Language Trainer</span></div>',
    unsafe_allow_html=True
)

# Selector de idioma nativo
opciones_ui = [f"🌐 {t['lang_name'][l]}" for l in UI_TEXT.keys()]
idx_ui = list(UI_TEXT.keys()).index(idioma_nativo)
st.selectbox("Idioma Nativo", opciones_ui, index=idx_ui, key="top_lang_selector", on_change=update_native_lang, label_visibility="collapsed")

st.markdown("---") # Línea divisoria compacta

# --- PANTALLA 1: LOGIN Y VERIFICACIÓN OTP ---
if st.session_state.usuario_db is None:
    # Manejar callback de Google OAuth (sin validar state — sesión nueva en cada redirect)
    if "code" in st.query_params and st.session_state.usuario_db is None:
        code = st.query_params["code"]
        with st.spinner("🔑 Verificando cuenta de Google..."):
            google_user = exchange_google_code(code)
            if google_user and "email" in google_user:
                correo_g = google_user["email"].strip().lower()
                nombre_g = google_user.get("given_name", correo_g.split("@")[0])
                apellido_g = google_user.get("family_name", "")
                datos, msg = iniciar_sesion(correo_g, nombre_g, apellido_g, "", t["desc_free"])
                st.session_state.usuario_db = datos
                for param in ["code", "state", "scope", "authuser", "prompt", "session_state"]:
                    if param in st.query_params:
                        del st.query_params[param]
                st.rerun()
            else:
                st.error("❌ Error autenticando con Google. Intenta de nuevo.")

    # Slogan ya incluido en el header del logo
    if not st.session_state.otp_sent:
        # Botón de Google Sign-In
        if st.secrets.get("GOOGLE_CLIENT_ID", ""):
            google_url = get_google_auth_url(st.session_state.get("oauth_state", "state"))
            st.markdown(
                f'<a href="{google_url}" class="google-btn" target="_self">'
                f'<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="20">'
                f' {t.get("btn_google", "Continue with Google")}</a>',
                unsafe_allow_html=True
            )
            st.markdown('<div class="divider-text">— o continúa con email —</div>', unsafe_allow_html=True)
        st.write(t["login_sub"])
        with st.form("form_login"):
            correo_in = st.text_input(t["email"]).strip().lower()
            nombres = st.text_input(t["names"])
            apellidos = st.text_input(t["lastnames"])
            whatsapp = st.text_input(t["wa"], placeholder="+1 555")
            st.write("---")
            st.write(f"**{t['plan_select']}**")
            plan_elegido = st.radio("Planes", [t["desc_free"], t["desc_standard"], t["desc_pro"]], label_visibility="collapsed")
            st.write("---")
            aceptar_tc = st.checkbox(t["tc_check"])
            submit_login = st.form_submit_button(t["btn_login"], type="primary")

            if submit_login:
                if not aceptar_tc: st.error(t["tc_error"])
                elif correo_in and nombres:
                    admin_vault = str(st.secrets.get("ADMIN_EMAIL", "")).strip().lower()
                    if correo_in == admin_vault and admin_vault != "":
                        datos, msg = iniciar_sesion(correo_in, nombres, apellidos, whatsapp, plan_elegido)
                        st.session_state.usuario_db = datos
                        st.rerun()
                    else:
                        codigo_gen = str(secrets_module.randbelow(9000) + 1000)
                        if enviar_otp(correo_in, codigo_gen, t):
                            st.session_state.otp_sent = True
                            st.session_state.otp_code = codigo_gen
                            st.session_state.temp_data = {"correo": correo_in, "nombres": nombres, "apellidos": apellidos, "whatsapp": whatsapp, "plan": plan_elegido}
                            st.rerun()
                        else: st.error(t["email_error"])
                else: st.error("⚠️ Completa los campos requeridos.")
        st.markdown(
            f'<details style="margin-top:18px; padding:10px 14px; background:#111827; border:1px solid #1E2A45; border-radius:10px;">'
            f'<summary style="cursor:pointer; color:#7A84A0; font-size:0.85rem; list-style:none;">'
            f'{t["tc_title"]}</summary>'
            f'<div class="legal-text" style="margin-top:8px;">{t["tc_text"]}</div></details>',
            unsafe_allow_html=True
        )
    else:
        st.info(t["otp_sent_msg"].format(st.session_state.temp_data["correo"]))
        with st.form("form_otp"):
            pin_usuario = st.text_input(t["otp_label"], max_chars=4)
            submit_otp = st.form_submit_button(t["btn_verify"], type="primary")
            if submit_otp:
                if str(pin_usuario).strip() == str(st.session_state.otp_code).strip():
                    d = st.session_state.temp_data
                    datos, msg = iniciar_sesion(d["correo"], d["nombres"], d["apellidos"], d["whatsapp"], d["plan"])
        if st.button(t["btn_cancel"], use_container_width=True):
            st.session_state.otp_sent = False
            st.rerun()

# --- PANTALLA 2 & 3: BIENVENIDA Y DIAGNÓSTICO ---
elif st.session_state.idioma_activo is None:
    u = st.session_state.usuario_db
    st.markdown(f"<h2>{t['welcome_title'].format(u['nombres'])}</h2>", unsafe_allow_html=True)
    st.write(t["welcome_ask"])
    nombres_traducidos = [t["lang_name"][lang] for lang in IDIOMAS_APRENDER.keys()]
    seleccion_traducida = st.selectbox(t["learn_prompt"], nombres_traducidos)
    idioma_seleccionado = "Inglés" 
    for original, traducido in t["lang_name"].items():
        if traducido == seleccion_traducida and original in IDIOMAS_APRENDER.keys():
            idioma_seleccionado = original
            break
    if st.button(t["btn_continue"], use_container_width=True):
        st.session_state.idioma_activo = idioma_seleccionado
        st.query_params["lang_session"] = idioma_seleccionado 
        st.rerun()

elif st.session_state.idioma_activo not in st.session_state.usuario_db.get("niveles", {}):
    u = st.session_state.usuario_db
    lang_objetivo_original = st.session_state.idioma_activo
    lang_objetivo_traducido = t["lang_name"].get(lang_objetivo_original, lang_objetivo_original)
    
    st.markdown(f"<h2>{t['diag_title']}</h2>", unsafe_allow_html=True)
    st.info(t["diag_prompt"].format(lang_objetivo_traducido))
    
    st.markdown('<div class="modern-card">', unsafe_allow_html=True)
    st.markdown('<div class="mic-hero-wrapper">', unsafe_allow_html=True)
    st.markdown(f'<div class="mic-label">🎙️ {t["record"]} <strong>{lang_objetivo_traducido}</strong></div>', unsafe_allow_html=True)
    audio_diag = audio_recorder(text="", icon_size="4x", key="diag_mic_main")
    st.markdown('<div class="mic-sublabel">Max 10s</div>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)
    texto_diag_manual = st.text_input(t["write"] + " " + lang_objetivo_traducido)
    submit_diag = st.button(t["btn_send"])

    texto_final_diag = ""
    if submit_diag and texto_diag_manual: texto_final_diag = texto_diag_manual
    elif audio_diag and audio_diag != st.session_state.audio_diagnostico and len(audio_diag) > 1000:
        st.session_state.audio_diagnostico = audio_diag
        with st.spinner(t["listening"]):
            try:
                r = sr.Recognizer()
                with sr.AudioFile(io.BytesIO(audio_diag)) as source:
                    audio = r.record(source, duration=10)
                    texto_final_diag = r.recognize_google(audio, language=IDIOMAS_APRENDER[lang_objetivo_original]["stt"])
            except: st.warning(t["err_audio"])
            
    if texto_final_diag:
        with st.spinner(t["diag_analyzing"]):
            nivel_detectado = evaluar_nivel(texto_final_diag, lang_objetivo_original, idioma_nativo)
            niveles_actuales = u.get("niveles", {})
            niveles_actuales[lang_objetivo_original] = nivel_detectado
            db.collection("usuarios").document(u["correo"]).update({"niveles": niveles_actuales})
            st.session_state.usuario_db["niveles"] = niveles_actuales
            st.session_state.diag_completado = True
            st.session_state.diag_mensaje = t["diag_success"].format(lang_objetivo_traducido, nivel_detectado)

    if st.session_state.get("diag_completado"):
        st.success(st.session_state.diag_mensaje)
        if st.button("Ir al panel principal 🚀", use_container_width=True):
            st.session_state.diag_completado = False
            st.rerun()

# --- PANTALLA 4: DASHBOARD PRINCIPAL ---
else:
    u = st.session_state.usuario_db
    correo_admin = st.secrets.get("ADMIN_EMAIL", "")
    es_admin = (u.get("correo") == correo_admin) and correo_admin != ""

    p = "\U0001f451 ADMIN PRO" if es_admin else u.get("plan", "Free")
    lim_f = 999999 if es_admin else (5 if p=="Free" else (20 if p=="Standard" else 100))
    lim_s = 30 if es_admin else (5 if p=="Free" else 10)
    lim_c = 1000 if es_admin else (200 if p=="Free" else 400)

    lang_activo_original = st.session_state.idioma_activo
    lang_activo_traducido = t["lang_name"].get(lang_activo_original, lang_activo_original)
    nivel_activo = u.get("niveles", {}).get(lang_activo_original, "A1")

    # Header: greeting (left) + settings popover (right)
    hdr_c1, hdr_c2 = st.columns([5, 1])
    with hdr_c1:
        _gh  = t["greeting"] + ", " + u["nombres"]
        _pl  = "Plan " + str(p) + " | " + lang_activo_traducido + " \u00b7 " + nivel_activo
        st.markdown(
            '<div style="text-align:center; padding:4px 0 6px 0;">' +
            '<div style="font-size:1.9rem; font-weight:800; color:#FFFFFF;">' + _gh + '</div>' +
            '<div style="font-size:0.85rem; color:#7A84A0; margin-top:2px;">' + _pl + '</div></div>',
            unsafe_allow_html=True
        )
    with hdr_c2:
        with st.popover("\u2699\ufe0f"):
            st.write("**" + t["settings"] + "**")
            if st.button(t["change_lang"], use_container_width=True, key="hdr_clang"):
                st.session_state.idioma_activo = None
                if "lang_session" in st.query_params: del st.query_params["lang_session"]
                st.rerun()
            if st.button(t["logout"], use_container_width=True, key="hdr_logout"):
                st.session_state.usuario_db = None
                st.session_state.idioma_activo = None
                if "user_session" in st.query_params: del st.query_params["user_session"]
                if "lang_session" in st.query_params: del st.query_params["lang_session"]
                st.rerun()

    # TABS — always 3, visible for all users (upgrade always shown)
    tab_train, tab_agent, tab_upgrade = st.tabs([
        t["tab_train"], t["tab_agent"], t["tab_upgrade"]
    ])

    # ── TAB 1: ENTRENAMIENTO ──────────────────────────────────────────────────
    with tab_train:
        lang_stt = IDIOMAS_APRENDER[lang_activo_original]["stt"]
        lang_tts = IDIOMAS_APRENDER[lang_activo_original]["tts"]

        if u["frases_usadas_hoy"] >= lim_f and not es_admin:
            st.error(t["limit_reached"])
        else:
            # MIC HERO with glow wrapper
            mic_label_html = (
                '<div class="mic-glow-section">' +
                '<div class="mic-label">\U0001f399\ufe0f ' + t["record"] + ' <strong>' + lang_activo_traducido + '</strong></div>' +
                '<div class="mic-glow-wrapper">'
            )
            st.markdown(mic_label_html, unsafe_allow_html=True)
            audio_bytes = audio_recorder(text="", icon_size="4x", key="hero_mic_main")
            st.markdown(
                '</div>' +
                '<div class="mic-sublabel">Max ' + str(lim_s) + 's &nbsp;\u00b7&nbsp; ' + t["hero_desc"] + '</div>' +
                '</div>',
                unsafe_allow_html=True
            )

            # Write alternative (expander)
            with st.form("form_texto", clear_on_submit=False):
                texto_escrito = st.text_input(t["write"] + " " + lang_activo_traducido + ":")
                submit_texto  = st.form_submit_button(t["btn_send"])

            final_text = ""
            if submit_texto and texto_escrito:
                if len(texto_escrito) > lim_c: st.error(t["err_char"].format(lim_c))
                else:
                    final_text = texto_escrito
                    st.session_state.ultimo_audio = audio_bytes
            elif audio_bytes and audio_bytes != st.session_state.ultimo_audio and len(audio_bytes) > 1000:
                st.session_state.ultimo_audio = audio_bytes
                with st.spinner(t["listening"]):
                    try:
                        r = sr.Recognizer()
                        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                            r.adjust_for_ambient_noise(source, duration=0.5)
                            audio = r.record(source, duration=lim_s)
                            final_text = r.recognize_google(audio, language=lang_stt)
                            st.success("\U0001f3a4: " + final_text)
                    except: st.error(t["err_audio"])

            if final_text and final_text != st.session_state.ultima_frase:
                with st.spinner(t["analyzing"] + "..."):
                    st.session_state.ultima_frase = final_text
                    res = procesar_con_gemini(final_text, lang_activo_original, idioma_nativo)
                    if "error" in res: st.warning(res["error"])
                    else:
                        st.write("---")
                        st.metric(t["score"], str(res.get("puntuacion", "N/A")) + "/10")
                        st.success("\u2705 " + t["correction"] + " **" + str(res.get("correccion", "")) + "**")
                        st.info("\U0001f5e3\ufe0f " + t["pronunciation"] + " " + str(res.get("pronunciacion", "")))
                        st.info("\U0001f4a1 " + t["tip"] + " " + str(res.get("tips", "")))
                        try:
                            tts = gTTS(text=res.get("correccion", ""), lang=lang_tts)
                            tts.save("feedback.mp3"); st.audio("feedback.mp3")
                        except: pass
                        doc_ref = db.collection("usuarios").document(u["correo"])
                        doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                        st.session_state.usuario_db["frases_usadas_hoy"] += 1
            elif final_text and final_text == st.session_state.ultima_frase:
                st.warning(t["repeat"])

        # Progress bottom bar
        texto_contador = "\u221e" if es_admin else str(st.session_state.usuario_db["frases_usadas_hoy"]) + " / " + str(lim_f)
        prog_val = min(st.session_state.usuario_db["frases_usadas_hoy"] / lim_f, 1.0) if not es_admin else 1.0
        st.markdown('<div style="margin-top:20px;">', unsafe_allow_html=True)
        st.progress(prog_val)
        st.markdown(
            '<div style="text-align:center;font-size:0.8rem;color:#7A84A0;margin-top:4px;">' +
            texto_contador + " " + t["trainings"] + '</div></div>',
            unsafe_allow_html=True
        )

    # ── TAB 2: RUTAS DE ESTUDIO ───────────────────────────────────────────────
    with tab_agent:
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        modo_elegido = st.radio(t["choose_mode"], [t["mode_fund"], t["mode_real"]], horizontal=True)
        st.write("---")

        TEMAS_FUNDAMENTOS = t["topics"]
        progreso_key  = "progreso_" + lang_activo_original
        leccion_actual = u.get(progreso_key, 0)
        es_fundamentos = (modo_elegido == t["mode_fund"])

        if es_fundamentos:
            st.subheader(t["mode_fund"])
            st.write(t["mode_fund_desc"])
            if leccion_actual < len(TEMAS_FUNDAMENTOS):
                tema_actual = TEMAS_FUNDAMENTOS[leccion_actual]
                # Lesson cards
                show_count = min(leccion_actual + 5, len(TEMAS_FUNDAMENTOS))
                for i in range(show_count):
                    tema = TEMAS_FUNDAMENTOS[i]
                    lbl  = t["lesson_txt"] + " " + str(i+1) + "/" + str(len(TEMAS_FUNDAMENTOS)) + ": " + tema
                    if i == leccion_actual:
                        st.markdown('<div class="lesson-card-active">\U0001f513 ' + lbl + '</div>', unsafe_allow_html=True)
                    elif i < leccion_actual:
                        st.markdown('<div class="lesson-card-done">\u2705 ' + lbl + '</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="lesson-card-locked">\U0001f512 ' + lbl + '</div>', unsafe_allow_html=True)
            else:
                tema_actual = "Repaso General Avanzado"
                st.success("\U0001f31f Has completado todos los fundamentos.")
        else:
            st.subheader(t["mode_real"])
            st.write(t["mode_real_desc"])
            tema_actual = "Role-play conversacional"

        if u["frases_usadas_hoy"] >= lim_f and not es_admin:
            st.error(t["limit_reached"])
        else:
            sesion_reto_key = "reto_" + lang_activo_original
            audio_reto_key  = "audio_reto_" + lang_activo_original
            if sesion_reto_key not in st.session_state:
                st.session_state[sesion_reto_key] = ""
                st.session_state[audio_reto_key]  = ""

            reto_activo   = st.session_state.get(sesion_reto_key) != ""
            ya_entreno_hoy = u["frases_usadas_hoy"] > 0

            if not st.session_state.get("reto_superado"):
                btn_texto = t["btn_next"] if (reto_activo or ya_entreno_hoy) else t["btn_gen_lesson"]
                if st.button(btn_texto, use_container_width=True):
                    with st.spinner(t["prep_lesson"]):
                        if es_fundamentos:
                            prompt_reto = (
                                "Act\u00faa como un tutor divertido. El usuario habla " + idioma_nativo +
                                " y aprende " + lang_activo_original + ". Tema: '" + tema_actual +
                                "'. Elige al azar UNA mec\u00e1nica:\n"
                                "1. 'Repetici\u00f3n': Ens\u00e9\u00f1ale 3 palabras y pide pronunciar una.\n"
                                "2. 'Mini-Quiz': Pregunta de opci\u00f3n m\u00faltiple, pide pronunciar en voz alta.\n"
                                "REGLA: NO HTML. Devuelve SOLO JSON: "
                                "{{'leccion_texto': 'Mensaje en " + idioma_nativo + " sin HTML', "
                                "'texto_audio': 'Solo palabras en " + lang_activo_original + " separadas por comas'}}"
                            )
                        else:
                            prompt_reto = (
                                "El usuario habla " + idioma_nativo + " y practica " + lang_activo_original +
                                ". Inventa un escenario de Role-play. NO HTML. "
                                "Devuelve SOLO JSON: {{'leccion_texto': 'Contexto en " + idioma_nativo +
                                " + primera pregunta en " + lang_activo_original + " sin HTML', "
                                "'texto_audio': 'Solo la pregunta en " + lang_activo_original + "'}}"
                            )
                        try:
                            client = genai.Client(api_key=API_KEY_FREE)
                            res_reto = client.models.generate_content(model="gemini-3.1-flash-lite-preview", contents=prompt_reto)
                            res_json = json.loads(res_reto.text.replace("```json\n","").replace("```","").strip())
                            st.session_state[sesion_reto_key] = res_json.get("leccion_texto","Error")
                            st.session_state[audio_reto_key]  = res_json.get("texto_audio","")
                            st.rerun()
                        except: st.error("Servidores ocupados. Intenta de nuevo.")

            if st.session_state.get(sesion_reto_key):
                st.markdown("> \U0001f916 **Agente IA:** " + st.session_state[sesion_reto_key])
                if st.session_state.get(audio_reto_key):
                    try:
                        tts_r = gTTS(text=st.session_state[audio_reto_key], lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                        tts_r.save("lesson_audio.mp3"); st.audio("lesson_audio.mp3")
                    except: pass
                st.write("---")
                col_m1, col_m2, col_m3 = st.columns([1,1,1])
                with col_m2:
                    audio_agent = audio_recorder(text="", icon_size="2x", key="mic_agent_main")
                with st.expander(t["write"]):
                    with st.form("form_agent", clear_on_submit=False):
                        texto_agent  = st.text_input("Escribe:", key="txt_agent")
                        submit_agent = st.form_submit_button(t["btn_send"])
                final_agent = ""
                if submit_agent and texto_agent: final_agent = texto_agent
                elif audio_agent and audio_agent != st.session_state.get("ultimo_audio_agent") and len(audio_agent) > 1000:
                    st.session_state["ultimo_audio_agent"] = audio_agent
                    with st.spinner(t["listening"]):
                        try:
                            r = sr.Recognizer()
                            with sr.AudioFile(io.BytesIO(audio_agent)) as source:
                                audio = r.record(source, duration=lim_s)
                                final_agent = r.recognize_google(audio, language=IDIOMAS_APRENDER[lang_activo_original]["stt"])
                                st.success("\U0001f3a4: " + final_agent)
                        except: st.error(t["err_audio"])
                if final_agent:
                    with st.spinner(t["analyzing"] + "..."):
                        prompt_eval = (
                            "Actúa como profesor de " + lang_activo_original + ". El usuario habla " + idioma_nativo +
                            ". El reto era: '" + st.session_state[sesion_reto_key] +
                            "'. El usuario respondió: '" + final_agent +
                            "'. Evalúa. Devuelve SOLO JSON: {'correccion': 'FRASE CORREGIDA EN " + lang_activo_original +
                            "', 'pronunciacion': 'fonética en " + idioma_nativo +
                            "', 'tips': 'Explica en " + idioma_nativo + " si logró el reto', 'puntuacion': '1-10'}"
                        )
                        try:
                            res_eval = genai.Client(api_key=API_KEY_FREE).models.generate_content(
                                model="gemini-3.1-flash-lite-preview", contents=prompt_eval)
                            res_json = json.loads(res_eval.text.replace("```json\n","").replace("```","").strip())
                            st.metric(t["score"], str(res_json.get("puntuacion","N/A")) + "/10")
                            st.success("\u2705 " + t["correction"] + " " + str(res_json.get("correccion","")))
                            st.info("\U0001f5e3\ufe0f " + t["pronunciation"] + " " + str(res_json.get("pronunciacion","")))
                            st.info("\U0001f4a1 " + t["tip"] + " " + str(res_json.get("tips","")))
                            try:
                                tts = gTTS(text=res_json.get("correccion",""), lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                                tts.save("feedback_agent.mp3"); st.audio("feedback_agent.mp3")
                            except: pass
                            doc_ref = db.collection("usuarios").document(u["correo"])
                            doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                            st.session_state.usuario_db["frases_usadas_hoy"] += 1
                            try: puntos = int(str(res_json.get("puntuacion","0")).replace("/10","").strip())
                            except: puntos = 5
                            if puntos >= 7:
                                st.balloons()
                                if es_fundamentos:
                                    st.success(t["lesson_passed"])
                                    doc_ref.update({progreso_key: firestore.Increment(1)})
                                    st.session_state.usuario_db[progreso_key] = leccion_actual + 1
                                else: st.success(t["role_passed"])
                                st.session_state.reto_superado = True
                        except: st.warning("Error evaluando. Intenta de nuevo.")

            if st.session_state.get("reto_superado"):
                if st.button(t["btn_next"], use_container_width=True, key="btn_continuar_reto"):
                    st.session_state[sesion_reto_key] = ""
                    st.session_state[audio_reto_key]  = ""
                    st.session_state.reto_superado = False
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── TAB 3: MEJORAR PLAN (always visible) ─────────────────────────────────
    with tab_upgrade:
        _cur = "Free" if "Free" in str(p) else ("Standard" if "Standard" in str(p) else "Pro")
        _up_tagline   = t.get("up_tagline",   "Elige el plan perfecto para ti")
        _up_popular   = t.get("up_popular",   "\u2b50 M\u00c1S POPULAR")
        _up_premium   = t.get("up_premium",   "\U0001f451 PREMIUM")
        _up_cur_badge = t.get("up_cur_badge", "Plan actual")
        _up_active    = t.get("up_active",    "\u2714 Tu plan actual")
        _up_subscribe = t.get("up_subscribe", "Suscribirse")
        _up_footer    = t.get("up_footer",    "\U0001f512 Pagos seguros \u00b7 Cancela cuando quieras")
        st.markdown(
            '<div style="text-align:center;padding:16px 0 8px 0;">' +
            '<div style="font-size:1.5rem;font-weight:800;color:#FFFFFF;">' + t["up_title"] + '</div>' +
            '<div style="font-size:0.85rem;color:#7A84A0;margin-top:4px;">' + _up_tagline + '</div></div>',
            unsafe_allow_html=True
        )
        fb = '<span style="background:#374151;color:#9CA3AF;font-size:0.7rem;padding:2px 8px;border-radius:10px;float:right;">' + _up_cur_badge + '</span>' if _cur=="Free" else ""
        st.markdown('<div class="plan-card-free">' + fb + '<div style="font-weight:700;color:#9CA3AF;">\U0001f193 FREE — $0</div><div style="font-size:0.85rem;color:#6B7280;margin-top:4px;">' + t.get("desc_free","5/day") + '</div></div>', unsafe_allow_html=True)
        sb = '<span style="background:#FF7F50;color:#FFF;font-size:0.7rem;padding:2px 8px;border-radius:10px;float:right;">' + _up_popular + '</span>'
        st.markdown('<div class="plan-card-std">' + sb + '<div style="font-size:1.1rem;font-weight:800;color:#FF7F50;">\u2728 STANDARD — $3</div><div style="font-size:0.85rem;color:#CBD5E0;margin-top:4px;">' + t.get("desc_standard","20/day") + '</div></div>', unsafe_allow_html=True)
        if _cur == "Standard":
            st.markdown('<div style="text-align:center;padding:4px 0;font-size:0.85rem;color:#FF7F50;">' + _up_active + '</div>', unsafe_allow_html=True)
        elif _cur != "Pro":
            if st.button(_up_subscribe + " $3/mes \u2192", use_container_width=True, key="btn_std"):
                st.info("(Pronto: pagos directos)")
        pb = '<span style="background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;font-size:0.7rem;padding:2px 8px;border-radius:10px;float:right;">' + _up_premium + '</span>'
        st.markdown('<div class="plan-card-pro">' + pb + '<div style="font-size:1.1rem;font-weight:800;color:#FFB347;">\U0001f451 PRO — $8</div><div style="font-size:0.85rem;color:#CBD5E0;margin-top:4px;">' + t.get("desc_pro","100/day") + '</div></div>', unsafe_allow_html=True)
        if _cur == "Pro":
            st.markdown('<div style="text-align:center;padding:4px 0;font-size:0.85rem;color:#FFB347;">' + _up_active + '</div>', unsafe_allow_html=True)
        else:
            if st.button(_up_subscribe + " $8/mes \u2192", use_container_width=True, key="btn_pro"):
                st.info("(Pronto: pagos directos)")
        st.markdown('<div style="text-align:center;color:#4B5563;font-size:0.75rem;margin-top:12px;">' + _up_footer + '</div>', unsafe_allow_html=True)
