import streamlit as st
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter
from datetime import date
import json
import time
import io
import speech_recognition as sr
from gtts import gTTS
from audio_recorder_streamlit import audio_recorder

# --- 1. CONFIGURACIÓN DE LLAVES Y FIREBASE ---
API_KEY_FREE = "AIzaSyDzyIgcyxI_xau0WVvs1UPQLXU73CURd3o"
API_KEY_PAID = "TU_LLAVE_DE_PAGO_AQUI"

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

st.set_page_config(page_title="Voxis AI", page_icon="🎙️")

# --- 2. CONFIGURACIÓN DE IDIOMAS Y TRADUCCIONES ---
IDIOMAS_APRENDER = {
    "Inglés": {"stt": "en-US", "tts": "en"},
    "Español": {"stt": "es-ES", "tts": "es"},
    "Francés": {"stt": "fr-FR", "tts": "fr"},
    "Alemán": {"stt": "de-DE", "tts": "de"},
    "Italiano": {"stt": "it-IT", "tts": "it"},
    "Portugués": {"stt": "pt-BR", "tts": "pt"},
    "Mandarín": {"stt": "zh-CN", "tts": "zh-CN"},
    "Japonés": {"stt": "ja-JP", "tts": "ja"},
    "Coreano": {"stt": "ko-KR", "tts": "ko"},
    "Ruso": {"stt": "ru-RU", "tts": "ru"}
}

