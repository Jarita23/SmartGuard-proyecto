import os
import io
import PIL.Image
import json
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai

load_dotenv()

# Inicializamos el cliente moderno
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

from app.db.supabase_client import insert_alerta_row

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
        # 1. Leer imagen
        request_object_content = await file.read()
        img = PIL.Image.open(io.BytesIO(request_object_content))

        # 2. Prompt de experto
        prompt = """
        Actúa como un experto en seguridad. Analiza esta imagen y detecta amenazas (armas, robos, violencia).
        Responde estrictamente en JSON:
        {
            "etiqueta": "Categoría corta",
            "descripcion": "Análisis técnico",
            "severidad": "alta, media o baja"
        }
        """

        # 3. Inferencia con el modelo EXACTO de tu lista
        # Usamos gemini-2.5-flash porque es el que tu dashboard mostró con uso
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[prompt, img]
        )
        
        # 4. Procesar respuesta
        text_response = response.text
        clean_response = text_response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("json")[-1].split("```")[0].strip()
            
        analisis_ia = json.loads(clean_response)

        # 5. Persistencia en Supabase
        resultado_final = {
            "camara_id": camara_id,
            "etiqueta": analisis_ia.get("etiqueta", "Detección"),
            "descripcion": analisis_ia.get("descripcion", "Sin detalles"),
            "severidad": analisis_ia.get("severidad", "baja"),
            "tipo": "deteccion_ia_2.5",
            "metadata": {"model": "gemini-2.5-flash", "region": "Talca-Chile"}
        }

        insert_alerta_row(resultado_final)

        return {"status": "success", "data": resultado_final}

    except Exception as e:
        print(f"Error técnico: {e}")
        # Manejo de cuota agotada (muy probable si haces muchas pruebas seguidas)
        if "429" in str(e):
            raise HTTPException(status_code=429, detail="Cuota de Google agotada. Espera 60 segundos.")
        raise HTTPException(status_code=500, detail=str(e))