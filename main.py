import os
import json
import logging
import smtplib
import secrets
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
import groq
from cachetools import LRUCache

# ─── CARGAR .env (sin dependencias externas) ───
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())

# ─── POOL DE LLAVES GEMINI Y GROQ ───
GEMINI_KEYS = []
for k, v in os.environ.items():
    if k.startswith("GEMINI_API_KEY") and v.strip():
        GEMINI_KEYS.append(v.strip())

if not GEMINI_KEYS and os.getenv("GEMINI_API_KEY"):
    GEMINI_KEYS.append(os.getenv("GEMINI_API_KEY", ""))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Instanciar cliente Groq de contingencia
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = groq.Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        pass

# ─── CACHE LRU (Max 1000 respuestas, ahorra cuota IA) ───
ai_cache = LRUCache(maxsize=1000)

EMAIL_USER     = os.getenv("EMAIL_USER", "soporte.voxis@gmail.com")
EMAIL_PASS     = os.getenv("EMAIL_PASS", "")   # Google App Password

# ─── OTP IN-MEMORY STORE ───
# { email: { code: str, expires_at: float, attempts: int } }
_otp_store: dict[str, dict[str, str | float | int]] = {}

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voxis AI Backend")

# ─── CORS: permite peticiones desde el HTML (local o desplegado) ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MODELOS GEMINI (verificados en ai.google.dev - Marzo 2026) ───
MODELOS_GEMINI = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
]

# ─── ESQUEMAS DE DATOS ───
class UserInput(BaseModel):
    phrase: str
    idioma_aprender: str = "Inglés"
    idioma_nativo: str = "Español"
    reto_esperado: str = ""

