import os
import io
import PIL.Image
import json
import requests  # <-- Añadido para enviar peticiones a Telegram
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai

load_dotenv()

# Inicializamos el cliente moderno
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

from app.db.supabase_client import insert_alerta_row

# ==========================================
# 📱 CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8848721200:AAGbvjLg51ng6CLxpatz7pnAbvteHg3JN1k"
TELEGRAM_CHAT_ID = "-5057471780"

def enviar_alerta_telegram(mensaje: str, imagen_bytes: bytes = None):
    """
    Envía la alerta directo al celular del guardia.
    Usamos la imagen en memoria (bytes) para máxima velocidad.
    """
    try:
        if not imagen_bytes:
            # Si por alguna razón no hay imagen, manda solo texto
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje})
        else:
            # Mandamos la foto con el mensaje como "caption"
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            archivos = {'photo': ('evidencia.jpg', imagen_bytes, 'image/jpeg')}
            datos = {'chat_id': TELEGRAM_CHAT_ID, 'caption': mensaje}
            requests.post(url, data=datos, files=archivos)
            
        print("📱 Notificación enviada a Telegram exitosamente.")
    except Exception as e:
        print(f"❌ Error al notificar por Telegram: {e}")

# ==========================================
# 🚀 APLICACIÓN FASTAPI
# ==========================================
app = FastAPI(
    title="SmartGuard AI - Security API",
    description="Sistema de detección de amenazas - Versión 2.5 (2026)",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "online", "message": "SmartGuard API v2.3 estable en Talca"}

@app.post("/analizar/{camara_id}")
async def analizar_imagen(camara_id: int, file: UploadFile = File(...)):
    try:
        print("📸 Paso 1: Leyendo imagen...")
        request_object_content = await file.read()
        img = PIL.Image.open(io.BytesIO(request_object_content))

        print("🧠 Paso 2: Enviando a Google Gemini...")
        prompt = """
        Actúa como un experto en seguridad. Analiza esta imagen y detecta amenazas (armas, robos, violencia).
        Responde estrictamente en JSON:
        {
            "etiqueta": "Categoría corta",
            "descripcion": "Análisis técnico",
            "severidad": "alta, media o baja"
        }
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[prompt, img]
        )
        
        print("📝 Paso 3: Procesando respuesta de la IA...")
        text_response = response.text
        clean_response = text_response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("json")[-1].split("```")[0].strip()
            
        analisis_ia = json.loads(clean_response)

        print("☁️ Paso 4: Intentando guardar en Supabase...")
        resultado_final = {
            "camara_id": camara_id,
            "etiqueta": analisis_ia.get("etiqueta", "Detección"),
            "descripcion": analisis_ia.get("descripcion", "Sin detalles"),
            "severidad": analisis_ia.get("severidad", "baja"),
            "tipo": "deteccion_ia_2.5",
            "metadata": {"model": "gemini-2.5-flash", "region": "Talca-Chile"}
        }
        insert_alerta_row(resultado_final)

        print("📱 Paso 5: Despachando a Telegram...")
        mensaje_tg = (
            f"🚨 SMARTGUARD ALERT - Cámara {camara_id} 🚨\n\n"
            f"⚠️ Detección: {resultado_final['etiqueta']}\n"
            f"🔴 Severidad: {resultado_final['severidad'].upper()}\n"
            f"📝 Detalle: {resultado_final['descripcion']}"
        )
        enviar_alerta_telegram(mensaje_tg, request_object_content)

        return {"status": "success", "data": resultado_final}

    except Exception as e:
        print(f"❌ COLAPSO EN EL BACKEND: {e}")
        if "429" in str(e):
            raise HTTPException(status_code=429, detail="Cuota de Google agotada.")
        raise HTTPException(status_code=500, detail=str(e))