UI_TEXT = {
    "Español": {
        "login_sub": "Identifícate para comenzar tu entrenamiento.",
        "email": "Correo Electrónico:",
        "names": "Nombres:",
        "lastnames": "Apellidos:",
        "wa": "WhatsApp (Obligatorio código de país):",
        "plan_select": "Elige tu plan inicial:",
        "btn_login": "Entrar / Registrarse",
        "greeting": "Hola",
        "plan": "Plan actual",
        "trainings": "Entrenamientos",
        "logout": "Cerrar Sesión",
        "tab_train": "🏋️ Entrenamiento",
        "tab_upgrade": "⭐ Mejorar Plan",
        "upgrade_title": "Desbloquea todo tu potencial 🚀",
        "upgrade_sub": "(Pronto: Enlace directo de pago con Stripe / Tarjetas)",
        "learn_prompt": "🌐 Idioma a entrenar:",
        "record": "Graba tu frase en",
        "write": "O escribe tu frase en",
        "listening": "Escuchando...",
        "analyzing": "Analizando tu nivel de",
        "score": "Puntaje",
        "correction": "Corrección:",
        "pronunciation": "Pronunciación:",
        "tip": "Tip:",
        "err_char": "Límite de {} caracteres máximo.",
        "err_audio": "Límite de {} segundos máximo.",
        "limit_reached": "🔒 Límite de frases alcanzado por hoy. Ve a la pestaña 'Mejorar Plan' para continuar.",
        "repeat": "Ya procesamos esta frase. Escribe o graba una diferente para continuar.",
        "desc_gratis": "Plan GRATIS ($0): 5 frases al día, audios de 5s, 200 caracteres.",
        "desc_starter": "Plan STARTER ($1/mes): 20 frases al día, audios de 10s, 400 caracteres.",
        "desc_promax": "Plan PRO MAX ($5/mes): 100 frases al día, audios de 10s, 400 caracteres. (Uso personal)"
    },
    "Inglés": {
        "login_sub": "Log in to start your training.",
        "email": "Email:",
        "names": "First Name:",
        "lastnames": "Last Name:",
        "wa": "WhatsApp (Country code required):",
        "plan_select": "Choose your starting plan:",
        "btn_login": "Login / Register",
        "greeting": "Hello",
        "plan": "Current Plan",
        "trainings": "Trainings",
        "logout": "Log Out",
        "tab_train": "🏋️ Training",
        "tab_upgrade": "⭐ Upgrade Plan",
        "upgrade_title": "Unlock your full potential 🚀",
        "upgrade_sub": "(Soon: Direct payment link via Stripe / Credit Cards)",
        "learn_prompt": "🌐 Language to train:",
        "record": "Record your phrase in",
        "write": "Or type your phrase in",
        "listening": "Listening...",
        "analyzing": "Analyzing your level of",
        "score": "Score",
        "correction": "Correction:",
        "pronunciation": "Pronunciation:",
        "tip": "Tip:",
        "err_char": "Maximum {} characters limit.",
        "err_audio": "Maximum {} seconds limit.",
        "limit_reached": "🔒 Phrase limit reached for today. Go to the 'Upgrade Plan' tab to continue.",
        "repeat": "We already processed this phrase. Type or record a different one.",
        "desc_gratis": "FREE Plan ($0): 5 phrases/day, 5s audio, 200 characters.",
        "desc_starter": "STARTER Plan ($1/mo): 20 phrases/day, 10s audio, 400 characters.",
        "desc_promax": "PRO MAX Plan ($5/mo): 100 phrases/day, 10s audio, 400 characters. (Personal use)"
    },
    "Francés": {
        "login_sub": "Connectez-vous pour commencer.",
        "email": "E-mail:",
        "names": "Prénom:",
        "lastnames": "Nom de famille:",
        "wa": "WhatsApp (Indicatif requis):",
        "plan_select": "Choisissez votre forfait :",
        "btn_login": "Se connecter / S'inscrire",
        "greeting": "Bonjour",
        "plan": "Forfait actuel",
        "trainings": "Entraînements",
        "logout": "Se déconnecter",
        "tab_train": "🏋️ Entraînement",
        "tab_upgrade": "⭐ Améliorer le forfait",
        "upgrade_title": "Débloquez tout votre potentiel 🚀",
        "upgrade_sub": "(Bientôt : Lien de paiement direct via Stripe / Cartes)",
        "learn_prompt": "🌐 Langue à pratiquer:",
        "record": "Enregistrez votre phrase en",
        "write": "Ou écrivez votre phrase en",
        "listening": "Écoute en cours...",
        "analyzing": "Analyse de votre niveau de",
        "score": "Score",
        "correction": "Correction:",
        "pronunciation": "Prononciation:",
        "tip": "Astuce:",
        "err_char": "Limite de {} caractères maximum.",
        "err_audio": "Limite de {} secondes maximum.",
        "limit_reached": "🔒 Limite de phrases atteinte. Allez à l'onglet 'Améliorer le forfait'.",
        "repeat": "Nous avons déjà traité cette phrase. Essayez-en une autre.",
        "desc_gratis": "GRATUIT (0$) : 5 phrases/jour, audio 5s, 200 caractères.",
        "desc_starter": "STARTER (1$/mois) : 20 phrases/jour, audio 10s, 400 caractères.",
        "desc_promax": "PRO MAX (5$/mois) : 100 phrases/jour, audio 10s, 400 caractères. (Usage personnel)"
    },
    "Alemán": {
        "login_sub": "Melden Sie sich an, um zu beginnen.",
        "email": "E-Mail:",
        "names": "Vorname:",
        "lastnames": "Nachname:",
        "wa": "WhatsApp (Ländercode erforderlich):",
        "plan_select": "Wählen Sie Ihren Plan:",
        "btn_login": "Anmelden / Registrieren",
        "greeting": "Hallo",
        "plan": "Aktueller Plan",
        "trainings": "Trainings",
        "logout": "Abmelden",
        "tab_train": "🏋️ Training",
        "tab_upgrade": "⭐ Plan aktualisieren",
        "upgrade_title": "Schalten Sie Ihr volles Potenzial frei 🚀",
        "upgrade_sub": "(Bald: Direkter Zahlungslink über Stripe / Kreditkarten)",
        "learn_prompt": "🌐 Zu übende Sprache:",
        "record": "Sprechen Sie Ihren Satz auf",
        "write": "Oder schreiben Sie Ihren Satz auf",
        "listening": "Höre zu...",
        "analyzing": "Analysiere dein Niveau in",
        "score": "Punktzahl",
        "correction": "Korrektur:",
        "pronunciation": "Aussprache:",
        "tip": "Tipp:",
        "err_char": "Maximal {} Zeichen Limit.",
        "err_audio": "Maximal {} Sekunden Limit.",
        "limit_reached": "🔒 Satzlimit erreicht. Gehen Sie zum Tab 'Plan aktualisieren'.",
        "repeat": "Satz bereits verarbeitet. Versuchen Sie einen anderen.",
        "desc_gratis": "GRATIS ($0): 5 Sätze/Tag, 5s Audio, 200 Zeichen.",
        "desc_starter": "STARTER ($1/Monat): 20 Sätze/Tag, 10s Audio, 400 Zeichen.",
        "desc_promax": "PRO MAX ($5/Monat): 100 Sätze/Tag, 10s Audio, 400 Zeichen. (Privatnutzung)"
    },
    "Italiano": {
        "login_sub": "Accedi per iniziare.",
        "email": "Email:",
        "names": "Nome:",
        "lastnames": "Cognome:",
        "wa": "WhatsApp (Prefisso obbligatorio):",
        "plan_select": "Scegli il tuo piano:",
        "btn_login": "Accedi / Registrati",
        "greeting": "Ciao",
        "plan": "Piano attuale",
        "trainings": "Allenamenti",
        "logout": "Esci",
        "tab_train": "🏋️ Allenamento",
        "tab_upgrade": "⭐ Migliora Piano",
        "upgrade_title": "Sblocca tutto il tuo potenziale 🚀",
        "upgrade_sub": "(Presto: Link di pagamento diretto tramite Stripe / Carte)",
        "learn_prompt": "🌐 Lingua da allenare:",
        "record": "Registra la tua frase in",
        "write": "O scrivi la tua frase in",
        "listening": "In ascolto...",
        "analyzing": "Analizzando il tuo livello di",
        "score": "Punteggio",
        "correction": "Correzione:",
        "pronunciation": "Pronuncia:",
        "tip": "Suggerimento:",
        "err_char": "Limite massimo di {} caratteri.",
        "err_audio": "Limite massimo di {} secondi.",
        "limit_reached": "🔒 Limite di frasi raggiunto. Vai alla scheda 'Migliora Piano'.",
        "repeat": "Frase già elaborata. Provane un'altra.",
        "desc_gratis": "GRATIS ($0): 5 frasi/giorno, audio 5s, 200 caratteri.",
        "desc_starter": "STARTER ($1/mese): 20 frasi/giorno, audio 10s, 400 caratteri.",
        "desc_promax": "PRO MAX ($5/mese): 100 frasi/giorno, audio 10s, 400 caratteri. (Uso personale)"
    },
    "Portugués": {
        "login_sub": "Faça login para começar.",
        "email": "E-mail:",
        "names": "Nomes:",
        "lastnames": "Sobrenomes:",
        "wa": "WhatsApp (Código do país obrigatório):",
        "plan_select": "Escolha seu plano:",
        "btn_login": "Entrar / Registrar",
        "greeting": "Olá",
        "plan": "Plano atual",
        "trainings": "Treinos",
        "logout": "Sair",
        "tab_train": "🏋️ Treinamento",
        "tab_upgrade": "⭐ Melhorar Plano",
        "upgrade_title": "Desbloqueie todo o seu potencial 🚀",
        "upgrade_sub": "(Em breve: Link de pagamento direto via Stripe / Cartões)",
        "learn_prompt": "🌐 Idioma para treinar:",
        "record": "Grave sua frase em",
        "write": "Ou digite sua frase em",
        "listening": "Ouvindo...",
        "analyzing": "Analisando seu nível de",
        "score": "Pontuação",
        "correction": "Correção:",
        "pronunciation": "Pronúncia:",
        "tip": "Dica:",
        "err_char": "Limite máximo de {} caracteres.",
        "err_audio": "Limite máximo de {} segundos.",
        "limit_reached": "🔒 Limite de frases atingido. Vá para a aba 'Melhorar Plano'.",
        "repeat": "Já processamos esta frase. Tente uma diferente.",
        "desc_gratis": "GRÁTIS ($0): 5 frases/dia, áudio 5s, 200 caracteres.",
        "desc_starter": "STARTER ($1/mês): 20 frases/dia, áudio 10s, 400 caracteres.",
        "desc_promax": "PRO MAX ($5/mês): 100 frases/dia, áudio 10s, 400 caracteres. (Uso pessoal)"
    },
    "Mandarín": {
        "login_sub": "登录以开始。",
        "email": "电子邮件：",
        "names": "名字：",
        "lastnames": "姓氏：",
        "wa": "WhatsApp（必须输入国家代码）：",
        "plan_select": "选择您的计划：",
        "btn_login": "登录 / 注册",
        "greeting": "你好",
        "plan": "当前计划",
        "trainings": "训练",
        "logout": "退出",
        "tab_train": "🏋️ 训练",
        "tab_upgrade": "⭐ 升级计划",
        "upgrade_title": "解锁您的全部潜力 🚀",
        "upgrade_sub": "(即将推出：通过 Stripe / 信用卡的直接付款链接)",
        "learn_prompt": "🌐 要训练的语言：",
        "record": "录制您的句子用",
        "write": "或输入您的句子用",
        "listening": "正在倾听...",
        "analyzing": "正在分析你的水平",
        "score": "分数",
        "correction": "纠正：",
        "pronunciation": "发音：",
        "tip": "提示：",
        "err_char": "最多 {} 个字符限制。",
        "err_audio": "最多 {} 秒限制。",
        "limit_reached": "🔒 达到每日句子限制。请转到“升级计划”选项卡。",
        "repeat": "我们已经处理过这句话。请尝试另一句。",
        "desc_gratis": "免费 ($0)：每天 5 个句子，5 秒音频，200 个字符。",
        "desc_starter": "STARTER ($1/月)：每天 20 个句子，10 秒音频，400 个字符。",
        "desc_promax": "PRO MAX ($5/月)：每天 100 个句子，10 秒音频，400 个字符。（个人使用）"
    },
    "Japonés": {
        "login_sub": "ログインして始めましょう。",
        "email": "メールアドレス：",
        "names": "名前：",
        "lastnames": "苗字：",
        "wa": "WhatsApp（国番号必須）：",
        "plan_select": "プランを選択：",
        "btn_login": "ログイン / 登録",
        "greeting": "こんにちは",
        "plan": "現在のプラン",
        "trainings": "トレーニング",
        "logout": "ログアウト",
        "tab_train": "🏋️ トレーニング",
        "tab_upgrade": "⭐ プランをアップグレード",
        "upgrade_title": "あなたの可能性を最大限に引き出す 🚀",
        "upgrade_sub": "(近日公開: Stripe / クレジットカードによる直接支払いリンク)",
        "learn_prompt": "🌐 練習する言語：",
        "record": "フレーズを録音する（言語：",
        "write": "またはフレーズを入力する（言語：",
        "listening": "聞いています...",
        "analyzing": "レベルを分析中：",
        "score": "スコア",
        "correction": "訂正：",
        "pronunciation": "発音：",
        "tip": "ヒント：",
        "err_char": "最大 {} 文字の制限です。",
        "err_audio": "最大 {} 秒の制限です。",
        "limit_reached": "🔒 フレーズの制限に達しました。「プランをアップグレード」タブへ移動してください。",
        "repeat": "このフレーズは既に処理されました。別のフレーズを試してください。",
        "desc_gratis": "無料 ($0): 1日5フレーズ、音声5秒、200文字。",
        "desc_starter": "STARTER ($1/月): 1日20フレーズ、音声10秒、400文字。",
        "desc_promax": "PRO MAX ($5/月): 1日100フレーズ、音声10秒、400文字。（個人利用）"
    },
    "Coreano": {
        "login_sub": "로그인하여 시작하세요.",
        "email": "이메일:",
        "names": "이름:",
        "lastnames": "성:",
        "wa": "WhatsApp(국가 코드 필수):",
        "plan_select": "플랜 선택:",
        "btn_login": "로그인 / 등록",
        "greeting": "안녕하세요",
        "plan": "현재 플랜",
        "trainings": "훈련",
        "logout": "로그아웃",
        "tab_train": "🏋️ 훈련",
        "tab_upgrade": "⭐ 플랜 업그레이드",
        "upgrade_title": "잠재력을 최대한 발휘하세요 🚀",
        "upgrade_sub": "(곧 출시: Stripe / 신용카드를 통한 직접 결제 링크)",
        "learn_prompt": "🌐 훈련할 언어:",
        "record": "다음 언어로 문장 녹음:",
        "write": "또는 다음 언어로 문장 입력:",
        "listening": "듣는 중...",
        "analyzing": "레벨 분석 중:",
        "score": "점수",
        "correction": "교정:",
        "pronunciation": "발음:",
        "tip": "팁:",
        "err_char": "최대 {}자 제한입니다.",
        "err_audio": "최대 {}초 제한입니다.",
        "limit_reached": "🔒 오늘의 문장 한도에 도달했습니다. '플랜 업그레이드' 탭으로 이동하세요.",
        "repeat": "이미 처리된 문장입니다. 다른 문장을 시도해 보세요.",
        "desc_gratis": "무료 ($0): 하루 5문장, 오디오 5초, 200자.",
        "desc_starter": "STARTER ($1/월): 하루 20문장, 오디오 10초, 400자.",
        "desc_promax": "PRO MAX ($5/월): 하루 100문장, 오디오 10초, 400자. (개인용)"
    },
    "Ruso": {
        "login_sub": "Войдите, чтобы начать.",
        "email": "Электронная почта:",
        "names": "Имя:",
        "lastnames": "Фамилия:",
        "wa": "WhatsApp (Обязателен код страны):",
        "plan_select": "Выберите план:",
        "btn_login": "Войти / Зарегистрироваться",
        "greeting": "Привет",
        "plan": "Текущий план",
        "trainings": "Тренировки",
        "logout": "Выйти",
        "tab_train": "🏋️ Тренировка",
        "tab_upgrade": "⭐ Улучшить план",
        "upgrade_title": "Раскройте свой потенциал 🚀",
        "upgrade_sub": "(Скоро: Прямая ссылка на оплату через Stripe / Карты)",
        "learn_prompt": "🌐 Язык для тренировки:",
        "record": "Запишите вашу фразу на",
        "write": "Или напишите вашу фразу на",
        "listening": "Слушаю...",
        "analyzing": "Анализирую ваш уровень",
        "score": "Оценка",
        "correction": "Исправление:",
        "pronunciation": "Произношение:",
        "tip": "Совет:",
        "err_char": "Ограничение в {} символов максимум.",
        "err_audio": "Ограничение в {} секунд максимум.",
        "limit_reached": "🔒 Достигнут лимит фраз. Перейдите на вкладку «Улучшить план».",
        "repeat": "Мы уже обработали эту фразу. Попробуйте другую.",
        "desc_gratis": "БЕСПЛАТНО ($0): 5 фраз/день, аудио 5с, 200 символов.",
        "desc_starter": "STARTER ($1/мес): 20 фраз/день, аудио 10с, 400 символов.",
        "desc_promax": "PRO MAX ($5/мес): 100 фраз/день, аудио 10с, 400 символов. (Личное)"
    }
}