# ─── LÓGICA DE CORRECCIÓN CON IA (Híbrida: Caché -> Gemini Pool -> Groq) ───
def procesar_con_gemini(texto: str, idioma_aprender: str, idioma_nativo: str, reto_esperado: str = "") -> dict:
    cache_key = f"{texto.lower().strip()}|{reto_esperado.lower().strip()}|{idioma_aprender}"
    if cache_key in ai_cache:
        logger.warning("Retornando respuesta desde el Caché LRU local (Ahorro 100% cuota) ⚡")
        return ai_cache[cache_key]

    prompt = (
        f"Actúa como un profesor nativo y conversacional experto de {idioma_aprender}. "
        f"El estudiante habla nativamente {idioma_nativo}. "
        f"Sigue la metodología 'Communicative Language Teaching'. La comunicación efectiva importa más que la gramática perfecta. "
        f"Aplica 'Comprehensible Input (i+1)' y 'Spaced Reinforcement'. "
        f"Si el usuario está en nivel principiante/Fundamentos, usa frases MUY cortas (6-8 palabras) y cotidianas. "
        f"RESPONDE SIEMPRE EN ESTE FORMATO JSON EXACTO (sin markdown):\n"
        f"{{\n"
        f'  "correccion_nativa": "Reescribe la frase del usuario de la forma más natural posible EN {idioma_aprender}",\n'
        f'  "tip_pronunciacion": "Consejo breve de pronunciación o fluidez EN {idioma_nativo}",\n'
        f'  "explicacion_breve": "Explicación MUY corta (máx 3 líneas) sobre la mejora EN {idioma_nativo}",\n'
        f'  "ejemplo_adicional": "Un ejemplo corto adicional usando la misma estructura correcta EN {idioma_aprender}",\n'
        f'  "respuesta_roleplay": "Respuesta natural para continuar la conversación EN {idioma_aprender}",\n'
        f'  "puntuacion": "Evalúa del 1 al 10 qué tan comprensible fue el mensaje original"\n'
        f"}}\n"
        f"Regla crítica: 'correccion_nativa', 'ejemplo_adicional' y 'respuesta_roleplay' DEBEN estar en {idioma_aprender}. "
        f"'tip_pronunciacion' y 'explicacion_breve' DEBEN estar en {idioma_nativo}. Usa un JSON válido.\n"
    )

    if reto_esperado:
        prompt += (
            f"\nREGLA MUY ESTRICTA DE EVALUACIÓN:\nEl reto del usuario era decir exactamente esto o responder a este tema: '{reto_esperado}'. "
            f"Evalúa EXCLUSIVAMENTE si lo que dijo responde lógicamente a este reto. "
            f"Si lo que dijo ('{texto}') NO tiene relación lógica con el reto planteado (por ejemplo, hablar de pie o comida cuando se pidió la palabra mano), "
            f"su puntuación DEBE SER MUY BAJA (ej. 1 o 2). Además, en 'explicacion_breve' debes decirle en tono amable que lo que dijo no tiene sentido con el reto, "
            f"señalando la incoherencia de manera constructiva.\n"
        )

    prompt += f"Frase a evaluar: '{texto}'"
    
    # 1. Intentar con el Pool de Llaves Gemini
    for i, key in enumerate(GEMINI_KEYS):
        client = genai.Client(api_key=key)
        for modelo in MODELOS_GEMINI:
            try:
                response = client.models.generate_content(model=modelo, contents=prompt)
                res_text = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(res_text)
                logger.info(f"✅ Éxito Gemini ({modelo}) con Key #{i+1}")
                ai_cache[cache_key] = result
                return result
            except json.JSONDecodeError:
                result = {
                    "correccion_nativa": response.text[:300],
                    "tip_pronunciacion": "",
                    "explicacion_breve": "Error al procesar la explicación.",
                    "ejemplo_adicional": "",
                    "respuesta_roleplay": "",
                    "puntuacion": "5"
                }
                ai_cache[cache_key] = result
                return result
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["429", "quota", "resource_exhausted"]):
                    logger.warning(f"⚠️ Gemini Key #{i+1} modelo {modelo} agotado (429).")
                else:
                    logger.warning(f"❌ Error en Gemini Key #{i+1} modelo {modelo}: {e}")
                continue
                
    # 2. Si TODAS las llaves y modelos Gemini fallan -> Fallback a Groq LLaMA 3
    if groq_client:
        try:
            logger.warning("🚨 ¡Todas las llaves Gemini fallaron! Usando Groq Llama 3.3 de emergencia 🛟")
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON-only response assistant. Provide ONLY A PURE JSON OBJECT according to the user prompt instructions without markdown formatting, backticks, or any additional text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
            )
            res_text = chat_completion.choices[0].message.content.replace("```json", "").replace("```", "").strip()
            result = json.loads(res_text)
            logger.info("✅ Éxito usando Groq Llama 3.3")
            ai_cache[cache_key] = result
            return result
        except json.JSONDecodeError:
            result = {
                "correccion_nativa": "Error parsing output from groq.",
                "tip_pronunciacion": "",
                "explicacion_breve": "Error de parseo JSON de soporte.",
                "ejemplo_adicional": "",
                "respuesta_roleplay": "",
                "puntuacion": "5"
            }
            ai_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"❌ Error crítico en Groq Fallback: {e}")

    return {"error": "Todos los servidores de IA están ocupados. Intenta en un par de segundos."}

# ─── ENDPOINTS ───
@app.get("/")
@app.head("/")
def home():
    return {"status": "Voxis AI Backend activo ✅", "modelos": MODELOS_GEMINI}

@app.post("/evaluate")
async def evaluate_phrase(data: UserInput):
    if not data.phrase or len(data.phrase.strip()) < 2:
        return {"error": "Frase muy corta."}
    if len(data.phrase) > 500:
        return {"error": "Frase demasiado larga (máx. 500 caracteres)."}

    result = procesar_con_gemini(data.phrase, data.idioma_aprender, data.idioma_nativo, data.reto_esperado)

    if "error" in result:
        return result

    return {
        "original":           data.phrase,
        "correccion_nativa":  result.get("correccion_nativa", ""),
        "tip_pronunciacion":  result.get("tip_pronunciacion", ""),
        "explicacion_breve":  result.get("explicacion_breve", ""),
        "ejemplo_adicional":  result.get("ejemplo_adicional", ""),
        "respuesta_roleplay": result.get("respuesta_roleplay", ""),
        "puntuacion":         result.get("puntuacion", "5")
    }

# ─── CHALLENGE ENDPOINT ───
class ChallengeInput(BaseModel):
    modo: str = "fund"
    tema: str = "Saludos"
    idioma_aprender: str = "Inglés"
    idioma_nativo: str = "Español"
    errores_hint: str = ""

