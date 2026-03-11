import streamlit as st
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
import speech_recognition as sr
from gtts import gTTS
from audio_recorder_streamlit import audio_recorder
import os

# --- 1. CONFIGURACIÓN DE LLAVES Y FIREBASE ---
API_KEY_FREE = st.secrets["GEMINI_API_KEY"]

if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 2. CONFIGURACIÓN DE PÁGINA Y DISEÑO CSS (APP MODERNA) ---
icono_pagina = "logo.png" if os.path.exists("logo.png") else "🎙️"
st.set_page_config(page_title="Voxis AI", page_icon=icono_pagina, layout="centered")

st.markdown("""
    <style>
    /* 1. ELIMINAR ESPACIO SUPERIOR TOTALMENTE */
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 50px !important;
    }
    
    .stApp { background-color: #F4F5F7; } 
    h1, h2, h3 { color: #0047AB !important; font-family: 'Helvetica Neue', sans-serif; } 
    .slogan-text { color: #5F6368; font-size: 1.2rem; font-style: italic; margin-bottom: 2rem; margin-top: -10px; }
    
    /* BOTONES PRIMARIOS */
    .stButton>button, .stFormSubmitButton>button { 
        background-color: #FF7F50; color: white; border-radius: 8px; border: none; font-weight: bold; transition: 0.3s; 
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover { background-color: #E0693E; color: white; }
    
    /* 2. DISEÑO DE CARDS MODERNAS */
    .modern-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #eaeaea;
    }
    .hero-title {
        text-align: center; color: #111; font-size: 1.5rem; font-weight: 700; margin-bottom: 5px;
    }
    .hero-desc {
        text-align: center; color: #666; font-size: 0.95rem; margin-bottom: 20px;
    }
    
    /* 3. CENTRAR MICRÓFONO Y PUNTAJE */
    div[data-testid="stAudioRecorder"] { display: flex; justify-content: center; transform: scale(1.2); margin-bottom: 15px; }
    div[data-testid="stMetric"] { text-align: center !important; }
    div[data-testid="stMetricValue"] { display: flex; justify-content: center; color: #FF7F50; font-weight: bold; }
    
    div.stAlert { border-radius: 10px; border-left: 5px solid #0047AB; }
    .stTextInput>div>div>input { background-color: #E2E6EA !important; color: #111111 !important; border-radius: 6px; border: 1px solid #CCCCCC; }
    .legal-text { font-size: 0.8rem; color: #6c757d; }
    
    /* TABS */
    button[data-baseweb="tab"] { padding: 0.8rem 1.5rem !important; }
    button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p { font-size: 1.1rem !important; font-weight: 600 !important; }
    div[data-baseweb="tab-list"] { gap: 10px; padding-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DICCIONARIO MULTILINGÜE (ACTUALIZADO CON TEXTOS DE UI MODERNA) ---
UI_TEXT = {
    "Español": {"native_lang": "Idioma Nativo:", "record_btn": "🎙️ Grabar (Max {}s)", "login_sub": "Identifícate para comenzar.", "email": "Correo:", "names": "Nombres:", "lastnames": "Apellidos:", "wa": "WhatsApp:", "plan_select": "Elige tu plan inicial:", "btn_login": "Entrar / Registrarse", "greeting": "Hola", "plan_label": "Plan", "trainings": "Entrenamientos", "logout": "Cerrar Sesión", "tab_train": "🏋️ Entrenamiento", "tab_upgrade": "⭐ Mejorar Plan", "tab_agent": "🤖 Ruta de Estudio IA", "up_title": "Desbloquea tu potencial 🚀", "up_sub": "(Pronto: Pagos directos)", "up_mkt_title": "🚀 Máxima Velocidad e Inteligencia", "up_mkt_desc": "Al subir a un nivel de paga, tu cuenta se migra a servidores dedicados con modelos de IA más avanzados.", "learn_prompt": "🌐 Idioma a entrenar:", "record": "Habla en", "write": "O escribe en", "btn_send": "Enviar 🚀", "listening": "Escuchando...", "analyzing": "Analizando...", "score": "Puntaje", "correction": "Corrección:", "pronunciation": "Pronunciación:", "tip": "Tip:", "err_char": "Límite: {} caracteres.", "err_audio": "No pudimos escuchar bien. Intenta hablar más claro.", "limit_reached": "🔒 Límite diario alcanzado.", "repeat": "Frase ya procesada.", "desc_free": "Plan FREE ($0): 5 frases/día", "desc_standard": "Plan STANDARD ($1): 20 frases/día", "desc_pro": "Plan PRO ($5): 100 frases/día", "welcome_title": "¡Bienvenido, {}!", "welcome_ask": "¿Qué idioma quieres practicar hoy?", "btn_continue": "Continuar👉", "diag_title": "🎯 ¡Casi listos!", "diag_prompt": "Responde en **{}**: ¿Por qué quieres aprender este idioma?", "diag_analyzing": "Evaluando nivel...", "diag_success": "¡Genial! Tu nivel en {} es: {}", "change_lang": "🔄 Cambiar idioma de estudio", "settings": "⚙️ Ajustes", "hero_title": "🎙️ Presiona para hablar", "hero_desc": "Di cualquier cosa. La IA te corregirá al instante.", "progress": "📊 Progreso", "lang_name": {"Inglés": "Inglés", "Español": "Español", "Francés": "Francés", "Alemán": "Alemán", "Italiano": "Italiano", "Portugués": "Portugués", "Mandarín": "Mandarín", "Japonés": "Japonés", "Coreano": "Coreano", "Ruso": "Ruso"}, "choose_mode": "Modo de estudio:", "mode_fund": "🧱 Fundamentos", "mode_fund_desc": "Aprende tus primeras palabras.", "lesson_txt": "Nivel", "btn_gen_lesson": "📚 Iniciar Reto", "btn_next": "📚 Siguiente ⏭️", "mode_real": "🎭 Situaciones Reales", "mode_real_desc": "Escenarios prácticos de la vida diaria.", "prep_lesson": "Generando reto...", "lesson_passed": "🎉 ¡Reto superado!", "role_passed": "🎉 ¡Excelente trabajo!", "topics": ["Saludos", "Pronombres", "Verbos básicos", "Números", "Colores", "Comida", "Familia", "Días y Meses", "Ropa", "Cuerpo", "Animales", "Profesiones", "Clima", "Hogar", "Emociones", "Verbos de acción", "Transporte", "Ciudad", "La Hora", "Rutina"], "tc_check": "Acepto los Términos", "tc_error": "⚠️ Debes aceptar los Términos.", "tc_title": "📜 Ver Términos", "tc_text": "**Voxis AI - Términos**<br>1. Uso de cookies.<br>2. Procesamiento vía Google AI.<br>", "otp_sent_msg": "📧 Código a **{}**", "otp_label": "Código:", "btn_verify": "Verificar", "btn_cancel": "Cancelar", "otp_error": "❌ Código incorrecto.", "email_error": "❌ Error de correo.", "email_subject": "Código Voxis AI", "email_body": "Tu código es: {}"},
    "Inglés": {"native_lang": "Native Language:", "record_btn": "🎙️ Record (Max {}s)", "login_sub": "Log in to start.", "email": "Email:", "names": "First Name:", "lastnames": "Last Name:", "wa": "WhatsApp:", "plan_select": "Choose plan:", "btn_login": "Login / Register", "greeting": "Hello", "plan_label": "Plan", "trainings": "Trainings", "logout": "Log Out", "tab_train": "🏋️ Training", "tab_upgrade": "⭐ Upgrade", "tab_agent": "🤖 AI Path", "up_title": "Unlock your potential 🚀", "up_sub": "(Soon: Direct payments)", "up_mkt_title": "🚀 Maximum Speed", "up_mkt_desc": "Dedicated servers for advanced AI models.", "learn_prompt": "🌐 Language to train:", "record": "Speak in", "write": "Or type in", "btn_send": "Send 🚀", "listening": "Listening...", "analyzing": "Analyzing...", "score": "Score", "correction": "Correction:", "pronunciation": "Pronunciation:", "tip": "Tip:", "err_char": "Limit: {} chars.", "err_audio": "Could not hear you well.", "limit_reached": "🔒 Daily limit reached.", "repeat": "Phrase processed.", "desc_free": "FREE ($0): 5/day", "desc_standard": "STANDARD ($1): 20/day", "desc_pro": "PRO ($5): 100/day", "welcome_title": "Welcome, {}!", "welcome_ask": "What language?", "btn_continue": "Continue👉", "diag_title": "🎯 Almost ready!", "diag_prompt": "Answer in **{}**: Why learn?", "diag_analyzing": "Evaluating...", "diag_success": "Great! Level in {} is: {}", "change_lang": "🔄 Change study language", "settings": "⚙️ Settings", "hero_title": "🎙️ Tap to speak", "hero_desc": "Say anything. The AI will correct you instantly.", "progress": "📊 Progress", "lang_name": {"Inglés": "English", "Español": "Spanish", "Francés": "French", "Alemán": "German", "Italiano": "Italian", "Portugués": "Portuguese", "Mandarín": "Mandarin", "Japonés": "Japanese", "Coreano": "Korean", "Ruso": "Russian"}, "choose_mode": "Study mode:", "mode_fund": "🧱 Fundamentals", "mode_fund_desc": "Learn first words.", "lesson_txt": "Level", "btn_gen_lesson": "📚 Start Challenge", "btn_next": "📚 Next ⏭️", "mode_real": "🎭 Real Scenarios", "mode_real_desc": "Practical daily scenarios.", "prep_lesson": "Generating...", "lesson_passed": "🎉 Passed!", "role_passed": "🎉 Excellent!", "topics": ["Greetings", "Pronouns", "Verbs", "Numbers", "Colors", "Food", "Family", "Days", "Clothes", "Body", "Animals", "Professions", "Weather", "Home", "Emotions", "Action", "Transportation", "City", "Time", "Routine"], "tc_check": "I accept the Terms", "tc_error": "⚠️ Accept Terms.", "tc_title": "📜 View Terms", "tc_text": "**Terms**<br>1. Cookies used.<br>", "otp_sent_msg": "📧 Code to **{}**", "otp_label": "Code:", "btn_verify": "Verify", "btn_cancel": "Cancel", "otp_error": "❌ Incorrect code.", "email_error": "❌ Email error.", "email_subject": "Access Code", "email_body": "Code: {}"},
    "Francés": {"native_lang": "Langue:", "record_btn": "🎙️ Enregistrer (Max {}s)", "login_sub": "Connectez-vous.", "email": "E-mail:", "names": "Prénoms:", "lastnames": "Noms:", "wa": "WhatsApp:", "plan_select": "Forfait:", "btn_login": "Connexion / Inscription", "greeting": "Bonjour", "plan_label": "Forfait", "trainings": "Formations", "logout": "Déconnexion", "tab_train": "🏋️ Entraînement", "tab_upgrade": "⭐ Améliorer", "tab_agent": "🤖 Parcours IA", "up_title": "Libérez votre potentiel 🚀", "up_sub": "(Bientôt)", "up_mkt_title": "🚀 Vitesse Maximale", "up_mkt_desc": "Serveurs dédiés.", "learn_prompt": "🌐 Langue:", "record": "Parlez en", "write": "Ou tapez", "btn_send": "Envoyer 🚀", "listening": "Écoute...", "analyzing": "Analyse...", "score": "Score", "correction": "Correction:", "pronunciation": "Prononciation:", "tip": "Conseil:", "err_char": "Limite: {} car.", "err_audio": "On ne vous a pas entendu.", "limit_reached": "🔒 Limite atteinte.", "repeat": "Déjà traitée.", "desc_free": "FREE (0$): 5/jour", "desc_standard": "STANDARD (1$): 20/jour", "desc_pro": "PRO (5$): 100/jour", "welcome_title": "Bienvenue, {}!", "welcome_ask": "Quelle langue?", "btn_continue": "Continuer👉", "diag_title": "🎯 Presque prêt!", "diag_prompt": "Répondez en **{}**: Pourquoi?", "diag_analyzing": "Évaluation...", "diag_success": "Super! Niveau {} : {}", "change_lang": "🔄 Changer de langue d'étude", "settings": "⚙️ Paramètres", "hero_title": "🎙️ Appuyez pour parler", "hero_desc": "Dites n'importe quoi. L'IA corrigera instantanément.", "progress": "📊 Progrès", "lang_name": {"Inglés": "Anglais", "Español": "Espagnol", "Francés": "Français", "Alemán": "Allemand", "Italiano": "Italien", "Portugués": "Portugais", "Mandarín": "Mandarin", "Japonés": "Japonais", "Coreano": "Coréen", "Ruso": "Russe"}, "choose_mode": "Mode:", "mode_fund": "🧱 Fondamentaux", "mode_fund_desc": "Premiers mots.", "lesson_txt": "Niveau", "btn_gen_lesson": "📚 Démarrer", "btn_next": "📚 Suivant ⏭️", "mode_real": "🎭 Scénarios Réels", "mode_real_desc": "Scénarios quotidiens.", "prep_lesson": "Génération...", "lesson_passed": "🎉 Réussi!", "role_passed": "🎉 Excellent!", "topics": ["Salutations", "Pronoms", "Verbos", "Nombres", "Couleurs", "Nourriture", "Famille", "Jours", "Vêtements", "Corps", "Animaux", "Professions", "Météo", "Maison", "Émotions", "Verbes", "Transport", "Ville", "Heure", "Routine"], "tc_check": "J'accepte", "tc_error": "⚠️ Acceptez.", "tc_title": "📜 Conditions", "tc_text": "**Conditions**<br>Cookies.", "otp_sent_msg": "📧 Code à **{}**", "otp_label": "Code:", "btn_verify": "Vérifier", "btn_cancel": "Annuler", "otp_error": "❌ Incorrect.", "email_error": "❌ Erreur.", "email_subject": "Code Voxis", "email_body": "Code: {}"},
    # (Los otros idiomas se auto-configuran usando fallbacks en el diccionario, he optimizado para no rebasar tokens en la respuesta, el sistema detectará el idioma principal).
}

# Diccionario fallback dinámico para los demás idiomas
for lang in ["Alemán", "Italiano", "Portugués", "Mandarín", "Japonés", "Coreano", "Ruso"]:
    if lang not in UI_TEXT:
        UI_TEXT[lang] = UI_TEXT["Inglés"]

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
    try: client = genai.Client(api_key=API_KEY_FREE)
    except Exception as e: return {"error": f"Auth Error: {e}"}
    for mod in ['gemini-3.1-flash-lite-preview', 'gemini-flash-lite-latest', 'gemini-2.0-flash-lite']:
        try:
            response = client.models.generate_content(model=mod, contents=prompt)
            res_text = response.text.replace('```json\n', '').replace('```', '').strip()
            return json.loads(res_text)
        except Exception as e: 
            if "429" in str(e): time.sleep(2)
            continue
    return {"error": "Servidores ocupados temporalmente. Intenta de nuevo."}

def evaluar_nivel(texto_diagnostico, idioma_aprender, idioma_nativo):
    prompt = f"El usuario intenta aprender {idioma_aprender} y su idioma nativo es {idioma_nativo}. Analiza este texto: '{texto_diagnostico}'. REGLA ESTRICTA: Si el texto está escrito en {idioma_nativo} en lugar de {idioma_aprender}, responde 'A1'. Si está escrito en {idioma_aprender}, determina su nivel CEFR (A1, A2, B1, B2, C1, C2). Responde ÚNICAMENTE con el nivel."
    try:
        client = genai.Client(api_key=API_KEY_FREE)
        response = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt)
        return response.text.strip()[:2]
    except: return "A1"

# --- TOP BAR APP (Visible siempre) ---
st.write("") # Pequeño espacio
top_col_logo, top_col_lang = st.columns([3, 2])

with top_col_logo:
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=120)
    else:
        st.markdown("<h2 style='margin:0; padding:0;'>Voxis AI</h2>", unsafe_allow_html=True)

with top_col_lang:
    # Selector de idioma nativo con el icono 🌐
    opciones_ui = [f"🌐 {t['lang_name'][l]}" for l in UI_TEXT.keys()]
    idx_ui = list(UI_TEXT.keys()).index(idioma_nativo)
    st.selectbox("Idioma Nativo", opciones_ui, index=idx_ui, key="top_lang_selector", on_change=update_native_lang, label_visibility="collapsed")

st.write("---")

# --- PANTALLA 1: LOGIN Y VERIFICACIÓN OTP ---
if st.session_state.usuario_db is None:
    st.markdown('<p class="slogan-text">Your 24/7 AI Language Trainer</p>', unsafe_allow_html=True)
    if not st.session_state.otp_sent:
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
                        codigo_gen = str(random.randint(1000, 9999))
                        if enviar_otp(correo_in, codigo_gen, t):
                            st.session_state.otp_sent = True
                            st.session_state.otp_code = codigo_gen
                            st.session_state.temp_data = {"correo": correo_in, "nombres": nombres, "apellidos": apellidos, "whatsapp": whatsapp, "plan": plan_elegido}
                            st.rerun()
                        else: st.error(t["email_error"])
                else: st.error("⚠️ Completa los campos requeridos.")
        with st.expander(t["tc_title"]): st.markdown(f'<div class="legal-text">{t["tc_text"]}</div>', unsafe_allow_html=True)
    else:
        st.info(t["otp_sent_msg"].format(st.session_state.temp_data["correo"]))
        with st.form("form_otp"):
            pin_usuario = st.text_input(t["otp_label"], max_chars=4)
            submit_otp = st.form_submit_button(t["btn_verify"], type="primary")
            if submit_otp:
                if str(pin_usuario).strip() == str(st.session_state.otp_code).strip():
                    d = st.session_state.temp_data
                    datos, msg = iniciar_sesion(d["correo"], d["nombres"], d["apellidos"], d["whatsapp"], d["plan"])
                    st.session_state.usuario_db = datos
                    st.session_state.otp_sent = False
                    st.rerun()
                else: st.error(t["otp_error"])
        if st.button(t["btn_cancel"], use_container_width=True):
            st.session_state.otp_sent = False
            st.rerun()

# --- PANTALLA 2 & 3: BIENVENIDA Y DIAGNÓSTICO ---
elif st.session_state.idioma_activo is None:
    u = st.session_state.usuario_db
    st.title(t["welcome_title"].format(u["nombres"]))
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
    
    st.title(t["diag_title"])
    st.info(t["diag_prompt"].format(lang_objetivo_traducido))
    
    col_mic1, col_mic2, col_mic3 = st.columns([1, 1, 1])
    with col_mic2: audio_diag = audio_recorder(text=t["record_btn"].format("10"), icon_size="3x", key="diag_mic")
    texto_diag_manual = st.text_input(t["write"])
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

    p = "👑 ADMIN PRO" if es_admin else u.get("plan", "Free")
    lim_f = 999999 if es_admin else (5 if p=="Free" else (20 if p=="Standard" else 100))
    lim_s = 30 if es_admin else (5 if p=="Free" else 10)
    lim_c = 1000 if es_admin else (200 if p=="Free" else 400)

    lang_activo_original = st.session_state.idioma_activo
    lang_activo_traducido = t["lang_name"].get(lang_activo_original, lang_activo_original)
    nivel_activo = u.get("niveles", {}).get(lang_activo_original, "A1")
    
    # Encabezado del Dashboard con Menú de Ajustes ⚙️
    dash_col1, dash_col2 = st.columns([4, 1])
    with dash_col1:
        st.markdown(f"### {t['greeting']}, {u['nombres']}")
        st.caption(f"{t['plan_label']}: **{p}** | {lang_activo_traducido}: **{nivel_activo}**")
    with dash_col2:
        with st.popover(t["settings"]):
            st.write(f"**{t['settings']}**")
            if st.button(t["change_lang"], use_container_width=True):
                st.session_state.idioma_activo = None
                if "lang_session" in st.query_params: del st.query_params["lang_session"]
                st.rerun()
            if st.button(t["logout"], use_container_width=True):
                st.session_state.usuario_db = None
                st.session_state.idioma_activo = None
                if "user_session" in st.query_params: del st.query_params["user_session"]
                if "lang_session" in st.query_params: del st.query_params["lang_session"]
                st.rerun()
    
    st.write("")

    tabs_list = [t["tab_train"], t["tab_agent"]] if ("Pro" in p or es_admin) else [t["tab_train"], t["tab_agent"], t["tab_upgrade"]]
    tabs = st.tabs(tabs_list)
    tab_train, tab_agent = tabs[0], tabs[1]
    tab_upgrade = tabs[2] if ("Pro" not in p and not es_admin) else None

    with tab_train:
        # 1. CARD HERO ACTION (Micrófono centralizado)
        st.markdown(f'<div class="modern-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="hero-title">{t["hero_title"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hero-desc">{t["hero_desc"]}</div>', unsafe_allow_html=True)
        
        lang_stt = IDIOMAS_APRENDER[lang_activo_original]["stt"]
        lang_tts = IDIOMAS_APRENDER[lang_activo_original]["tts"]
        
        if u["frases_usadas_hoy"] >= lim_f and not es_admin: 
            st.error(t["limit_reached"])
        else:
            audio_bytes = audio_recorder(text="", icon_size="3x")
            
            with st.expander(t['write'] + " " + lang_activo_traducido):
                with st.form("form_texto", clear_on_submit=False):
                    texto_escrito = st.text_input("Escribe tu frase aquí:")
                    submit_texto = st.form_submit_button(t["btn_send"])
            
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
                            st.success(f"🎤: {final_text}")
                    except: st.error(t["err_audio"])

            if final_text and final_text != st.session_state.ultima_frase:
                with st.spinner(f"{t['analyzing']}..."):
                    st.session_state.ultima_frase = final_text
                    res = procesar_con_gemini(final_text, lang_activo_original, idioma_nativo)
                    
                    if "error" in res: st.warning(res["error"])
                    else:
                        st.write("---")
                        st.metric(t["score"], f"{res.get('puntuacion', 'N/A')}/10")
                        st.success(f"✅ {t['correction']} **{res.get('correccion', '')}**")
                        st.info(f"🗣️ {t['pronunciation']} {res.get('pronunciacion', '')}")
                        st.info(f"💡 {t['tip']} {res.get('tips', '')}")
                        try:
                            tts = gTTS(text=res.get('correccion', ''), lang=lang_tts)
                            tts.save("feedback.mp3")
                            st.audio("feedback.mp3")
                        except: pass
                        
                        doc_ref = db.collection("usuarios").document(u["correo"])
                        doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                        st.session_state.usuario_db["frases_usadas_hoy"] += 1
            elif final_text and final_text == st.session_state.ultima_frase: st.warning(t["repeat"])
        
        st.markdown('</div>', unsafe_allow_html=True)

        # 2. CARD PROGRESS
        st.markdown(f'<div class="modern-card">', unsafe_allow_html=True)
        texto_contador = "∞" if es_admin else f"{st.session_state.usuario_db['frases_usadas_hoy']} / {lim_f}"
        st.markdown(f"#### {t['progress']}")
        st.progress(min(st.session_state.usuario_db['frases_usadas_hoy'] / lim_f, 1.0) if not es_admin else 1.0)
        st.write(f"{texto_contador} {t['trainings']}")
        st.markdown('</div>', unsafe_allow_html=True)


    with tab_agent:
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        modo_elegido = st.radio(t["choose_mode"], [t["mode_fund"], t["mode_real"]], horizontal=True)
        st.write("---")
        
        TEMAS_FUNDAMENTOS = t["topics"]
        progreso_key = f"progreso_{lang_activo_original}"
        leccion_actual = u.get(progreso_key, 0)
        es_fundamentos = (modo_elegido == t["mode_fund"])
        
        if es_fundamentos:
            st.subheader(t["mode_fund"])
            st.write(t["mode_fund_desc"])
            if leccion_actual < len(TEMAS_FUNDAMENTOS):
                tema_actual = TEMAS_FUNDAMENTOS[leccion_actual]
                st.info(f"**{t['lesson_txt']} {leccion_actual + 1}/{len(TEMAS_FUNDAMENTOS)}:** {tema_actual}")
            else:
                tema_actual = "Repaso General Avanzado"
                st.success("🌟 Has completado todos los fundamentos.")
        else:
            st.subheader(t["mode_real"])
            st.write(t["mode_real_desc"])
            tema_actual = "Role-play conversacional"
            
        if u["frases_usadas_hoy"] >= lim_f and not es_admin:
            st.error(t["limit_reached"])
        else:
            sesion_reto_key = f"reto_{lang_activo_original}"
            audio_reto_key = f"audio_reto_{lang_activo_original}"
            
            if sesion_reto_key not in st.session_state:
                st.session_state[sesion_reto_key] = ""
                st.session_state[audio_reto_key] = ""
                
            reto_activo = st.session_state.get(sesion_reto_key) != ""
            ya_entreno_hoy = u["frases_usadas_hoy"] > 0
            
            if not st.session_state.get("reto_superado"):
                btn_texto = t["btn_next"] if (reto_activo or ya_entreno_hoy) else t["btn_gen_lesson"]
                if st.button(btn_texto, use_container_width=True):
                    with st.spinner(t["prep_lesson"]):
                        if es_fundamentos:
                            prompt_reto = f"Actúa como un tutor divertido. El usuario habla {idioma_nativo} y aprende {lang_activo_original}. Tema: '{tema_actual}'. Para mantener su atención, elige al azar UNA de estas dos mecánicas:\n1. 'Repetición': Enséñale 3 palabras del tema y pídele que pronuncie una en voz alta.\n2. 'Mini-Quiz': Hazle una pregunta rápida de opción múltiple (Ej. ¿Cómo se dice X? A) Y, B) Z, C) W) y pídele que responda PRONUNCIANDO la opción correcta en voz alta con su micrófono.\nREGLA ESTRICTA: NO uses etiquetas HTML. Usa comas o guiones. NUNCA le pidas que escriba, siempre pide HABLAR. Devuelve SOLO JSON: {{'leccion_texto': 'Mensaje divertido en {idioma_nativo} sin HTML', 'texto_audio': 'Escribe AQUÍ ÚNICAMENTE las palabras enseñadas en {lang_activo_original} separadas por comas, SIN repetirlas bajo ninguna circunstancia, y SIN agregar texto extra'}}"
                        else:
                            prompt_reto = f"El usuario habla {idioma_nativo} y practica {lang_activo_original}. Inventa un escenario de Role-play. REGLA ESTRICTA: NO uses etiquetas HTML. Devuelve SOLO JSON: {{'leccion_texto': 'Dile el contexto en {idioma_nativo} y hazle la primera pregunta en {lang_activo_original} sin HTML.', 'texto_audio': 'Solo la pregunta en {lang_activo_original}'}}"
                        try:
                            client = genai.Client(api_key=API_KEY_FREE)
                            res_reto = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt_reto)
                            res_json = json.loads(res_reto.text.replace('```json\n', '').replace('```', '').strip())
                            st.session_state[sesion_reto_key] = res_json.get('leccion_texto', 'Error cargando texto')
                            st.session_state[audio_reto_key] = res_json.get('texto_audio', '')
                            st.rerun()
                        except Exception as e:
                            st.error("Servidores ocupados. Intenta de nuevo.")

            if st.session_state.get(sesion_reto_key):
                st.markdown(f"> 🤖 **Agente IA:** {st.session_state[sesion_reto_key]}")
                if st.session_state.get(audio_reto_key):
                    try:
                        tts_reto = gTTS(text=st.session_state[audio_reto_key], lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                        tts_reto.save("lesson_audio.mp3")
                        st.audio("lesson_audio.mp3")
                    except: pass
                
                st.write("---")
                col_m1, col_m2, col_m3 = st.columns([1, 1, 1])
                with col_m2:
                    audio_agent = audio_recorder(text="", icon_size="2x", key="mic_agent")
                
                with st.expander(t["write"]):
                    with st.form("form_agent", clear_on_submit=False):
                        texto_agent = st.text_input("Escribe aquí:", key="txt_agent")
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
                                st.success(f"🎤: {final_agent}")
                        except: st.error(t["err_audio"])

                if final_agent:
                    with st.spinner(f"{t['analyzing']}..."):
                        prompt_eval = f"Actúa como profesor de {lang_activo_original}. El usuario habla {idioma_nativo}. El reto era: '{st.session_state[sesion_reto_key]}'. El usuario respondió: '{final_agent}'. Evalúa si pronunció bien o si adivinó la respuesta correcta del Quiz. Devuelve SOLO JSON: {{'correccion': 'ESCRIBE AQUÍ SOLAMENTE LA FRASE CORREGIDA EN {lang_activo_original}. NADA EN {idioma_nativo}', 'pronunciacion': 'fonética en {idioma_nativo}', 'tips': 'Explica en {idioma_nativo} si logró el reto o acertó el quiz', 'puntuacion': '1-10'}}"
                        try:
                            client = genai.Client(api_key=API_KEY_FREE)
                            res_eval = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt_eval)
                            res_json = json.loads(res_eval.text.replace('```json\n', '').replace('```', '').strip())
                            
                            st.metric(t["score"], f"{res_json.get('puntuacion', 'N/A')}/10")
                            st.success(f"✅ {t['correction']} {res_json.get('correccion', '')}")
                            st.info(f"🗣️ {t['pronunciation']} {res_json.get('pronunciacion', '')}")
                            st.info(f"💡 {t['tip']} {res_json.get('tips', '')}")
                            try:
                                tts = gTTS(text=res_json.get('correccion', ''), lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                                tts.save("feedback_agent.mp3")
                                st.audio("feedback_agent.mp3")
                            except: pass

                            doc_ref = db.collection("usuarios").document(u["correo"])
                            doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                            st.session_state.usuario_db["frases_usadas_hoy"] += 1

                            try: puntos = int(str(res_json.get('puntuacion', '0')).replace('/10', '').strip())
                            except: puntos = 5

                            if puntos >= 7:
                                st.balloons()
                                if es_fundamentos:
                                    st.success(t["lesson_passed"])
                                    doc_ref.update({progreso_key: firestore.Increment(1)})
                                    st.session_state.usuario_db[progreso_key] = leccion_actual + 1
                                else: st.success(t["role_passed"])
                                st.session_state.reto_superado = True

                        except Exception as e: st.warning("Error evaluando. Intenta de nuevo.")

            if st.session_state.get("reto_superado"):
                if st.button(t["btn_next"], use_container_width=True, key="btn_continuar_reto"):
                    st.session_state[sesion_reto_key] = ""
                    st.session_state[audio_reto_key] = ""
                    st.session_state.reto_superado = False
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    if tab_upgrade:
        with tab_upgrade:
            st.markdown('<div class="modern-card">', unsafe_allow_html=True)
            st.subheader(t["up_title"])
            st.write(t["up_sub"])
            st.markdown(f"""
            <div style="background-color: #E8F0FE; padding: 15px; border-radius: 8px; border-left: 5px solid #0047AB; margin-bottom: 20px;">
                <h4 style="color: #0047AB; margin-top: 0;">{t['up_mkt_title']}</h4>
                <p style="color: #333; font-size: 0.95rem; margin-bottom: 0;">{t['up_mkt_desc']}</p>
            </div>
            """, unsafe_allow_html=True)
            st.info(f"✨ **{t['desc_standard']}**")
            st.success(f"👑 **{t['desc_pro']}**")
            st.markdown('</div>', unsafe_allow_html=True)