# Configuración del Idioma Nativo Global
idiomas_disponibles = list(UI_TEXT.keys())
idioma_nativo = st.selectbox("🗣️ Native Language / Idioma Nativo:", idiomas_disponibles, index=0)
t = UI_TEXT[idioma_nativo] 

if "ultima_frase" not in st.session_state:
    st.session_state.ultima_frase = ""

# --- 3. LÓGICA DE BASE DE DATOS Y ANTI-FRAUDE ---
def verificar_reloj_medianoche(usuario_data):
    hoy = date.today().strftime("%Y-%m-%d")
    if usuario_data.get("ultima_fecha_uso") != hoy:
        usuario_data["frases_usadas_hoy"] = 0
        usuario_data["ultima_fecha_uso"] = hoy
        db.collection("usuarios").document(usuario_data["correo"]).set(usuario_data, merge=True)
    return usuario_data

def iniciar_sesion(correo, nombres, apellidos, whatsapp, plan_elegido):
    usuarios_ref = db.collection("usuarios")
    query_wa = usuarios_ref.where(filter=FieldFilter("whatsapp", "==", whatsapp)).stream()
    
    for doc in query_wa:
        if doc.id != correo:
            return None, "Error: WhatsApp vinculado a otra cuenta."

    doc_ref = db.collection("usuarios").document(correo)
    doc = doc_ref.get()
    
    if doc.exists: 
        datos = verificar_reloj_medianoche(doc.to_dict())
        return datos, f"{t['greeting']} / Welcome."
    else:
        # LÓGICA CORREGIDA: Busca el precio exacto en cualquier idioma
        if "$0" in plan_elegido or "0$" in plan_elegido:
            plan_final = "GRATIS"
        elif "$1" in plan_elegido or "1$" in plan_elegido:
            plan_final = "STARTER"
        else:
            plan_final = "PRO MAX"

        nuevo_usuario = {
            "correo": correo,
            "nombres": nombres,
            "apellidos": apellidos,
            "whatsapp": whatsapp,
            "plan": plan_final,
            "frases_usadas_hoy": 0,
            "ultima_fecha_uso": date.today().strftime("%Y-%m-%d")
        }
            
        doc_ref.set(nuevo_usuario)
        return nuevo_usuario, "Cuenta creada / Account created."