@app.post("/challenge")
async def generate_challenge(data: ChallengeInput):
    perfil = ""
    if data.errores_hint:
        perfil = f" Ojo, el estudiante suele cometer estos errores: {data.errores_hint}. Crea el reto enfocándote sutilmente en practicar esto."

    if data.modo == "fund":
        prompt = (
            f"Eres un tutor divertido de idiomas. El estudiante habla {data.idioma_nativo} y aprende {data.idioma_aprender}. "
            f"Tema: '{data.tema}'.{perfil} Elige UNA mecánica al azar (Repetición, Mini-Quiz, o Traducción). "
            f"Sé breve y usa emojis. Escribe el reto en {data.idioma_nativo}. "
            f"Responde ÚNICAMENTE con JSON válido, sin texto adicional ni markdown: "
            f'{{"reto": "texto del reto aquí", "frase_audio": "solo las palabras en {data.idioma_aprender}"}}'
        )
    else:
        prompt = (
            f"Eres un tutor de idiomas creativo. El estudiante habla {data.idioma_nativo} y practica {data.idioma_aprender}. "
            f"Crea un role-play de la vida real (cafetería, aeropuerto, tienda, etc.).{perfil} "
            f"Contexto breve en {data.idioma_nativo}, primera pregunta en {data.idioma_aprender}. Usa emojis. "
            f"Responde ÚNICAMENTE con JSON válido, sin texto adicional ni markdown: "
            f'{{"reto": "contexto + situación aquí", "frase_audio": "primera frase en {data.idioma_aprender}"}}'
        )

    for i, key in enumerate(GEMINI_KEYS):
        client = genai.Client(api_key=key)
        for modelo in MODELOS_GEMINI:
            try:
                response = client.models.generate_content(model=modelo, contents=prompt)
                res_text = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(res_text)
                return {
                    "reto":        result.get("reto", ""),
                    "frase_audio": result.get("frase_audio", ""),
                }
            except json.JSONDecodeError:
                return {"reto": response.text.strip()[:500], "frase_audio": ""}
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["429", "quota", "resource_exhausted"]):
                    logger.warning(f"⚠️ Gemini Key #{i+1} modelo {modelo} agotado (429) en Retos.")
                else:
                    logger.warning(f"❌ Error Gemini Key #{i+1} modelo {modelo} en Retos: {e}")
                continue

    if groq_client:
        try:
            logger.warning("🚨 Todas las llaves Gemini fallaron generando Retos. Usando Groq Llama 3.3 🛟")
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a JSON-only response bot. Only return JSON without markdown."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
            )
            res_text = chat_completion.choices[0].message.content.replace("```json", "").replace("```", "").strip()
            result = json.loads(res_text)
            return {
                "reto":        result.get("reto", ""),
                "frase_audio": result.get("frase_audio", ""),
            }
        except Exception as e:
            logger.error(f"❌ Error en Groq Fallback (Retos): {e}")

    return {"error": "Todos los modelos de IA están ocupados. Intenta en unos segundos."}


# ─── OTP: ENVIAR CÓDIGO ───
class OtpRequest(BaseModel):
    email: str
    lang: str = "es"

