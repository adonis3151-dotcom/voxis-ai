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

# --- 2. CONFIGURACIÓN DE PÁGINA Y DISEÑO CSS ---
icono_pagina = "logo.png" if os.path.exists("logo.png") else "🎙️"
st.set_page_config(page_title="Voxis AI", page_icon=icono_pagina, layout="centered")

# CSS Avanzado para Logo, Micrófono y Menú Fijo Flotante
st.markdown("""
    <style>
    /* Reducir el espacio superior excesivo */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 7rem !important; /* Espacio para el menú fijo */
    }
    [data-testid="stHeader"] {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #F4F5F7; } 
    h1, h2, h3 { color: #0047AB !important; font-family: 'Helvetica Neue', sans-serif; } 
    
    /* Estilo del Logo y Slogan en Dashboard */
    .dashboard-header {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        margin-bottom: 2rem;
    }
    .slogan-text-dashboard { 
        color: #5F6368; 
        font-size: 1.1rem; 
        font-style: italic; 
        margin-top: -10px; 
    }
    
    /* Botones Generales */
    .stButton>button, .stFormSubmitButton>button { background-color: #FF7F50; color: white; border-radius: 8px; border: none; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover, .stFormSubmitButton>button:hover { background-color: #E0693E; color: white; }
    
    /* Centrar las métricas de puntaje */
    div[data-testid="stMetric"] { text-align: center !important; }
    div[data-testid="stMetricValue"] { display: flex; justify-content: center; color: #FF7F50; font-weight: bold; }
    
    div.stAlert { border-radius: 10px; border-left: 5px solid #0047AB; }
    .stTextInput>div>div>input { background-color: #E2E6EA !important; color: #111111 !important; border-radius: 6px; border: 1px solid #CCCCCC; }
    .legal-text { font-size: 0.8rem; color: #6c757d; }
    
    /* Pestañas */
    button[data-baseweb="tab"] { padding: 0.8rem 1.5rem !important; }
    button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p { font-size: 1.1rem !important; font-weight: 600 !important; }
    div[data-baseweb="tab-list"] { gap: 15px; padding-bottom: 5px; }

    /* --- ESTILO DEL MENÚ FIJO FLOTANTE (FOOTER) --- */
    .fixed-footer {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 90%;
        max-width: 500px;
        background-color: white;
        padding: 10px 20px;
        border-radius: 20px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        z-index: 9999;
        display: flex;
        justify-content: space-around;
        align-items: center;
    }
    
    /* Estilos específicos para los widgets dentro del footer */
    .fixed-footer .stSelectbox { margin-bottom: 0px !important; width: 150px; }
    .fixed-footer .stButton button { 
        background-color: transparent !important; 
        color: #5F6368 !important; 
        border: 1px solid #CCCCCC !important;
        font-weight: normal !important;
        padding: 5px 10px !important;
        font-size: 0.8rem !important;
    }
    .fixed-footer .stButton button:hover { background-color: #F4F5F7 !important; }
    
    /* Ajuste para móviles */
    @media (max-width: 600px) {
        .fixed-footer { width: 95%; padding: 5px 10px; }
        .fixed-footer .stSelectbox { width: 120px; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. DICCIONARIO MULTILINGÜE COMPLETO ---
UI_TEXT = {
    "Español": {"native_lang": "🗣️ Tu Idioma", "short_mic_hint": " Haz un solo clic para hablar", "record_btn": "🎙️ Grabar (Max {}s)", "login_sub": "Identifícate para comenzar.", "email": "Correo:", "names": "Nombres:", "lastnames": "Apellidos:", "wa": "WhatsApp:", "plan_select": "Elige tu plan inicial:", "btn_login": "Entrar / Registrarse", "greeting": "Hola", "plan_label": "Plan actual", "trainings": "Entrenamientos", "logout": "Cerrar Sesión", "tab_train": "🏋️ Entrenamiento", "tab_upgrade": "⭐ Mejorar Plan", "tab_agent": "🤖 Ruta de Estudio IA", "up_title": "Desbloquea tu potencial 🚀", "up_sub": "(Pronto: Pagos directos)", "learn_prompt": "🌐 Idioma a entrenar:", "record": "Presiona el micro para hablar en", "write": "O escribe en", "btn_send": "Enviar 🚀", "listening": "Escuchando...", "analyzing": "Analizando...", "score": "Puntaje", "correction": "Corrección:", "pronunciation": "Pronunciación:", "tip": "Tip:", "err_char": "Límite: {} caracteres.", "err_audio": "No pudimos escuchar bien. Intenta hablar más claro o escribe tu respuesta.", "limit_reached": "🔒 Límite diario alcanzado.", "repeat": "Frase ya procesada.", "desc_free": "Plan FREE ($0): 5 frases/día", "desc_standard": "Plan STANDARD ($1): 20 frases/día", "desc_pro": "Plan PRO ($5): 100 frases/día", "welcome_title": "¡Bienvenido, {}!", "welcome_ask": "¿Qué idioma quieres practicar hoy?", "btn_continue": "Continuar 👉", "diag_title": "🎯 ¡Casi listos!", "diag_prompt": "Responde en **{}**: ¿Por qué quieres aprender este idioma?", "diag_analyzing": "Evaluando nivel...", "diag_success": "¡Genial! Tu nivel en {} es: {}", "change_lang": "🔄 Cambiar Idioma", "lang_name": {"Inglés": "Inglés", "Español": "Español", "Francés": "Francés", "Alemán": "Alemán", "Italiano": "Italiano", "Portugués": "Portugués", "Mandarín": "Mandarín", "Japonés": "Japonés", "Coreano": "Coreano", "Ruso": "Ruso"}, "choose_mode": "Elige tu modo de estudio:", "mode_fund": "🧱 Fundamentos", "mode_fund_desc": "Juega, aprende y escucha tus primeras palabras.", "lesson_txt": "Nivel", "btn_gen_lesson": "📚 Iniciar Reto de Hoy", "btn_next": "📚 Siguiente ⏭️", "mode_real": "🎭 Situaciones Reales", "mode_real_desc": "Pierde el miedo hablando en escenarios prácticos de la vida diaria.", "prep_lesson": "Generando reto interactivo...", "lesson_passed": "🎉 ¡Reto superado! Haz clic en 'Siguiente' para avanzar.", "role_passed": "🎉 ¡Excelente trabajo! Haz clic en 'Siguiente' para otro Role-play.", "topics": ["Saludos", "Pronombres", "Verbos básicos", "Números", "Colores", "Comida", "Familia", "Días y Meses", "Ropa", "Cuerpo", "Animales", "Profesiones", "Clima", "Hogar", "Emociones", "Verbos de acción", "Transporte", "Ciudad", "La Hora", "Rutina"], "super_power_title": "⚡ Práctica Libre", "super_power_desc": "Presiona el micrófono, di cualquier frase y la IA corregirá tu pronunciación y gramática como un tutor real al instante.", "tc_check": "Acepto los Términos, Condiciones y Política de Privacidad", "tc_error": "⚠️ Debes aceptar los Términos y Condiciones para continuar.", "tc_title": "📜 Ver Términos y Condiciones", "tc_text": "**Voxis AI - Términos Básicos (Placeholder)**<br>1. Al registrarte aceptas el uso de cookies de sesión para la aplicación.<br>2. Los datos de audio no se comparten; se procesan a través de servidores seguros de Google AI.<br>3. Las cuentas Free están sujetas a límites diarios de cuota.<br>*(El documento legal final se agregará en la versión web pública).*\",", "otp_sent_msg": "📧 Hemos enviado un código a **{}**", "otp_label": "Código de verificación de 4 dígitos:", "btn_verify": "Verificar Código", "btn_cancel": "Cancelar / Volver", "otp_error": "❌ Código incorrecto. Intenta de nuevo.", "email_error": "❌ Error al enviar el correo. Verifica que tu dirección exista.", "email_subject": "Tu código de acceso a Voxis AI", "email_body": "¡Hola!\n\nTu código de acceso seguro para entrar a Voxis AI es: {}\n\nSi no solicitaste esto, puedes ignorar este correo."},
    "Inglés": {"native_lang": "🗣️ Your Language", "short_mic_hint": " Click once to talk", "record_btn": "🎙️ Record (Max {}s)", "login_sub": "Log in to start.", "email": "Email:", "names": "First Name:", "lastnames": "Last Name:", "wa": "WhatsApp:", "plan_select": "Choose starting plan:", "btn_login": "Login / Register", "greeting": "Hello", "plan_label": "Current Plan", "trainings": "Trainings", "logout": "Log Out", "tab_train": "🏋️ Training", "tab_upgrade": "⭐ Upgrade Plan", "tab_agent": "🤖 AI Study Path", "up_title": "Unlock your potential 🚀", "up_sub": "(Soon: Direct payments)", "learn_prompt": "🌐 Language to train:", "record": "Tap mic to speak in", "write": "Or type in", "btn_send": "Send 🚀", "listening": "Listening...", "analyzing": "Analyzing...", "score": "Score", "correction": "Correction:", "pronunciation": "Pronunciation:", "tip": "Tip:", "err_char": "Limit: {} chars.", "err_audio": "Could not hear you well. Please speak louder or type.", "limit_reached": "🔒 Daily limit reached.", "repeat": "Phrase already processed.", "desc_free": "FREE Plan ($0): 5 phrases/day", "desc_standard": "STANDARD Plan ($1): 20 phrases/day", "desc_pro": "PRO Plan ($5): 100 phrases/day", "welcome_title": "Welcome, {}!", "welcome_ask": "What language do you want to practice?", "btn_continue": "Continue 👉", "diag_title": "🎯 Almost ready!", "diag_prompt": "Answer in **{}**: Why do you want to learn this language?", "diag_analyzing": "Evaluating level...", "diag_success": "Great! Your level in {} is: {}", "change_lang": "🔄 Change Language", "lang_name": {"Inglés": "English", "Español": "Spanish", "Francés": "French", "Alemán": "German", "Italiano": "Italian", "Portugués": "Portuguese", "Mandarín": "Mandarin", "Japonés": "Japanese", "Coreano": "Korean", "Ruso": "Russian"}, "choose_mode": "Choose your study mode:", "mode_fund": "🧱 Fundamentals", "mode_fund_desc": "Play, learn and listen to your first words.", "lesson_txt": "Level", "btn_gen_lesson": "📚 Start Today's Challenge", "btn_next": "📚 Next ⏭️", "mode_real": "🎭 Real Scenarios", "mode_real_desc": "Lose the fear by speaking in practical daily scenarios.", "prep_lesson": "Generating interactive challenge...", "lesson_passed": "🎉 Challenge passed! Click 'Next' to advance.", "role_passed": "🎉 Excellent work! Click 'Next' for another Role-play.", "topics": ["Greetings", "Pronouns", "Basic Verbs", "Numbers", "Colors", "Food", "Family", "Days & Months", "Clothes", "Body", "Animals", "Professions", "Weather", "Home", "Emotions", "Action Verbs", "Transportation", "City", "Time", "Routine"], "super_power_title": "⚡ Free Practice", "super_power_desc": "Press the microphone, say any phrase, and the AI will correct your pronunciation and grammar like a real tutor instantly.", "tc_check": "I accept the Terms, Conditions, and Privacy Policy", "tc_error": "⚠️ You must accept the Terms and Conditions to continue.", "tc_title": "📜 View Terms and Conditions", "tc_text": "**Voxis AI - Basic Terms (Placeholder)**<br>1. By registering, you accept the use of session cookies.<br>2. Audio data is not shared; it is processed via secure Google AI servers.<br>3. Free accounts are subject to daily quota limits.<br>*(The final legal document will be added in the public web version).*\",", "otp_sent_msg": "📧 We sent a code to **{}**", "otp_label": "4-digit verification code:", "btn_verify": "Verify Code", "btn_cancel": "Cancel / Go back", "otp_error": "❌ Incorrect code. Try again.", "email_error": "❌ Error sending email. Check the address.", "email_subject": "Your Voxis AI Access Code", "email_body": "Hello!\n\nYour secure access code for Voxis AI is: {}\n\nIf you didn't request this, please ignore this email."},
    "Francés": {"native_lang": "🗣️ Votre langue", "short_mic_hint": " Cliquez une fois pour parler", "record_btn": "🎙️ Enregistrer (Max {}s)", "login_sub": "Connectez-vous.", "email": "E-mail:", "names": "Prénoms:", "lastnames": "Noms:", "wa": "WhatsApp:", "plan_select": "Forfait:", "btn_login": "Connexion / Inscription", "greeting": "Bonjour", "plan_label": "Forfait", "trainings": "Formations", "logout": "Déconnexion", "tab_train": "🏋️ Entraînement", "tab_upgrade": "⭐ Améliorer Forfait", "tab_agent": "🤖 Parcours IA", "up_title": "Libérez votre potentiel 🚀", "up_sub": "(Bientôt: Paiements)", "learn_prompt": "🌐 Langue à former:", "record": "Parlez en", "write": "Ou tapez en", "btn_send": "Envoyer 🚀", "listening": "Écoute...", "analyzing": "Analyse...", "score": "Score", "correction": "Correction:", "pronunciation": "Prononciation:", "tip": "Conseil:", "err_char": "Limite: {} car.", "err_audio": "Nous n'avons pas bien entendu. Parlez plus fort.", "limit_reached": "🔒 Limite atteinte.", "repeat": "Phrase déjà traitée.", "desc_free": "Plan FREE (0$): 5/jour", "desc_standard": "Plan STANDARD (1$): 20/jour", "desc_pro": "Plan PRO (5$): 100/jour", "welcome_title": "Bienvenue, {}!", "welcome_ask": "Quelle langue pratiquer?", "btn_continue": "Continuer 👉", "diag_title": "🎯 Presque prêt!", "diag_prompt": "Répondez en **{}**: Pourquoi apprendre cette langue?", "diag_analyzing": "Évaluation...", "diag_success": "Super! Niveau en {} : {}", "change_lang": "🔄 Changer de Langue", "lang_name": {"Inglés": "Anglais", "Español": "Espagnol", "Francés": "Français", "Alemán": "Allemand", "Italiano": "Italien", "Portugués": "Portugais", "Mandarín": "Mandarin", "Japonés": "Japonais", "Coreano": "Coréen", "Ruso": "Russe"}, "choose_mode": "Choisissez votre mode :", "mode_fund": "🧱 Fondamentaux", "mode_fund_desc": "Jouez, apprenez et écoutez vos premiers mots.", "lesson_txt": "Niveau", "btn_gen_lesson": "📚 Démarrer le défi", "btn_next": "📚 Suivant ⏭️", "mode_real": "🎭 Scénarios Réels", "mode_real_desc": "Perdez la peur en parlant dans des scénarios quotidiens.", "prep_lesson": "Génération du défi interactif...", "lesson_passed": "🎉 Défi réussi! Cliquez sur 'Suivant' pour avancer.", "role_passed": "🎉 Excellent travail! Cliquez sur 'Suivant' pour un autre jeu de rôle.", "topics": ["Salutations", "Pronoms", "Verbos", "Nombres", "Couleurs", "Nourriture", "Famille", "Jours", "Vêtements", "Corps", "Animaux", "Professions", "Météo", "Maison", "Émotions", "Verbes d'action", "Transport", "Ville", "Heure", "Routine"], "super_power_title": "⚡ Pratique Libre", "super_power_desc": "Appuyez sur le microphone, dites n'importe quelle phrase, et l'IA corrigera votre pronunciation et votre grammaire comme un vrai tuteur.", "tc_check": "J'accepte les conditions générales et la politique de confidentialité", "tc_error": "⚠️ Vous devez accepter les conditions pour continuer.", "tc_title": "📜 Voir les conditions générales", "tc_text": "**Voxis AI - Conditions (Espace réservé)**<br>1. Vous acceptez l'utilisation de cookies de session.<br>2. L'audio est traité via des serveurs sécurisés Google AI.<br>3. Les quotas quotidiens s'appliquent.<br>*(Document final au lancement web).*\",", "otp_sent_msg": "📧 Code envoyé à **{}**", "otp_label": "Code de vérification (4 chiffres):", "btn_verify": "Vérifier", "btn_cancel": "Annuler", "otp_error": "❌ Code incorrect.", "email_error": "❌ Erreur d'e-mail.", "email_subject": "Code d'accès Voxis AI", "email_body": "Bonjour,\n\nVotre code d'accès est : {}"},
    "Alemán": {"native_lang": "🗣️ Deine Sprache", "short_mic_hint": " Einmal klicken zum Sprechen", "record_btn": "🎙️ Aufnehmen (Max {}s)", "login_sub": "Melden Sie sich an.", "email": "E-Mail:", "names": "Vorname:", "lastnames": "Nachname:", "wa": "WhatsApp:", "plan_select": "Plan wählen:", "btn_login": "Anmelden / Registrieren", "greeting": "Hallo", "plan_label": "Plan", "trainings": "Trainings", "logout": "Abmelden", "tab_train": "🏋️ Training", "tab_upgrade": "⭐ Upgrade", "tab_agent": "🤖 KI-Lernpfad", "up_title": "Potenzial ausschöpfen 🚀", "up_sub": "(Bald: Zahlungen)", "learn_prompt": "🌐 Sprache:", "record": "Sprechen in", "write": "Oder tippen in", "btn_send": "Senden 🚀", "listening": "Zuhören...", "analyzing": "Analysieren...", "score": "Punktzahl", "correction": "Korrektur:", "pronunciation": "Aussprache:", "tip": "Tipp:", "err_char": "Limit: {} Zeichen.", "err_audio": "Wir konnten Sie nicht hören.", "limit_reached": "🔒 Tageslimit erreicht.", "repeat": "Satz verarbeitet.", "desc_free": "FREE-Plan (0$): 5/Tag", "desc_standard": "STANDARD-Plan (1$): 20/Tag", "desc_pro": "PRO-Plan (5$): 100/Tag", "welcome_title": "Willkommen, {}!", "welcome_ask": "Welche Sprache üben?", "btn_continue": "Weiter 👉", "diag_title": "🎯 Fast fertig!", "diag_prompt": "Antworte auf **{}**: Warum diese Sprache lernen?", "diag_analyzing": "Bewertung...", "diag_success": "Großartig! Niveau in {} : {}", "change_lang": "🔄 Sprache ändern", "lang_name": {"Inglés": "Englisch", "Español": "Spanisch", "Francés": "Französisch", "Alemán": "Deutsch", "Italiano": "Italienisch", "Portugués": "Portugiesisch", "Mandarín": "Mandarin", "Japonés": "Japanisch", "Coreano": "Koreanisch", "Ruso": "Russisch"}, "choose_mode": "Lernmodus wählen:", "mode_fund": "🧱 Grundlagen", "mode_fund_desc": "Spielen, lernen und hören Sie Ihre ersten Wörter.", "lesson_txt": "Level", "btn_gen_lesson": "📚 Herausforderung starten", "btn_next": "📚 Nächste ⏭️", "mode_real": "🎭 Echte Szenarien", "mode_real_desc": "Sprechen Sie ohne Angst in täglichen Szenarien.", "prep_lesson": "Interaktive Herausforderung wird erstellt...", "lesson_passed": "🎉 Bestanden! Klick 'Nächste', um fortzufahren.", "role_passed": "🎉 Hervorragende Arbeit! Klick 'Nächste'.", "topics": ["Begrüßungen", "Pronomen", "Verben", "Zahlen", "Farben", "Essen", "Familie", "Tage", "Kleidung", "Körper", "Tiere", "Berufe", "Wetter", "Zuhause", "Emotionen", "Aktionsverben", "Transport", "Stadt", "Zeit", "Routine"], "super_power_title": "⚡ Freies Üben", "super_power_desc": "Drücke auf das Mikrofon, sage einen beliebigen Satz und die KI korrigiert deine Aussprache.", "tc_check": "Ich akzeptiere die Allgemeinen Geschäftsbedingungen", "tc_error": "⚠️ Sie müssen die Bedingungen akzeptieren, um fortzufahren.", "tc_title": "📜 AGB anzeigen", "tc_text": "**Voxis AI - Bedingungen (Platzhalter)**<br>1. Mit der Registrierung akzeptieren Sie Sitzungscookies.<br>2. Audio wird über Google AI verarbeitet.<br>3. Quoten können variieren.<br>*(Endgültiges Dokument beim Web-Start).*\",", "otp_sent_msg": "📧 Code gesendet an **{}**", "otp_label": "Bestätigungscode (4 Ziffern):", "btn_verify": "Überprüfen", "btn_cancel": "Abbrechen", "otp_error": "❌ Falscher Code.", "email_error": "❌ E-Mail-Fehler.", "email_subject": "Voxis AI Zugangscode", "email_body": "Hallo!\n\nDein Zugangscode ist: {}"},
    "Italiano": {"native_lang": "🗣️ La tua lingua", "short_mic_hint": " Clicca una volta per parlare", "record_btn": "🎙️ Registra (Max {}s)", "login_sub": "Accedi per iniziare.", "email": "Email:", "names": "Nome:", "lastnames": "Cognome:", "wa": "WhatsApp:", "plan_select": "Scegli piano:", "btn_login": "Accedi / Registrati", "greeting": "Ciao", "plan_label": "Piano", "trainings": "Allenamenti", "logout": "Esci", "tab_train": "🏋️ Allenamento", "tab_upgrade": "⭐ Migliora", "tab_agent": "🤖 Percorso IA", "up_title": "Sblocca potenziale 🚀", "up_sub": "(Presto: Pagamenti)", "learn_prompt": "🌐 Lingua:", "record": "Parla in", "write": "O scrivi in", "btn_send": "Invia 🚀", "listening": "Ascoltando...", "analyzing": "Analizzando...", "score": "Punteggio", "correction": "Correzione:", "pronunciation": "Pronuncia:", "tip": "Suggerimento:", "err_char": "Limite: {} car.", "err_audio": "Non ti abbiamo sentito bene. Parla più forte.", "limit_reached": "🔒 Limite raggiunto.", "repeat": "Già elaborata.", "desc_free": "Piano FREE ($0): 5/giorno", "desc_standard": "Piano STANDARD ($1): 20/giorno", "desc_pro": "Piano PRO ($5): 100/giorno", "welcome_title": "Benvenuto, {}!", "welcome_ask": "Che lingua vuoi praticare?", "btn_continue": "Continua 👉", "diag_title": "🎯 Quasi pronti!", "diag_prompt": "Rispondi in **{}**: Perché vuoi imparare?", "diag_analyzing": "Valutazione...", "diag_success": "Ottimo! Livello in {} : {}", "change_lang": "🔄 Cambia Lingua", "lang_name": {"Inglés": "Inglese", "Español": "Spagnolo", "Francés": "Francese", "Alemán": "Tedesco", "Italiano": "Italiano", "Portugués": "Portoghese", "Mandarín": "Mandarino", "Japonés": "Giapponese", "Coreano": "Coreano", "Ruso": "Russo"}, "choose_mode": "Scegli la modalità:", "mode_fund": "🧱 Fondamenti", "mode_fund_desc": "Gioca, impara e ascolta le tue prime parole.", "lesson_txt": "Livello", "btn_gen_lesson": "📚 Inizia Sfida", "btn_next": "📚 Avanti ⏭️", "mode_real": "🎭 Scenari Reali", "mode_real_desc": "Parla senza paura in scenari quotidiani.", "prep_lesson": "Generazione sfida interattiva...", "lesson_passed": "🎉 Superato! Clicca 'Avanti' per il prossimo livello.", "role_passed": "🎉 Ottimo lavoro! Clicca 'Avanti'.", "topics": ["Saluti", "Pronomi", "Verbi", "Numeri", "Colori", "Cibo", "Famiglia", "Giorni", "Vestiti", "Corpo", "Animali", "Professioni", "Meteo", "Casa", "Emozioni", "Verbi di azione", "Trasporto", "Città", "Ora", "Routine"], "super_power_title": "⚡ Pratica Libera", "super_power_desc": "Premi il microfono, di' qualsiasi frase e l'IA correggerà la tua pronuncia all'istante.", "tc_check": "Accetto i Termini, le Condizioni e la Privacy Policy", "tc_error": "⚠️ Devi accettare i Termini e le Condizioni.", "tc_title": "📜 Visualizza Termini e Condizioni", "tc_text": "**Voxis AI - Termini (Segnaposto)**<br>1. Registrandoti accetti i cookie di sessione.<br>2. L'audio è elaborato tramite server sicuri Google AI.<br>3. Le quote giornaliere si applicano.<br>*(Il documento finale sarà aggiunto al lancio web).*\",", "otp_sent_msg": "📧 Codice inviato a **{}**", "otp_label": "Codice di verifica:", "btn_verify": "Verifica", "btn_cancel": "Annulla", "otp_error": "❌ Codice errato.", "email_error": "❌ Errore email.", "email_subject": "Codice di accesso Voxis AI", "email_body": "Ciao!\n\nIl tuo codice è: {}"},
    "Portugués": {"native_lang": "🗣️ Seu Idioma", "short_mic_hint": " Clique uma vez para falar", "record_btn": "🎙️ Gravar (Max {}s)", "login_sub": "Faça login.", "email": "E-mail:", "names": "Nome:", "lastnames": "Sobrenome:", "wa": "WhatsApp:", "plan_select": "Escolha o plano:", "btn_login": "Entrar / Registrar", "greeting": "Olá", "plan_label": "Plano", "trainings": "Treinos", "logout": "Sair", "tab_train": "🏋️ Treino", "tab_upgrade": "⭐ Melhorar Plano", "tab_agent": "🤖 Trilha IA", "up_title": "Desbloqueie potencial 🚀", "up_sub": "(Em breve: Pagamentos)", "learn_prompt": "🌐 Idioma:", "record": "Fale em", "write": "Ou digite em", "btn_send": "Enviar 🚀", "listening": "Ouvindo...", "analyzing": "Analisando...", "score": "Pontuação", "correction": "Correção:", "pronunciation": "Pronúncia:", "tip": "Dica:", "err_char": "Limite: {} car.", "err_audio": "Não conseguimos ouvir bem. Fale mais alto.", "limit_reached": "🔒 Limite atingido.", "repeat": "Frase processada.", "desc_free": "Plano FREE ($0): 5/dia", "desc_standard": "Plano STANDARD ($1): 20/dia", "desc_pro": "Plano PRO ($5): 100/dia", "welcome_title": "Bem-vindo, {}!", "welcome_ask": "Qual idioma praticar?", "btn_continue": "Continuar 👉", "diag_title": "🎯 Quase pronto!", "diag_prompt": "Responda em **{}**: Por que aprender este idioma?", "diag_analyzing": "Avaliando...", "diag_success": "Ótimo! Nível em {} : {}", "change_lang": "🔄 Mudar Idioma", "lang_name": {"Inglés": "Inglês", "Español": "Espanhol", "Francés": "Francês", "Alemán": "Alemão", "Italiano": "Italiano", "Portugués": "Português", "Mandarín": "Mandarim", "Japonés": "Japonês", "Coreano": "Coreano", "Ruso": "Rússia"}, "choose_mode": "Escolha seu modo:", "mode_fund": "🧱 Fundamentos", "mode_fund_desc": "Jogue, aprenda e ouça suas primeiras palavras.", "lesson_txt": "Nível", "btn_gen_lesson": "📚 Iniciar Desafio", "btn_next": "📚 Próximo ⏭️", "mode_real": "🎭 Cenários Reais", "mode_real_desc": "Perca o medo falando em cenários diários.", "prep_lesson": "Gerando desafio interativo...", "lesson_passed": "🎉 Sucesso! Clique em 'Próximo' para avançar.", "role_passed": "🎉 Excelente! Clique em 'Próximo' para outro cenário.", "topics": ["Saudações", "Pronomes", "Verbos", "Números", "Cores", "Comida", "Família", "Dias", "Roupas", "Corpo", "Animais", "Profissões", "Clima", "Casa", "Emoções", "Ação", "Transporte", "Cidade", "Hora", "Rotina"], "super_power_title": "⚡ Prática Livre", "super_power_desc": "Pressione o microfone, diga qualquer frase e a IA corrigirá sua pronúncia e gramática instantaneamente.", "tc_check": "Aceito os Termos, Condições e Política de Privacidade", "tc_error": "⚠️ Você deve aceitar os Termos e Condições.", "tc_title": "📜 Ver Termos e Condições", "tc_text": "**Voxis AI - Termos (Espaço reservado)**<br>1. Ao registrar-se você aceita os cookies de sessão.<br>2. O áudio é processado via servidores seguros do Google AI.<br>3. Contas gratuitas têm cotas diárias.<br>*(O documento legal final será adicionado no lançamento da web).*\",", "otp_sent_msg": "📧 Enviamos um código para **{}**", "otp_label": "Código de verificação:", "btn_verify": "Verificar", "btn_cancel": "Cancelar", "otp_error": "❌ Código incorreto.", "email_error": "❌ Erro ao enviar e-mail.", "email_subject": "Código de acesso Voxis AI", "email_body": "Olá!\n\nSeu código é: {}"},
    "Mandarín": {"native_lang": "🗣️ 你的语言", "short_mic_hint": " 单击一次即可说话", "record_btn": "🎙️ 录音 (最多{}秒)", "login_sub": "登录以开始。", "email": "电子邮件:", "names": "名:", "lastnames": "姓:", "wa": "WhatsApp:", "plan_select": "选择计划:", "btn_login": "登录 / 注册", "greeting": "你好", "plan_label": "计划", "trainings": "训练", "logout": "登出", "tab_train": "🏋️ 训练", "tab_upgrade": "⭐ 升级", "tab_agent": "🤖 AI 路径", "up_title": "释放潜力 🚀", "up_sub": "(即将推出)", "learn_prompt": "🌐 语言:", "record": "用此语言说话:", "write": "或输入:", "btn_send": "发送 🚀", "listening": "倾听中...", "analyzing": "分析中...", "score": "分数", "correction": "纠正:", "pronunciation": "发音:", "tip": "提示:", "err_char": "限制: {} 字符。", "err_audio": "听不清楚，请大声说话或输入。", "limit_reached": "🔒 达到限额。", "repeat": "已处理。", "desc_free": "FREE 计划 ($0): 5句/天", "desc_standard": "STANDARD 计划 ($1): 20句/天", "desc_pro": "PRO 计划 ($5): 100句/天", "welcome_title": "欢迎, {}!", "welcome_ask": "想练习什么语言？", "btn_continue": "继续 👉", "diag_title": "🎯 差不多了！", "diag_prompt": "请用 **{}** 回答：为什么想学？", "diag_analyzing": "评估中...", "diag_success": "太棒了！{} 级别: {}", "change_lang": "🔄 更改语言", "lang_name": {"Inglés": "英语", "Español": "西班牙语", "Francés": "法语", "Alemán": "德语", "Italiano": "意大利语", "Portugués": "葡萄牙语", "Mandarín": "中文", "Japonés": "日语", "Coreano": "韩语", "Ruso": "俄语"}, "choose_mode": "选择模式:", "mode_fund": "🧱 基础知识", "mode_fund_desc": "边玩边学，聆听你的第一批单词。", "lesson_txt": "水平", "btn_gen_lesson": "📚 开始今日挑战", "btn_next": "📚 下一步 ⏭️", "mode_real": "🎭 真实场景", "mode_real_desc": "在日常实用场景中开口说，消除恐惧。", "prep_lesson": "正在生成互动挑战...", "lesson_passed": "🎉 挑战成功！点击'下一步'继续。", "role_passed": "🎉 干得好！点击'下一步'进行另一个角色扮演。", "topics": ["问候", "代词", "动词", "数字", "颜色", "食物", "家庭", "日期", "衣服", "身体", "动物", "职业", "天气", "家庭用品", "情绪", "动作", "交通", "城市", "时间", "日常"], "super_power_title": "⚡ 自由练习", "super_power_desc": "按下麦克风，说出任何短语，AI 将像真正的导师一样立即纠正您的发音和语法。", "tc_check": "我接受条款，条件和隐私政策", "tc_error": "⚠️ 您必须接受条款和条件才能继续。", "tc_title": "📜 查看条款和条件", "tc_text": "**Voxis AI - 条款 (占位符)**<br>1. 注册即表示您接受会话 cookie。<br>2. 音频数据不会共享；它通过安全的 Google AI 处理。<br>3. 每日有额度限制。<br>*(最终法律文件将在公开发布时添加)。*\",", "otp_sent_msg": "📧 代码已发送至 **{}**", "otp_label": "验证码:", "btn_verify": "验证", "btn_cancel": "取消", "otp_error": "❌ 代码错误。", "email_error": "❌ 邮件发送失败。", "email_subject": "Voxis AI 访问代码", "email_body": "您的代码是: {}"},
    "Japonés": {"native_lang": "🗣️ あなたの言語", "short_mic_hint": " 一度クリックして話す", "record_btn": "🎙️ 録音 (最大{}秒)", "login_sub": "ログインして開始。", "email": "Eメール:", "names": "名:", "lastnames": "姓:", "wa": "WhatsApp:", "plan_select": "プラン:", "btn_login": "ログイン / 登録", "greeting": "こんにちは", "plan_label": "プラン", "trainings": "トレーニング", "logout": "ログアウト", "tab_train": "🏋️ 練習", "tab_upgrade": "⭐ アップグレード", "tab_agent": "🤖 AI パス", "up_title": "可能性を解き放つ 🚀", "up_sub": "(まもなく)", "learn_prompt": "🌐 言語:", "record": "話す:", "write": "または入力:", "btn_send": "送信 🚀", "listening": "聞いています...", "analyzing": "分析中...", "score": "スコア", "correction": "訂正:", "pronunciation": "発音:", "tip": "ヒント:", "err_char": "制限: {} 文字。", "err_audio": "よく聞こえませんでした。", "limit_reached": "🔒 制限到達。", "repeat": "処理済み。", "desc_free": "FREE ($0): 5回/日", "desc_standard": "STANDARD ($1): 20回/日", "desc_pro": "PRO ($5): 100回/日", "welcome_title": "ようこそ, {}!", "welcome_ask": "どの言語を練習しますか？", "btn_continue": "続ける 👉", "diag_title": "🎯 ほぼ完了！", "diag_prompt": "**{}** で回答: なぜ学びたいですか？", "diag_analyzing": "評価中...", "diag_success": "素晴らしい！ {} レベル: {}", "change_lang": "🔄 言語を変更", "lang_name": {"Inglés": "英語", "Español": "スペイン語", "Francés": "フランス語", "Alemán": "ドイツ語", "Italiano": "イタリア語", "Portugués": "ポルトガル語", "Mandarín": "中国語", "Japonés": "日本語", "Coreano": "韓国語", "Ruso": "ロシア語"}, "choose_mode": "モードを選択:", "mode_fund": "🧱 基礎", "mode_fund_desc": "遊びながら最初の単語を学び、聞く。", "lesson_txt": "レベル", "btn_gen_lesson": "📚 チャレンジを開始", "btn_next": "📚 次へ ⏭️", "mode_real": "🎭 リアルシナリオ", "mode_real_desc": "日常のシナリオで話して恐怖をなくす。", "prep_lesson": "インタラクティブなチャレンジを生成中...", "lesson_passed": "🎉 クリア！'次へ'をクリック。", "role_passed": "🎉 素晴らしい！'次へ'をクリック。", "topics": ["挨拶", "代名詞", "動詞", "数字", "色", "食べ物", "家族", "日付", "服", "体", "動物", "職業", "天気", "家", "感情", "動作", "交通", "都市", "時間", "日常"], "super_power_title": "⚡ フリートレーニング", "super_power_desc": "マイクを押して任意のフレーズを言うと、AIが発音を修正します。", "tc_check": "利用規約とプライバシーポリシーに同意します", "tc_error": "⚠️ 続行するには利用規約に同意する必要があります。", "tc_title": "📜 利用規約を表示", "tc_text": "**Voxis AI - 利用規約 (プレースホルダー)**<br>1. 登録により、セッションCookieの使用に同意したことになります。<br>2. 音声データはGoogle AIサーバーを介して安全に処理されます。<br>3. 割り当て制限が適用されます。<br>*(最終的なドキュメントはWeb公開時に追加されます)。*\",", "otp_sent_msg": "📧 **{}** にコードを送信しました", "otp_label": "認証コード:", "btn_verify": "確認", "btn_cancel": "キャンセル", "otp_error": "❌ コードが間違っています.", "email_error": "❌ メールエラー.", "email_subject": "Voxis AI アクセスコード", "email_body": "あなたのコードは: {}"},
    "Coreano": {"native_lang": "🗣️ 귀하의 언어", "short_mic_hint": " 말하려면 한 번 클릭하세요.", "record_btn": "🎙️ 녹음 (최대 {}초)", "login_sub": "로그인하세요.", "email": "이메일:", "names": "이름:", "lastnames": "성:", "wa": "WhatsApp:", "plan_select": "플랜:", "btn_login": "로그인 / 가입", "greeting": "안녕하세요", "plan_label": "플랜", "trainings": "훈련", "logout": "로그아웃", "tab_train": "🏋️ 훈련", "tab_upgrade": "⭐ 업그레이드", "tab_agent": "🤖 AI 경로", "up_title": "잠재력 발휘 🚀", "up_sub": "(곧 제공)", "learn_prompt": "🌐 언어:", "record": "말하기:", "write": "또는 입력:", "btn_send": "보내기 🚀", "listening": "듣는 중...", "analyzing": "분석 중...", "score": "점수", "correction": "교정:", "pronunciation": "발음:", "tip": "팁:", "err_char": "제한: {} 자.", "err_audio": "잘 들리지 않습니다.", "limit_reached": "🔒 한도 초과.", "repeat": "처리됨.", "desc_free": "FREE 플랜 ($0): 5번/일", "desc_standard": "STANDARD 플랜 ($1): 20번/일", "desc_pro": "PRO 플랜 ($5): 100번/일", "welcome_title": "환영합니다, {}!", "welcome_ask": "어떤 언어를 연습할까요?", "btn_continue": "계속 👉", "diag_title": "🎯 거의 완료!", "diag_prompt": "**{}**로 대답: 왜 배우고 싶나요?", "diag_analyzing": "평가 중...", "diag_success": "멋져요! {} 레벨: {}", "change_lang": "🔄 언어 변경", "lang_name": {"Inglés": "영어", "Español": "스페인어", "Francés": "프랑스어", "Alemán": "독일어", "Italiano": "이탈리아어", "Portugués": "포르투갈어", "Mandarín": "중국어", "Japonés": "일본어", "Coreano": "한국어", "Ruso": "러시아어"}, "choose_mode": "모 모드 선택:", "mode_fund": "🧱 기초", "mode_fund_desc": "첫 단어를 놀면서 배우고 들어보세요.", "lesson_txt": "레벨", "btn_gen_lesson": "📚 오늘의 도전 시작", "btn_next": "📚 다음 ⏭️", "mode_real": "🎭 실제 상황", "mode_real_desc": "실제 상황에서 말하기의 두려움을 없애세요.", "prep_lesson": "대화형 도전 생성 중...", "lesson_passed": "🎉 통과! '다음'을 클릭하여 진행하세요.", "role_passed": "🎉 훌륭합니다! '다음'을 클릭하세요.", "topics": ["인사말", "대명사", "동사", "숫자", "색상", "음식", "가족", "날짜", "옷", "신체", "동물", "직업", "날씨", "집", "감정", "동작", "교통", "도시", "시간", "일상"], "super_power_title": "⚡ 자유 연습", "super_power_desc": "마이크를 누르고 아무 문장이나 말하면 AI가 발음과 문법을 즉시 교정해 줍니다.", "tc_check": "이용 약관 및 개인 정보 보호 정책에 동의합니다", "tc_error": "⚠️ 계속하려면 이용 약관에 동의해야 합니다.", "tc_title": "📜 이용 약관 보기", "tc_text": "**Voxis AI - 약관 (자리 표시자)**<br>1. 등록하면 세션 쿠키 사용에 동의하게 됩니다.<br>2. 오디오 데이터는 Google AI 서버를 통해 안전하게 처리됩니다.<br>3. 할당량 제한이 적용됩니다.<br>*(최종 문서는 웹 출시에 추가됩니다).*\",", "otp_sent_msg": "📧 **{}** 로 코드를 보냈습니다", "otp_label": "인증 코드:", "btn_verify": "확인", "btn_cancel": "취소", "otp_error": "❌ 잘못된 코드입니다.", "email_error": "❌ 이메일 오류.", "email_subject": "Voxis AI 액세스 코드", "email_body": "코드는 다음과 같습니다: {}"},
    "Ruso": {"native_lang": "🗣️ Ваш язык", "short_mic_hint": " Нажмите один раз, чтобы говорить", "record_btn": "🎙️ Запись (Макс. {}с)", "login_sub": "Войдите.", "email": "Почта:", "names": "Имя:", "lastnames": "Фамилия:", "wa": "WhatsApp:", "plan_select": "План:", "btn_login": "Вход / Регистрация", "greeting": "Привет", "plan_label": "План", "trainings": "Тренировки", "logout": "Выйти", "tab_train": "🏋️ Тренировка", "tab_upgrade": "⭐ Улучшить", "tab_agent": "🤖 Путь ИИ", "up_title": "Раскройте потенциал 🚀", "up_sub": "(Скоро)", "learn_prompt": "🌐 Язык:", "record": "Говорить на", "write": "Или введите", "btn_send": "Отправить 🚀", "listening": "Слушаю...", "analyzing": "Анализ...", "score": "Оценка", "correction": "Исправление:", "pronunciation": "Произношение:", "tip": "Совет:", "err_char": "Лимит: {} симв.", "err_audio": "Вас плохо слышно.", "limit_reached": "🔒 Лимит достигнут.", "repeat": "Обработано.", "desc_free": "FREE ($0): 5 фраз/день", "desc_standard": "STANDARD ($1): 20 фраз/день", "desc_pro": "PRO ($5): 100 фраз/день", "welcome_title": "Добро пожаловать, {}!", "welcome_ask": "Какой язык практикуем?", "btn_continue": "Продолжить 👉", "diag_title": "🎯 Почти готово!", "diag_prompt": "Ответьте на **{}**: Почему вы хотите учить?", "diag_analyzing": "Оценка...", "diag_success": "Отлично! Уровень в {} : {}", "change_lang": "🔄 Сменить язык", "lang_name": {"Inglés": "Английский", "Español": "Испанский", "Francés": "Французский", "Alemán": "Немецкий", "Italiano": "Итальянский", "Portugués": "Португальский", "Mandarín": "Китайский", "Japonés": "Японский", "Coreano": "Корейский", "Ruso": "Русский"}, "choose_mode": "Выберите режим:", "mode_fund": "🧱 Основы", "mode_fund_desc": "Играйте, учите и слушайте свои первые слова.", "lesson_txt": "Уровень", "btn_gen_lesson": "📚 Начать испытание", "btn_next": "📚 Далее ⏭️", "mode_real": "🎭 Реальные сценарии", "mode_real_desc": "Говорите без страха в повседневных сценариях.", "prep_lesson": "Генерация интерактивного испытания...", "lesson_passed": "🎉 Пройдено! Нажмите 'Далее' для продолжения.", "role_passed": "🎉 Отличная работа! Нажмите 'Далее'.", "topics": ["Приветствия", "Местоимения", "Глаголы", "Числа", "Цвета", "Еда", "Семья", "Дни", "Одежда", "Тело", "Животные", "Профессии", "Погода", "Дом", "Эмоции", "Действия", "Транспорт", "Город", "Время", "Рутина"], "super_power_title": "⚡ Свободная практика", "super_power_desc": "Нажмите на микрофон, скажите любую фразу, и ИИ мгновенно исправит ваше произношение.", "tc_check": "Я принимаю Условия и Политику конфиденциальности", "tc_error": "⚠️ Вы должны принять условия, чтобы продолжить.", "tc_title": "📜 Посмотреть Условия", "tc_text": "**Voxis AI - Условия (Заполнитель)**<br>1. Регистрируясь, вы принимаете файлы cookie сеанса.<br>2. Аудио обрабатывается через серверы Google AI.<br>3. Квоты могут меняться.<br>*(Финальный документ при запуске веб-версии).*\",", "otp_sent_msg": "📧 Код отправлен на **{}**", "otp_label": "Код подтверждения:", "btn_verify": "Подтвердить", "btn_cancel": "Отмена", "otp_error": "❌ Неверный код.", "email_error": "❌ Ошибка отправки.", "email_subject": "Код доступа Voxis AI", "email_body": "Ваш код: {}"}
}

IDIOMAS_APRENDER = {
    "Inglés": {"stt": "en-US", "tts": "en"}, "Español": {"stt": "es-ES", "tts": "es"}, "Francés": {"stt": "fr-FR", "tts": "fr"},
    "Alemán": {"stt": "de-DE", "tts": "de"}, "Italiano": {"stt": "it-IT", "tts": "it"}, "Portugués": {"stt": "pt-BR", "tts": "pt"},
    "Mandarín": {"stt": "zh-CN", "tts": "zh-CN"}, "Japonés": {"stt": "ja-JP", "tts": "ja"}, "Coreano": {"stt": "ko-KR", "tts": "ko"},
    "Ruso": {"stt": "ru-RU", "tts": "ru"}
}

# --- 4. GESTIÓN DE ESTADO INICIAL ---

if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "Español"

idioma_nativo = st.session_state.ui_lang
t = UI_TEXT[idioma_nativo]

# Inicialización de llaves de estado
for key in ["ultima_frase", "ultimo_audio", "audio_diagnostico", "usuario_db", "idioma_activo", "otp_sent", "otp_code", "temp_data", "processing_audio"]:
    if key not in st.session_state:
        st.session_state[key] = None if "audio" in key or key == "usuario_db" or key == "idioma_activo" else ("" if "ultima" in key or key=="otp_code" else (False if "sent" in key or "processing" in key else {}))

# Lógica de cambio de idioma nativo (migrada de UI principal a sesión)
if "last_native_lang" not in st.session_state:
    st.session_state.last_native_lang = idioma_nativo
elif st.session_state.last_native_lang != idioma_nativo:
    # Limpiar caché de retos al cambiar idioma nativo
    for key in list(st.session_state.keys()):
        if key.startswith("reto_") or key.startswith("audio_reto_"):
            st.session_state[key] = ""
    st.session_state.last_native_lang = idioma_nativo

# Recuperación de sesión por URL
if st.session_state.usuario_db is None and "user_session" in st.query_params:
    correo_recuperado = st.query_params["user_session"]
    doc_recuperado = db.collection("usuarios").document(correo_recuperado).get()
    if doc_recuperado.exists:
        st.session_state.usuario_db = doc_recuperado.to_dict()

if st.session_state.idioma_activo is None and "lang_session" in st.query_params:
    st.session_state.idioma_activo = st.query_params["lang_session"]

# --- FUNCIÓN DE ENVÍO DE CORREOS ---
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
    
    hoy = date.today().strftime("%Y-%m-%d")
    if doc.exists:
        datos = doc.to_dict()
        # Actualizar plan si cambió en el login
        if datos.get("plan") != plan_db:
            datos["plan"] = plan_db
            doc_ref.update({"plan": plan_db})
            
        # Reiniciar contador diario si es un nuevo día
        if datos.get("ultima_fecha_uso") != hoy:
            datos["frases_usadas_hoy"] = 0
            datos["ultima_fecha_uso"] = hoy
            doc_ref.set(datos, merge=True)
        # Asegurar estructura de niveles
        if "niveles" not in datos:
            datos["niveles"] = {}
            doc_ref.update({"niveles": {}})
        
        st.query_params["user_session"] = correo 
        return datos, "Welcome back!"
    else:
        # Crear nuevo usuario
        nuevo = {
            "correo": correo, "nombres": nombres, "apellidos": apellidos, "whatsapp": whatsapp, 
            "plan": plan_db, "frases_usadas_hoy": 0, "ultima_fecha_uso": hoy,
            "niveles": {} 
        }
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
            if "429" in str(e): # Rate limit
                time.sleep(1)
            continue
    return {"error": "Servidores ocupados temporalmente. Intenta de nuevo."}

def evaluar_nivel(texto_diagnostico, idioma_aprender, idioma_nativo):
    prompt = f"El usuario intenta aprender {idioma_aprender} y su idioma nativo es {idioma_nativo}. Analiza este texto: '{texto_diagnostico}'. REGLA ESTRICTA: Si el texto está escrito en {idioma_nativo} en lugar de {idioma_aprender}, responde 'A1'. Si está escrito en {idioma_aprender}, determina su nivel CEFR (A1, A2, B1, B2, C1, C2). Responde ÚNICAMENTE con el nivel."
    try:
        client = genai.Client(api_key=API_KEY_FREE)
        response = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt)
        return response.text.strip()[:2] 
    except: return "A1" 

# --- PANTALLA 1: LOGIN Y VERIFICACIÓN OTP ---
if st.session_state.usuario_db is None:
    # Logo más grande y Eslogan en Login
    if os.path.exists("logo.png"):
        col_logo_login, col_empty_login = st.columns([1, 1])
        with col_logo_login:
            st.image("logo.png", width=200) # Aumentado
    else:
        st.title("Voxis AI")
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
                if not aceptar_tc:
                    st.error(t["tc_error"])
                elif correo_in and nombres:
                    # Bypass OTP para Admin
                    admin_vault = str(st.secrets.get("ADMIN_EMAIL", "")).strip().lower()

                    if correo_in == admin_vault and admin_vault != "":
                        datos, msg = iniciar_sesion(correo_in, nombres, apellidos, whatsapp, plan_elegido)
                        st.session_state.usuario_db = datos
                        st.rerun()
                    else:
                        # Usuario normal: Enviar PIN
                        codigo_gen = str(random.randint(1000, 9999))
                        if enviar_otp(correo_in, codigo_gen, t):
                            st.session_state.otp_sent = True
                            st.session_state.otp_code = codigo_gen
                            st.session_state.temp_data = {
                                "correo": correo_in, "nombres": nombres,
                                "apellidos": apellidos, "whatsapp": whatsapp, "plan": plan_elegido
                            }
                            st.rerun()
                        else:
                            st.error(t["email_error"])
                else:
                    st.error("⚠️ Completa los campos requeridos.")

        with st.expander(t["tc_title"]):
            st.markdown(f'<div class="legal-text">{t["tc_text"]}</div>', unsafe_allow_html=True)

    else:
        # Pantalla de ingreso de PIN
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
                    st.session_state.otp_code = ""
                    st.rerun()
                else:
                    st.error(t["otp_error"])

        if st.button(t["btn_cancel"], use_container_width=True):
            st.session_state.otp_sent = False
            st.session_state.otp_code = ""
            st.rerun()

# --- PANTALLA 2 & 3: BIENVENIDA Y DIAGNÓSTICO (Niveles) ---
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

# Pantalla de Diagnóstico (Si no tiene nivel en el idioma elegido)
elif st.session_state.idioma_activo not in st.session_state.usuario_db.get("niveles", {}):
    u = st.session_state.usuario_db
    lang_objetivo_original = st.session_state.idioma_activo
    lang_objetivo_traducido = t["lang_name"].get(lang_objetivo_original, lang_objetivo_original)
    
    st.title(t["diag_title"])
    st.info(t["diag_prompt"].format(lang_objetivo_traducido))
    
    # Micrófono centrado para Diagnóstico
    col_mic1, col_mic2, col_mic3 = st.columns([1, 1, 1])
    with col_mic2:
        audio_diag = audio_recorder(text=t["short_mic_hint"], icon_size="3x", key="diag_mic")
        
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
    
    # Definición de límites por plan
    p = u.get("plan", "Free")
    lim_f = 5 if p=="Free" else (20 if p=="Standard" else 100)
    lim_s = 5 if p=="Free" else 10 # Segundos grabación
    lim_c = 200 if p=="Free" else 400 # Caracteres escritura

    lang_activo_original = st.session_state.idioma_activo
    lang_activo_traducido = t["lang_name"].get(lang_activo_original, lang_activo_original)
    nivel_activo = u.get("niveles", {}).get(lang_activo_original, "A1")
    
    # --- CABECERA DEL DASHBOARD (Logo grande y Slogan centrado) ---
    st.markdown('<div class="dashboard-header">', unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        st.image("logo.png", width=200) # MUCHO MÁS GRANDE
    st.markdown(f'<h3>{t["greeting"]}, {u["nombres"]}</h3>', unsafe_allow_html=True)
    st.markdown('<p class="slogan-text-dashboard">Your 24/7 AI Language Trainer</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Info de plan y nivel
    st.caption(f"{t['plan_label']}: **{p}** | {lang_activo_traducido}: **{nivel_activo}**")
    
    # --- PESTAÑAS DE TRABAJO ---
    # Removidos botones grandes de Logout y Change Lang de aquí
    tabs_list = [t["tab_train"], t["tab_agent"]] if "Pro" in p else [t["tab_train"], t["tab_agent"], t["tab_upgrade"]]
    tabs = st.tabs(tabs_list)
    
    tab_train, tab_agent = tabs[0], tabs[1]
    tab_upgrade = tabs[2] if "Pro" not in p else None

    # --- LÓGICA DE GRABACIÓN DE AUDIO (FIX 1-CLIC) ---
    def manejar_grabacion(key_mic, language_stt, seconds_limit, dict_t):
        # Implementación robusta para 1-clic
        st.session_state.processing_audio = False # Reset flag al renderizar mic
        
        # Centrar mic con columnas
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            audio_bytes = audio_recorder(text=dict_t["short_mic_hint"], icon_size="3x", key=key_mic)
        
        if audio_bytes and len(audio_bytes) > 1000:
             # Evitar re-procesar el mismo audio instantáneamente (genera bucle con rerun)
            if audio_bytes == st.session_state.ultimo_audio and not st.session_state.processing_audio:
                return None
                
            st.session_state.ultimo_audio = audio_bytes
            st.session_state.processing_audio = True # Bloquear otros inputs
            
            with st.spinner(dict_t["listening"]):
                try:
                    r = sr.Recognizer()
                    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                        r.adjust_for_ambient_noise(source, duration=0.5)
                        audio = r.record(source, duration=seconds_limit)
                        final_text = r.recognize_google(audio, language=language_stt)
                        # Mostrar lo capturado para feedback visual inmediato
                        st.markdown(f"🎤 **{u['nombres']}:** *{final_text}*")
                        return final_text
                except sr.UnknownValueError:
                    st.error(dict_t["err_audio"])
                    return None
                except Exception as e:
                    st.error(f"Error: {e}")
                    return None
                finally:
                    st.session_state.processing_audio = False # Liberar bloqueo
        return None

    # --- TAB 1: PRÁCTICA LIBRE ---
    with tab_train:
        st.markdown(f"""
        <div style="background-color: #FF7F50; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h4 style="color: white !important; margin-top: 0px; margin-bottom: 5px; font-family: 'Helvetica Neue', sans-serif;">{t['super_power_title']}</h4>
            <span style="font-size: 1rem; font-weight: normal;">{t['super_power_desc']}</span>
        </div>
        """, unsafe_allow_html=True)

        contador_ui = st.empty()
        contador_ui.info(f"📊 {t['trainings']}: {u['frases_usadas_hoy']} / {lim_f}")
        
        lang_stt = IDIOMAS_APRENDER[lang_activo_original]["stt"]
        lang_tts = IDIOMAS_APRENDER[lang_activo_original]["tts"]
        
        if u["frases_usadas_hoy"] >= lim_f: 
            st.error(t["limit_reached"])
        else:
            # --- LÓGICA DE ENTRADA (Audio Fix + Texto) ---
            final_text = None
            
            # 1. Intentar Audio (1-clic fix activado)
            texto_audio = manejar_grabacion("mic_libre", lang_stt, lim_s, t)
            if texto_audio: final_text = texto_audio
            
            # 2. Formulario de Texto (Input secundario)
            if not st.session_state.processing_audio:
                with st.form("form_texto", clear_on_submit=True):
                    texto_escrito = st.text_input(f"{t['write']} {lang_activo_traducido}:")
                    submit_texto = st.form_submit_button(t["btn_send"])
                    if submit_texto and texto_escrito:
                        if len(texto_escrito) > lim_c: st.error(t["err_char"].format(lim_c))
                        else: final_text = texto_escrito

            # --- PROCESAMIENTO DE LA FRASE (AI) ---
            if final_text and final_text != st.session_state.ultima_frase:
                with st.spinner(f"{t['analyzing']}..."):
                    st.session_state.ultima_frase = final_text
                    res = procesar_con_gemini(final_text, lang_activo_original, idioma_nativo)
                    
                    if "error" in res: st.warning(res["error"])
                    else:
                        st.metric(t["score"], f"{res.get('puntuacion', 'N/A')}/10")
                        st.success(f"✅ {t['correction']} {res.get('correccion', '')}")
                        st.info(f"🗣️ {t['pronunciation']} {res.get('pronunciacion', '')}")
                        st.info(f"💡 {t['tip']} {res.get('tips', '')}")
                        
                        # TTS Feedback
                        try:
                            tts = gTTS(text=res.get('correccion', ''), lang=lang_tts)
                            tts.save("feedback.mp3")
                            st.audio("feedback.mp3", autoplay=True)
                        except: pass
                        
                        # Actualizar Firebase y Estado
                        doc_ref = db.collection("usuarios").document(u["correo"])
                        doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                        st.session_state.usuario_db["frases_usadas_hoy"] += 1
                        contador_ui.info(f"📊 {t['trainings']}: {st.session_state.usuario_db['frases_usadas_hoy']} / {lim_f}")
                        
            elif final_text and final_text == st.session_state.ultima_frase:
                 st.warning(t["repeat"])

    # --- TAB 2: RUTA DE ESTUDIO (Agente) ---
    with tab_agent:
        modo_elegido = st.radio(t["choose_mode"], [t["mode_fund"], t["mode_real"]], horizontal=True, label_visibility="collapsed")
        st.write("---")
        
        TEMAS_FUNDAMENTOS = t["topics"]
        progreso_key = f"progreso_{lang_activo_original}"
        leccion_actual = u.get(progreso_key, 0) 
        es_fundamentos = (modo_elegido == t["mode_fund"])
        
        # UI del progreso
        if es_fundamentos:
            st.subheader(t["mode_fund"])
            if leccion_actual < len(TEMAS_FUNDAMENTOS):
                tema_actual = TEMAS_FUNDAMENTOS[leccion_actual]
                st.info(f"**{t['lesson_txt']} {leccion_actual + 1}/{len(TEMAS_FUNDAMENTOS)}:** {tema_actual}")
            else:
                tema_actual = "Repaso General Avanzado"
                st.success("🌟 Has completado todos los fundamentos.")
        else:
            st.subheader(t["mode_real"])
            tema_actual = "Role-play conversacional"
            
        contador_agent = st.empty()
        contador_agent.info(f"📊 {t['trainings']}: {u['frases_usadas_hoy']} / {lim_f}")

        if u["frases_usadas_hoy"] >= lim_f:
            st.error(t["limit_reached"])
        else:
            sesion_reto_key = f"reto_{lang_activo_original}"
            audio_reto_key = f"audio_reto_{lang_activo_original}"
            
            if sesion_reto_key not in st.session_state:
                st.session_state[sesion_reto_key] = ""
                st.session_state[audio_reto_key] = ""
                
            reto_activo = st.session_state.get(sesion_reto_key) != ""
            ya_entreno_hoy = u["frases_usadas_hoy"] > 0
            
            # Botón de Generar/Siguiente Reto
            if not st.session_state.get("reto_superado"):
                btn_texto = t["btn_next"] if (reto_activo or ya_entreno_hoy) else t["btn_gen_lesson"]
                if st.button(btn_texto, use_container_width=True):
                    with st.spinner(t["prep_lesson"]):
                        # Prompt Engineering para retos
                        if es_fundamentos:
                            prompt_reto = f"Actúa como un tutor divertido. El usuario habla {idioma_nativo} y aprende {lang_activo_original}. Tema: '{tema_actual}'. Mini-Quiz: Hazle una pregunta rápida (Ej. ¿Cómo se dice Comida?) y pídele que responda PRONUNCIANDO la respuesta en {lang_activo_original} con su micrófono. REGLA ESTRICTA: NO uses etiquetas HTML. Devuelve SOLO JSON: {{'leccion_texto': 'Pregunta divertida en {idioma_nativo} sin HTML', 'texto_audio': 'Solo la respuesta correcta en {lang_activo_original}'}}"
                        else:
                            prompt_reto = f"El usuario habla {idioma_nativo} y practica {lang_activo_original}. Inventa un escenario de Role-play. REGLA ESTRICTA: NO uses etiquetas HTML. Devuelve SOLO JSON: {{'leccion_texto': 'Dile el contexto en {idioma_nativo} y hazle la primera pregunta en {lang_activo_original} sin HTML.', 'texto_audio': 'Solo la pregunta en {lang_activo_original}'}}"
                            
                        try:
                            client = genai.Client(api_key=API_KEY_FREE)
                            res_reto = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt_reto)
                            res_json = json.loads(res_reto.text.replace('```json\n', '').replace('```', '').strip())
                            st.session_state[sesion_reto_key] = res_json.get('leccion_texto', 'Error cargando texto')
                            st.session_state[audio_reto_key] = res_json.get('texto_audio', '')
                            st.rerun()
                        except: st.error("Error AI. Intenta de nuevo.")

            # Mostrar Reto Activo
            if st.session_state.get(sesion_reto_key):
                st.markdown(f"> 🤖 **Agente IA:** {st.session_state[sesion_reto_key]}")
                # TTS del Agente
                if st.session_state.get(audio_reto_key):
                    try:
                        tts_reto = gTTS(text=st.session_state[audio_reto_key], lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                        tts_reto.save("lesson_audio.mp3")
                        st.audio("lesson_audio.mp3", autoplay=True)
                    except: pass
                
                st.write("---")
                
                # --- LÓGICA DE RESPUESTA AL RETO (Audio Fix + Texto) ---
                final_agent = None
                
                # 1. Intentar Audio (1-clic fix activado)
                texto_audio_ag = manejar_grabacion("mic_agente", lang_stt, lim_s, t)
                if texto_audio_ag: final_agent = texto_audio_ag
                
                # 2. Formulario de Texto para Agente
                if not st.session_state.processing_audio:
                    with st.form("form_agent", clear_on_submit=True):
                        texto_agent = st.text_input(f"{t['write']} {lang_activo_traducido}:", key="txt_agent")
                        submit_agent = st.form_submit_button(t["btn_send"])
                        if submit_agent and texto_agent: final_agent = texto_agent

                # --- EVALUACIÓN DE LA RESPUESTA ---
                if final_agent:
                    with st.spinner(f"{t['analyzing']}..."):
                        prompt_eval = f"Actúa como profesor de {lang_activo_original}. El usuario habla {idioma_nativo}. El reto era: '{st.session_state[sesion_reto_key]}'. El usuario respondió: '{final_agent}'. Evalúa y devuelve SOLO JSON: {{'correccion': 'FRASE CORREGIDA EN {lang_activo_original}.', 'tips': 'Explica en {idioma_nativo} si logró el reto.', 'puntuacion': '1-10'}}"
                        try:
                            client = genai.Client(api_key=API_KEY_FREE)
                            res_eval = client.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt_eval)
                            res_json = json.loads(res_eval.text.replace('```json\n', '').replace('```', '').strip())
                            
                            st.metric(t["score"], f"{res_json.get('puntuacion', 'N/A')}/10")
                            st.success(f"✅ {t['correction']} {res_json.get('correccion', '')}")
                            st.info(f"💡 {t['tip']} {res_json.get('tips', '')}")
                            
                            # TTS Feedback Agente
                            try:
                                tts = gTTS(text=res_json.get('correccion', ''), lang=IDIOMAS_APRENDER[lang_activo_original]["tts"])
                                tts.save("feedback_agent.mp3")
                                st.audio("feedback_agent.mp3", autoplay=True)
                            except: pass

                            # Actualizar contadores
                            doc_ref = db.collection("usuarios").document(u["correo"])
                            doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
                            st.session_state.usuario_db["frases_usadas_hoy"] += 1
                            contador_agent.info(f"📊 {t['trainings']}: {st.session_state.usuario_db['frases_usadas_hoy']} / {lim_f}")

                            # Lógica de superación de reto
                            try:
                                puntos = int(str(res_json.get('puntuacion', '0')).replace('/10', '').strip())
                            except: puntos = 5

                            if puntos >= 7:
                                st.balloons()
                                if es_fundamentos:
                                    st.success(t["lesson_passed"])
                                    doc_ref.update({progreso_key: firestore.Increment(1)})
                                    st.session_state.usuario_db[progreso_key] = leccion_actual + 1
                                else: st.success(t["role_passed"])
                                st.session_state.reto_superado = True
                        except: st.warning("Error AI.")

            # Botón de Siguiente Reto (aparece abajo al ganar)
            if st.session_state.get("reto_superado"):
                if st.button(t["btn_next"], use_container_width=True, key="btn_next_bottom"):
                    st.session_state[sesion_reto_key] = ""
                    st.session_state[audio_reto_key] = ""
                    st.session_state.reto_superado = False
                    st.rerun()

    # --- TAB 3: UPGRADE ---
    if tab_upgrade:
        with tab_upgrade:
            st.subheader(t["up_title"])
            st.write(t["up_sub"])
            # Marketing box persuativo
            st.markdown(f"""
            <div style="background-color: #E8F0FE; padding: 15px; border-radius: 8px; border-left: 5px solid #0047AB; margin-bottom: 20px;">
                <h4 style="color: #0047AB; margin-top: 0;">🚀 Potencia tu Aprendizaje</h4>
                <p style="color: #333; font-size: 0.95rem; margin-bottom: 0;">
                Al subir a un plan de pago, accedes a modelos de Inteligencia Artificial dedicados y más avanzados. 
                Esto duplica la precisión de las correcciones, reduce el tiempo de respuesta y desbloquea 
                conversaciones mucho más fluidas y complejas. ¡Lleva tu fluidez al siguiente nivel!
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.info(f"✨ **{t['desc_standard']}**")
            st.success(f"👑 **{t['desc_pro']}**")

    # ==============================================================================
    # --- 5. MENÚ FIJO FLOTANTE AL FONDO (THE ISLANDS - FIX) ---
    # ==============================================================================
    
    # Creamos el contenedor HTML para el menú flotante
    st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
    
    # Dentro del footer, usamos columnas de Streamlit para que los widgets funcionen
    # columnas: [Vacío, Selector Idioma, Separador, Botón Logout, Vacío]
    col_f_1, col_f_lang, col_f_sep, col_f_logout, col_f_5 = st.columns([1, 4, 1, 4, 1])
    
    with col_f_lang:
        # Selector de Idioma Nativo (widget discreto)
        # Definición de opciones y traducción
        opciones_nativo_traducidas = [UI_TEXT[st.session_state.ui_lang]["lang_name"][lang] for lang in UI_TEXT.keys()]
        # Encontrar índice del idioma actual para que aparezca seleccionado
        idioma_actual_nombre_traducido = UI_TEXT[st.session_state.ui_lang]["lang_name"][idioma_nativo]
        try:
            idx_lang_actual = opciones_nativo_traducidas.index(idioma_actual_nombre_traducido)
        except ValueError:
            idx_lang_actual = 0 # Fallback Español

        # Renderizar el selectbox discreto (label_visibility oculto por CSS)
        label_nativo_discreto = t["native_lang"] # "Tu Idioma"
        seleccion_nativo_traducida = st.selectbox(
            label_nativo_discreto, 
            opciones_nativo_traducidas, 
            index=idx_lang_actual, 
            key="lang_selector_fixed",
            label_visibility="collapsed" # Ocultar label para que se vea limpio
        )
        
        # Lógica de cambio de idioma nativo (inversa para encontrar llave original)
        seleccion_nativo_llave_original = "Español" # Fallback
        t_current_ui = UI_TEXT[st.session_state.ui_lang]
        for original_key, traducido in t_current_ui["lang_name"].items():
            if traducido == seleccion_nativo_traducida and original_key in UI_TEXT.keys():
                seleccion_nativo_llave_original = original_key
                break

        # Ejecutar cambio si seleccionó uno diferente
        if seleccion_nativo_llave_original != st.session_state.ui_lang:
            st.session_state.ui_lang = seleccion_nativo_llave_original
            st.rerun()

    with col_f_logout:
        # Botón de Cerrar Sesión (widget discreto)
        if st.button(t["logout"], key="logout_fixed", use_container_width=True):
            # Limpieza completa de sesión
            st.session_state.usuario_db = None
            st.session_state.idioma_activo = None
            st.session_state.ui_lang = "Español" # Reset a default
            # Limpiar parámetros URL para evitar re-login automático
            if "user_session" in st.query_params: del st.query_params["user_session"]
            if "lang_session" in st.query_params: del st.query_params["lang_session"]
            st.rerun()

    # Cerramos el contenedor HTML
    st.markdown('</div>', unsafe_allow_html=True)