def registrar_uso(correo):
    doc_ref = db.collection("usuarios").document(correo)
    doc_ref.update({"frases_usadas_hoy": firestore.Increment(1)})
    st.session_state.usuario_db["frases_usadas_hoy"] += 1

# --- 4. LÓGICA DE IA Y PROCESAMIENTO ---
def procesar_con_gemini(plan, texto, idioma_aprender, idioma_nativo):
    prompt = f"Actúa como preparador experto de {idioma_aprender}. El estudiante habla nativamente {idioma_nativo}. Analiza y devuelve SOLO JSON en este formato estricto: {{'correccion': '...', 'pronunciacion': '...', 'tips': '...', 'puntuacion': '1-10'}}. En 'pronunciacion', escribe cómo se lee la corrección usando la fonética de un hablante de {idioma_nativo}. En 'tips', explica los errores y da consejos EXCLUSIVAMENTE en {idioma_nativo}. Frase a corregir: {texto}"
    
    api_key_actual = API_KEY_FREE
    modelos = ['gemini-3.1-flash-lite-preview', 'gemini-flash-lite-latest', 'gemini-flash-latest', 'gemini-2.0-flash-lite']

    try:
        client = genai.Client(api_key=api_key_actual)
    except Exception as e:
        return {"error": f"Auth Error: {e}"}

    for mod in modelos:
        try:
            time.sleep(3) 
            response = client.models.generate_content(model=mod, contents=prompt)
            res_text = response.text.replace('```json\n', '').replace('```', '').strip()
            return json.loads(res_text)
        except Exception as e:
            continue
            
    return {"error": "Servers are currently busy. Please try again."}