@app.post("/send-otp")
async def send_otp(data: OtpRequest):
    email = data.email.strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "error": "Correo inválido."}

    # -- MASTER CODE BYPASS --
    if email in ["master@voxis.com", "adonis3151@gmail.com", "master"]:
        code = "0000"
        _otp_store[email] = {
            "code":       code,
            "expires_at": time.time() + 86400,  # 24 horas
            "attempts":   0,
        }
        return {"ok": True, "dev_code": code, "warning": "Master account bypass"}

    code = str(secrets.randbelow(9000) + 1000)   # 1000–9999
    _otp_store[email] = {
        "code":       code,
        "expires_at": time.time() + 600,  # 10 minutos
        "attempts":   0,
    }

    subjects = {
        "es": "Tu código de acceso a Voxis AI",
        "en": "Your Voxis AI access code",
        "fr": "Votre code d'accès Voxis AI",
        "de": "Dein Voxis-AI-Zugangscode",
        "it": "Il tuo codice di accesso Voxis AI",
        "pt": "Seu código de acesso Voxis AI",
    }
    subject = subjects.get(data.lang, subjects["es"])

    html_body = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#0A0E1A;padding:40px 20px;">
      <div style="max-width:420px;margin:0 auto;background:#131929;border-radius:20px;
                  border:1px solid #1E2A45;padding:36px;text-align:center;">
        <div style="font-size:2rem;margin-bottom:6px;">🎙️</div>
        <div style="font-size:1.4rem;font-weight:800;color:#FFFFFF;margin-bottom:4px;">Voxis AI</div>
        <div style="font-size:0.8rem;color:#7A84A0;margin-bottom:28px;letter-spacing:1.5px;text-transform:uppercase;">Your 24/7 AI Language Trainer</div>
        <div style="font-size:0.9rem;color:#C9D0E0;margin-bottom:20px;">Tu código de verificación es:</div>
        <div style="background:linear-gradient(135deg,#FF7F50,#E05020);border-radius:14px;
                    padding:20px 0;margin:0 auto 24px auto;font-size:2.8rem;font-weight:900;
                    letter-spacing:12px;color:#FFFFFF;width:240px;">{code}</div>
        <div style="font-size:0.78rem;color:#7A84A0;line-height:1.6;">
          Expira en <strong style="color:#C9D0E0;">10 minutos</strong>.<br>
          Si no lo solicitaste, ignora este correo.
        </div>
      </div>
    </div>"""

    try:
        if not EMAIL_PASS:
            logger.warning("EMAIL_PASS no configurado — OTP no enviado por correo.")
            return {"ok": True, "dev_code": code, "warning": "EMAIL_PASS not set — code returned for dev only"}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Voxis AI <{EMAIL_USER}>"
        msg["To"]      = email
        msg.attach(MIMEText(f"Tu código de acceso a Voxis AI: {code}. Expira en 10 minutos.", "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, email, msg.as_string())

        return {"ok": True}
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth error — verifica EMAIL_USER y EMAIL_PASS (App Password de Google)")
        return {"ok": False, "error": "Error de autenticación del correo. Contacta soporte."}
    except Exception as e:
        logger.error(f"Error enviando OTP: {e}")
        return {"ok": False, "error": "No se pudo enviar el correo. Intenta de nuevo."}


# ─── OTP: VERIFICAR CÓDIGO ───
class OtpVerify(BaseModel):
    email: str
    code: str

@app.post("/verify-otp")
async def verify_otp(data: OtpVerify):
    email = data.email.strip().lower()
    code  = data.code.strip()

    entry = _otp_store.get(email)
    if not entry:
        return {"ok": False, "error": "No hay código activo para este correo. Solicita uno nuevo."}

    if time.time() > entry["expires_at"]:
        del _otp_store[email]
        return {"ok": False, "error": "El código expiró. Solicita uno nuevo."}

    if entry["attempts"] >= 3:
        del _otp_store[email]
        return {"ok": False, "error": "Demasiados intentos. Solicita un nuevo código."}

    entry["attempts"] += 1

    if code != entry["code"]:
        remaining = 3 - entry["attempts"]
        return {"ok": False, "error": f"Código incorrecto. {remaining} intento(s) restante(s)."}

    # ✅ Código correcto
    del _otp_store[email]
    return {"ok": True}

# ─── FORMULARIO DE CONTACTO ───
class ContactRequest(BaseModel):
    name: str
    email: str
    message: str

@app.post("/contact")
async def receive_contact(data: ContactRequest):
    correo_remitente = data.email.strip()
    if not correo_remitente or "@" not in correo_remitente:
        return {"ok": False, "error": "Correo inválido."}

    try:
        if not EMAIL_PASS:
            logger.warning("EMAIL_PASS no configurado — Mensaje de contacto no enviado.")
            return {"ok": False, "error": "Servidor de correo no configurado."}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Soporte Voxis - Nuevo mensaje de {data.name}"
        msg["From"] = f"Voxis App <{EMAIL_USER}>"
        msg["To"] = "soporte.voxis@gmail.com"
        msg.add_header('reply-to', correo_remitente)

        body = f"Nombre: {data.name}\nCorreo de contacto: {correo_remitente}\n\nMensaje:\n{data.message}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, "soporte.voxis@gmail.com", msg.as_string())

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error enviando contacto: {e}")
        return {"ok": False, "error": f"Fallo al enviar el mensaje al servidor: {str(e)}"}