# --- 5. INTERFAZ GRÁFICA (FRONTEND) ---
if "usuario_db" not in st.session_state:
    st.session_state.usuario_db = None

if st.session_state.usuario_db is None:
    st.image("https://via.placeholder.com/800x200.png?text=Voxis+AI", use_container_width=True)
    st.title("Voxis AI")
    st.subheader("Your 24/7 AI Language Trainer")
    st.write(t["login_sub"])
    
    with st.form("login_form"):
        correo = st.text_input(t["email"])
        nombres = st.text_input(t["names"])
        apellidos = st.text_input(t["lastnames"])
        whatsapp = st.text_input(t["wa"], placeholder="+1 555 5555")
        
        st.write("---")
        st.write(f"**{t['plan_select']}**")
        plan_elegido = st.radio(
            "Planes",
            options=[t['desc_gratis'], t['desc_starter'], t['desc_promax']],
            label_visibility="collapsed"
        )
        st.write("---")
        
        submit = st.form_submit_button(t["btn_login"])
        
        if submit and correo and whatsapp:
            whatsapp_limpio = whatsapp.replace(" ", "").replace("-", "").strip()
            if not whatsapp_limpio.startswith("+"):
                st.error("⚠️ Format error. Include '+' and country code.")
            else:
                datos, mensaje = iniciar_sesion(correo, nombres, apellidos, whatsapp_limpio, plan_elegido)
                if datos:
                    st.session_state.usuario_db = datos
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(mensaje)
else:
    usuario = st.session_state.usuario_db
    plan = usuario["plan"]
    usadas = usuario["frases_usadas_hoy"]
    
    # PARCHE: Si tu usuario de prueba quedó guardado con el error anterior, esto lo corrige visualmente.
    if plan not in ["GRATIS", "STARTER", "PRO MAX"]:
        plan = "GRATIS"
    
    if plan == "GRATIS":
        limite_frases = 5
        limite_segundos = 5
        limite_caracteres = 200
    elif plan == "STARTER":
        limite_frases = 20
        limite_segundos = 10
        limite_caracteres = 400
    else: 
        limite_frases = 100
        limite_segundos = 10
        limite_caracteres = 400
    
    st.title(f"{t['greeting']}, {usuario['nombres']} 🎙️")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"{t['plan']}: **{plan}** | Your 24/7 AI Language Trainer")
    with col2:
        if st.button(t["logout"], use_container_width=True):
            st.session_state.usuario_db = None
            st.rerun()

    if plan == "PRO MAX":
        tabs = st.tabs([t["tab_train"]])
        tab_train = tabs[0]
        tab_upgrade = None 
    else:
        tabs = st.tabs([t["tab_train"], t["tab_upgrade"]])
        tab_train = tabs[0]
        tab_upgrade = tabs[1]

    # --- PESTAÑA: MEJORAR PLAN ---
    if tab_upgrade:
        with tab_upgrade:
            st.subheader(t["upgrade_title"])
            st.write(t["upgrade_sub"])
            if plan == "GRATIS":
                st.info(f"✨ **{t['desc_starter']}**")
                st.success(f"👑 **{t['desc_promax']}**")
            elif plan == "STARTER":
                st.success(f"👑 **{t['desc_promax']}**")

    # --- PESTAÑA: ENTRENAMIENTO ---
    with tab_train:
        contador_ui = st.empty()
        contador_ui.info(f"📊 {t['trainings']}: {usadas} / {limite_frases}")
            
        idioma_aprender = st.selectbox(t["learn_prompt"], list(IDIOMAS_APRENDER.keys()))
        lang_stt = IDIOMAS_APRENDER[idioma_aprender]["stt"]
        lang_tts = IDIOMAS_APRENDER[idioma_aprender]["tts"]

        if usadas >= limite_frases:
            st.error(t["limit_reached"])
        else:
            st.write("---")
            audio_bytes = audio_recorder(text=f"{t['record']} {idioma_aprender} (Max {limite_segundos}s)", icon_size="2x")
            frase_escrita = st.text_input(f"{t['write']} {idioma_aprender} (Max {limite_caracteres} ch):")
            texto_final = ""

            if audio_bytes:
                with st.spinner(t["listening"]):
                    try:
                        recognizer = sr.Recognizer()
                        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                            data = recognizer.record(source, duration=limite_segundos) 
                            texto_final = recognizer.recognize_google(data, language=lang_stt)
                            st.success(f"🎤 : '{texto_final}'")
                    except:
                        st.error(t["err_audio"].format(limite_segundos))
            
            elif frase_escrita:
                if len(frase_escrita) > limite_caracteres:
                    st.error(t["err_char"].format(limite_caracteres))
                else:
                    texto_final = frase_escrita

            if texto_final and texto_final != st.session_state.ultima_frase:
                with st.spinner(f"{t['analyzing']} {idioma_aprender}..."):
                    st.session_state.ultima_frase = texto_final 
                    res = procesar_con_gemini(plan, texto_final, idioma_aprender, idioma_nativo)
                    
                    if "error" in res:
                        st.warning(res["error"])
                    else:
                        st.metric(t["score"], f"{res.get('puntuacion', 'N/A')}/10")
                        st.success(f"✅ {t['correction']} {res.get('correccion', '')}")
                        st.info(f"🗣️ {t['pronunciation']} {res.get('pronunciacion', '')}")
                        st.info(f"💡 {t['tip']} {res.get('tips', '')}")
                        
                        try:
                            tts = gTTS(text=res.get('correccion', ''), lang=lang_tts)
                            tts.save("feedback.mp3")
                            st.audio("feedback.mp3")
                        except:
                            pass
                        
                        registrar_uso(usuario["correo"])
                        usadas_actualizadas = st.session_state.usuario_db["frases_usadas_hoy"]
                        contador_ui.info(f"📊 {t['trainings']}: {usadas_actualizadas} / {limite_frases}")
                            
            elif texto_final and texto_final == st.session_state.ultima_frase:
                st.info(t["repeat"])
