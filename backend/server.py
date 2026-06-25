# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN INICIAL
# ==========================================
import os
import sys
os.environ["OPENCV_FFMPEG_THREADS"] = "1"

#  BANDERA DE ULTRA BAJA LATENCIA (TCP PARA RED LOCAL DAHUA)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000"

import cv2
import io
import time
import json
import PIL.Image
import threading
import requests
import asyncio
import math
import hashlib
import re
from datetime import datetime

import numpy as np
from pathlib import Path
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any

# ==========================================
# CARGA BLINDADA DE VARIABLES DE ENTORNO
# ==========================================
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

print(f"[SISTEMA] Archivo .env forzado desde: {ENV_PATH}")

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from ultralytics import YOLO

# ==========================================
# INICIALIZACIÓN DE SERVICIOS (MODO DIOS)
# ==========================================
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

from supabase import create_client

SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")
SUPABASE_MASTER_KEY = os.getenv("SUPABASE_MASTER_KEY")

supabase = create_client(SUPABASE_URL_ENV, SUPABASE_MASTER_KEY)

ORIGINES_PERMITIDOS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app = FastAPI(
    title="SmartGuard AI - Computer Vision Autonomous Engine",
    description="Sistema biomecánico con detección autónoma de credenciales QR - v3.7",
    version="3.7.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURACIÓN DEL BOT DE TELEGRAM (CONFIGURACIÓN DE DEFENSA)
# ==========================================
TELEGRAM_TOKEN = "8848721200:AAGbvjLg51ng6CLxpatz7pnAbvteHg3JN1k"
TELEGRAM_CHAT_ID = "-1003790783396"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ==========================================
# VARIABLES GLOBALES ENTRADA Y CONTROL DE ESTADO
# ==========================================
model_obj = YOLO(str(BASE_DIR / 'models' / 'yolov8m.pt')).to('cuda')
model_pose = YOLO(str(BASE_DIR / 'models' / 'yolov8m-pose.pt')).to('cuda')

qr_detector = cv2.QRCodeDetector()

ESTANTE_ROI = [950, 320, 1250, 640]

RTSP_URL = os.getenv("RTSP_URL")

print(f"[HARDWARE] SmartGuard configurado en modo: CAMARA IP DAHUA (RTSP) -> {RTSP_URL}")

ultimo_frame_procesado = None
lock_frame = threading.Lock()
sistema_activo = True
ultimo_disparo = 0.0

modo_reposicion = False

class CamaraAsincrona:
    def __init__(self, src):
        if isinstance(src, int) or src.isdigit():
            self.cap = cv2.VideoCapture(int(src))
        else:
            self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
            
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        self.ret, self.frame = self.cap.read()
        self.corriendo = True
        self.hilo = threading.Thread(target=self._actualizar, daemon=True)
        self.hilo.start()

    def _actualizar(self):
        while self.corriendo:
            try:
                if not self.cap.grab():
                    time.sleep(0.01)
                    continue
                
                ret, frame = self.cap.retrieve()
                if ret:
                    self.ret = ret
                    self.frame = frame
            except Exception:
                break

    def read(self):
        return self.ret, self.frame.copy() if self.ret else None

# ==========================================
# FLUJO PIPELINE: REGISTRO, STORAGE Y TELEGRAM
# ==========================================
def procesar_y_despachar_sospecha(frame_evidencia):
    global ultimo_disparo
    print("[EDGE] Despachando sospecha biometrica local...")
    try:
        print("[EDGE] Paso 1: Codificando imagen...")
        ret, buffer = cv2.imencode('.jpg', frame_evidencia)
        if not ret:
            print("[EDGE] ERROR: No se pudo codificar la imagen")
            return
        imagen_bytes = buffer.tobytes()
        firma_sha256 = hashlib.sha256(imagen_bytes).hexdigest()
        nombre_archivo = f"evidencia_{int(time.time())}.jpg"
        bucket_name = "evidencia_biometrica"

        print(f"[EDGE] Paso 2: Subiendo a Supabase Storage -> {nombre_archivo}")
        upload_res = supabase.storage.from_(bucket_name).upload(
            nombre_archivo, imagen_bytes, {"content-type": "image/jpeg"}
        )
        print(f"[EDGE] Supabase upload OK: {upload_res}")

        imagen_url = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo)
        print(f"[EDGE] Paso 3: URL obtenida: {imagen_url}")

        alerta_data = {
            "camara_id": 1,
            "etiqueta": "SOSPECHA DE OCULTAMIENTO",
            "descripcion": "Analisis biometrico local detecto movimiento anomalo de manos.",
            "severidad": "media",
            "tipo": "biometria_ia_3.5",
            "estado_validacion": "pendiente",
            "imagen_url": imagen_url,
            "metadata": {
                "archivo_storage": nombre_archivo,
                "sha256_hash": firma_sha256
            }
        }

        print("[EDGE] Paso 4: Insertando en Supabase DB...")
        res_db = supabase.table("alertas").insert(alerta_data).execute()
        alerta_id = res_db.data[0]['id'] if res_db.data else int(time.time())
        print(f"[EDGE] DB OK: alerta_id={alerta_id}")

        payload_telegram = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"**SMARTGUARD LIVE** \n\n**Evento:** Alerta Biometrica Local\n**ID Registro:** {alerta_id}\n\nEl sistema Edge detecto que las manos del sujeto interactuaron con el area de riesgo. Valide la intencionalidad:",
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({
                "inline_keyboard": [[
                    {"text": "Riesgo Alto (Robo)", "callback_data": f"alto:{alerta_id}:{nombre_archivo}"},
                    {"text": "Falsa Alarma", "callback_data": f"falsa:{alerta_id}:{nombre_archivo}"}
                ]]
            })
        }

        print(f"[EDGE] Paso 5: Enviando foto a Telegram chat_id={TELEGRAM_CHAT_ID}...")
        url_photo = f"{TELEGRAM_API_URL}/sendPhoto"
        res_tg = requests.post(
            url_photo,
            data=payload_telegram,
            files={'photo': ('evidencia.jpg', imagen_bytes)}
        )
        print(f"[EDGE] Telegram respuesta: {res_tg.status_code} | {res_tg.text[:300]}")

        if res_tg.status_code == 200:
            tg_data = res_tg.json()
            msg_id = tg_data['result']['message_id']
            supabase.table("alertas").update(
                {"telegram_message_id": msg_id}
            ).eq("id", alerta_id).execute()
            print(f"[TELEGRAM] Alerta enviada. Message ID: {msg_id}")

    except Exception as e:
        import traceback
        print(f"[BACKEND] Error al despachar sospecha: {e}")
        print(traceback.format_exc())
# ==========================================
# 📐 MOTOR GEOMÉTRICO DE COLISIONES (AABB)
# ==========================================
def colision_cajas(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right > x_left and y_bottom > y_top:
        return True
    return False

# ==========================================
# FORMATO ESTRICTO TELEGRAM MARKDOWNV2
# ==========================================
def escapar_mdv2(texto: str) -> str:
    if not texto:
        return "N/D"
    caracteres_peligrosos = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(caracteres_peligrosos)}])', r'\\\1', str(texto))

def construir_informe_forense_mdv2(datos_ia: dict, camara_nombre: str) -> str:
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fh_esc = escapar_mdv2(fecha_hora)
    cam_esc = escapar_mdv2(camara_nombre)
    gen_esc = escapar_mdv2(datos_ia.get("genero", "N/D"))
    edad_esc = escapar_mdv2(datos_ia.get("edad", "N/D"))
    rostro_esc = escapar_mdv2(datos_ia.get("rostro", "N/D"))
    psup_esc = escapar_mdv2(datos_ia.get("prenda_superior", "N/D"))
    pinf_esc = escapar_mdv2(datos_ia.get("prenda_inferior", "N/D"))
    acc_esc = escapar_mdv2(datos_ia.get("accesorios", "Ninguno visible"))
    evi_esc = escapar_mdv2(datos_ia.get("evidencia", "Ocultamiento detectado"))
    conf_esc = escapar_mdv2(str(datos_ia.get("confianza", "96")))

    mensaje = (
        rf"🔴 *\[ALERTA SMARTGUARD\]*\n"
        rf"_PROCEDIMIENTO EN DESARROLLO_\n"
        rf"El guardia confirmó el hurto en sala\.\n"
        rf"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
        f"📅 *Fecha/Hora:* `{fh_esc}`\n"
        f"🎥 *Origen:* `{cam_esc}`\n"
        rf"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
        f"🕵️‍♂️ *INFORME FORENSE IA*\n"
        rf"• *Género/Edad:* {gen_esc} \| {edad_esc}\n"
        f"• *Rostro:* {rostro_esc}\n"
        f"• *Prenda Superior:* {psup_esc}\n"
        f"• *Prenda Inferior:* {pinf_esc}\n"
        f"• *Accesorios/Objetos:* {acc_esc}\n"
        f"📦 *Evidencia:* {evi_esc}\n"
        f"🤖 *Métrica IA:* ||Confianza del modelo: {conf_esc}%||"
    )
    return mensaje

# ==========================================
# CAPA CLOUD FORENSE (GEMINI BAJO DEMANDA)
# ==========================================
def ejecutar_perfilamiento_forense(alerta_id, nombre_archivo):
    print(f"[CLOUD] Activando Gemini para analisis forense estructurado del registro {alerta_id}...") 
    try:                                          
        imagen_bytes = supabase.storage.from_("evidencia_biometrica").download(nombre_archivo) 
        img = PIL.Image.open(io.BytesIO(imagen_bytes)) 

        prompt = """
        Actúa como un perfilador forense de seguridad para supermercados. 
        Analiza esta imagen de un hurto detectado por cámaras de seguridad.
        
        Devuelve ÚNICAMENTE un objeto JSON válido con las siguientes claves exactas, siendo breve y directo en cada valor (máximo 4 palabras por clave):
        {
            "genero": "Ej: Masculino",
            "edad": "Ej: 20-30 años",
            "rostro": "Ej: Gafas oscuras, barba",
            "prenda_superior": "Ej: Chaqueta negra reflectante",
            "prenda_inferior": "Ej: Pantalón de mezclilla",
            "accesorios": "Ej: Mochila negra, gorro gris",
            "evidencia": "Ej: Botella en mano derecha",
            "confianza": "95"
        }
        No incluyas formato markdown de código (como ```json) en tu respuesta, solo el JSON puro.
        """                                        
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img]) 
        
        respuesta_cruda = response.text.strip().replace('```json', '').replace('```', '')
        datos_ia = json.loads(respuesta_cruda)
        
        informe_formateado = construir_informe_forense_mdv2(datos_ia, "CAM-01 / Pasillo Principal")
        
        resumen_web = (
            f"👤 {datos_ia.get('genero')} | {datos_ia.get('edad')}\n"
            f"👕 {datos_ia.get('prenda_superior')} | 👖 {datos_ia.get('prenda_inferior')}\n"
            f"🎒 Accesorios: {datos_ia.get('accesorios')}\n"
            f"🤖 Confianza IA: {datos_ia.get('confianza')}%"
        )

        supabase.table("alertas").update({    
            "descripcion_ia": resumen_web, 
            "severidad": "alta"               
        }).eq("id", alerta_id).execute()      
        
        print(f"[CLOUD] Perfil forense MDV2 estructurado con éxito.") 
        return informe_formateado            
    except Exception as e:                    
        print(f"[CLOUD] Error en el perfilamiento forense JSON de Gemini: {e}") 
        return r"🔴 *ERROR FORENSE* \nNo se pudo estructurar la lectura biométrica\."

# ==========================================
# HILO TELEGRAM INTERACTIVE POLLING (HITL)
# ==========================================
def bucle_telegram_polling():
    print("[TELEGRAM BOT] Escuchador interactivo de validacion humana activado.")
    global sistema_activo
    
    # Paso 1: Limpiar cualquier sesion anterior antes de empezar
    print("[TELEGRAM] Limpiando sesiones anteriores...")
    for intento in range(5):
        try:
            r = requests.get(
                f"{TELEGRAM_API_URL}/getUpdates",
                params={"offset": -1, "limit": 1, "timeout": 0},
                timeout=5
            )
            if r.status_code == 200:
                print("[TELEGRAM] Sesion limpia. Iniciando polling.")
                break
            elif r.status_code == 409:
                print(f"[TELEGRAM] Conflicto detectado, esperando {(intento+1)*3}s...")
                time.sleep((intento + 1) * 3)
        except Exception:
            time.sleep(2)

    offset = 0
    while sistema_activo:
        try:
            res = requests.get(
                f"{TELEGRAM_API_URL}/getUpdates",
                params={"offset": offset, "limit": 10, "timeout": 5},
                timeout=8
            )

            if res.status_code == 409:
                print("[TELEGRAM] Conflicto 409 detectado. Esperando 10s y reintentando...")
                time.sleep(10)
                continue

            if res.status_code != 200:
                print(f"⚠️ [TELEGRAM] Error {res.status_code}: {res.text[:100]}")
                time.sleep(3)
                continue

            updates = res.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1

                if "callback_query" not in update:
                    continue

                cb_query    = update["callback_query"]
                cb_data     = cb_query["data"]
                msg_id      = cb_query["message"]["message_id"]
                chat_id     = cb_query["message"]["chat"]["id"]
                cb_query_id = cb_query["id"]

                print(f"🖱️ [TELEGRAM] Botón presionado: {cb_data}")

                partes         = cb_data.split(":")
                accion         = partes[0]
                alerta_id      = partes[1]
                nombre_archivo = partes[2]

                requests.post(
                    f"{TELEGRAM_API_URL}/answerCallbackQuery",
                    json={"callback_query_id": cb_query_id}
                )

                if accion == "alto":
                    print(f"[TELEGRAM] RIESGO ALTO para alerta {alerta_id}.")
                    supabase.table("alertas").update(
                        {"estado_validacion": "riesgo_alto"}
                    ).eq("id", alerta_id).execute()

                    requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "caption": f"*HURTO CONFIRMADO*\n\nEl guardia validó la alerta {alerta_id}.\n_Procesando perfil forense con IA..._",
                        "parse_mode": "Markdown"
                    })

                    def hilo_forense():
                        perfil = ejecutar_perfilamiento_forense(alerta_id, nombre_archivo)
                        requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "caption": perfil,
                            "parse_mode": "MarkdownV2"
                        })
                    threading.Thread(target=hilo_forense, daemon=True).start()

                elif accion == "falsa":
                    print(f"[TELEGRAM] FALSA ALARMA para alerta {alerta_id}.")
                    supabase.table("alertas").update({
                        "estado_validacion": "falsa_alarma",
                        "imagen_url": None
                    }).eq("id", alerta_id).execute()

                    try:
                        supabase.storage.from_("evidencia_biometrica").remove([nombre_archivo])
                        print(f"[STORAGE] {nombre_archivo} eliminado.")
                    except Exception as se:
                        print(f"[STORAGE] Error: {se}")

                    del_res = requests.post(
                        f"{TELEGRAM_API_URL}/deleteMessage",
                        json={"chat_id": chat_id, "message_id": msg_id}
                    )
                    if del_res.status_code == 200:
                        print("[PRIVACIDAD] Mensaje eliminado de Telegram.")

            time.sleep(0.3)

        except Exception as e:
            print(f"❌ [TELEGRAM] Error: {e}")
            time.sleep(3)

# ==========================================
# MOTOR BIOMÉTRICO LOCAL (EDGE) - v7.1
# ==========================================
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo, modo_reposicion

    cap = CamaraAsincrona(RTSP_URL)

    INF_W, INF_H   = 640, 360
    DISP_W, DISP_H = 1280, 720
    ESCALA_X = DISP_W / INF_W   
    ESCALA_Y = DISP_H / INF_H

    frames_ocultamiento_confirmado = 0
    UMBRAL_GATILLO          = 15
    TIEMPO_COOLDOWN         = 15.0
    FRAME_ACTUAL            = 0
    FRAMES_DE_CALENTAMIENTO = 60

    frames_desde_ultimo_qr = 999
    UMBRAL_MEMORIA_QR       = 90

    memoria_toco_estante = False
    frames_sin_faltante  = 0
    UMBRAL_PERDON        = 20

    CONFIANZA_MIN_MUNECA = 0.4
    UMBRAL_LADO = 0.38

    stock_estante_congelado = 0
    frames_para_nuevo_stock = 0

    frames_analisis_activo_sin_resolucion = 0
    UMBRAL_GATILLO_CIEGO = 90

    fuente    = cv2.FONT_HERSHEY_DUPLEX
    suavizado = cv2.LINE_AA

    F_GRANDE  = 0.85
    F_MEDIO   = 0.65
    F_PEQUEÑO = 0.50
    GROSOR_TITULO = 2
    GROSOR_HUD    = 1

    Y_LINEA_1 = 32
    Y_LINEA_2 = 62
    X_TEXTO   = 20

    ROI_INF = [
        int(ESTANTE_ROI[0] / ESCALA_X),
        int(ESTANTE_ROI[1] / ESCALA_Y),
        int(ESTANTE_ROI[2] / ESCALA_X),
        int(ESTANTE_ROI[3] / ESCALA_Y),
    ]

    print("[SISTEMA] SmartGuard Biometrico v7.1 Activado.")
    print("[SISTEMA] GPU activa | Torso adaptativo corregido | Filtro COCO limpio | UI HD.")

    while cap.corriendo and sistema_activo:

        success, frame = cap.read()
        if not success:
            time.sleep(0.03)
            continue

        if frame.shape[1] != DISP_W or frame.shape[0] != DISP_H:
            frame = cv2.resize(frame, (DISP_W, DISP_H))
            
        frame_inf = cv2.resize(frame, (INF_W,  INF_H))
        FRAME_ACTUAL += 1

        if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO:
            cv2.putText(frame, "CALIBRANDO SENSORES...", (X_TEXTO, Y_LINEA_1),
                        fuente, F_GRANDE, (0, 255, 255), GROSOR_TITULO, suavizado)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.03)
            continue

        try:
            data_qr, _, _ = qr_detector.detectAndDecode(frame_inf)
        except Exception:
            data_qr = ""

        if data_qr == "STAFF_SMARTGUARD":
            frames_desde_ultimo_qr = 0
            modo_reposicion = True
        else:
            frames_desde_ultimo_qr += 1
            if frames_desde_ultimo_qr > UMBRAL_MEMORIA_QR:
                modo_reposicion = False

        if modo_reposicion:
            frames_ocultamiento_confirmado = 0
            frames_analisis_activo_sin_resolucion = 0
            memoria_toco_estante           = False
            frames_sin_faltante            = 0
            stock_estante_congelado        = 0
            cv2.putText(frame, "MODO REPOSICION: VIGILANCIA PASIVA",
                        (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 140, 255), GROSOR_TITULO, suavizado)
            cv2.rectangle(frame,
                        (ESTANTE_ROI[0], ESTANTE_ROI[1]),
                        (ESTANTE_ROI[2], ESTANTE_ROI[3]), (0, 140, 255), 1)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.01)
            continue

        obj_results = model_obj.track(frame_inf, persist=True, conf=0.15, classes=[0, 39], verbose=False)

        botellas_en_estante   = 0
        botella_visible_fuera = False
        cliente_en_zona       = False
        persona_en_camara     = False

        if obj_results[0].boxes.id is not None:
            clases_obj = obj_results[0].boxes.cls.cpu().numpy().astype(int)
            boxes_obj  = obj_results[0].boxes.xyxy.cpu().numpy()

            for box_inf_raw, cls in zip(boxes_obj, clases_obj):
                xi1, yi1, xi2, yi2 = box_inf_raw
                xd1 = int(xi1 * ESCALA_X)
                yd1 = int(yi1 * ESCALA_Y)
                xd2 = int(xi2 * ESCALA_X)
                yd2 = int(yi2 * ESCALA_Y)
                box_inf_int = [int(xi1), int(yi1), int(xi2), int(yi2)]

                if cls == 0:
                    persona_en_camara = True
                    if colision_cajas(box_inf_int, ROI_INF):
                        cliente_en_zona = True
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (0, 255, 255), 2)
                        cv2.putText(frame, "CLIENTE EN ZONA",
                                    (xd1, max(20, yd1 - 10)), fuente, F_PEQUEÑO, (0, 255, 255), GROSOR_HUD, suavizado)
                    else:
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (0, 150, 150), 1)

                elif cls == 39:
                    if colision_cajas(box_inf_int, ROI_INF):
                        botellas_en_estante += 1
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (0, 255, 0), 2)
                    else:
                        botella_visible_fuera = True
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (255, 165, 0), 2)

        if not persona_en_camara:
            memoria_toco_estante = False
            frames_sin_faltante  = 0

        if botellas_en_estante > stock_estante_congelado:
            frames_para_nuevo_stock += 1
            if frames_para_nuevo_stock >= 10:
                stock_estante_congelado = botellas_en_estante
                frames_para_nuevo_stock = 0
                print(f"[STOCK] Nuevo maximo confirmed en estante: {stock_estante_congelado}")
        else:
            frames_para_nuevo_stock = 0

        faltante_en_estante = (botellas_en_estante < stock_estante_congelado)

        if faltante_en_estante and cliente_en_zona:
            memoria_toco_estante = True

        if not faltante_en_estante and memoria_toco_estante:
            frames_sin_faltante += 1
            if frames_sin_faltante >= UMBRAL_PERDON:
                memoria_toco_estante = False
                frames_sin_faltante  = 0
                print("[SISTEMA] Memoria borrada: botella devuelta al estante.")
        else:
            frames_sin_faltante = 0

        manos_en_peligro    = False
        esqueleto_confiable = False
        esta_de_lado        = False

        if not faltante_en_estante and not memoria_toco_estante:
            frames_analisis_activo_sin_resolucion = 0
            if frames_ocultamiento_confirmado > 0:
                frames_ocultamiento_confirmado = max(0, frames_ocultamiento_confirmado - 2)
            cv2.putText(frame, "MONITOREO PASIVO...",
                        (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (255, 255, 255), GROSOR_TITULO, suavizado)
            cv2.putText(frame, f"STOCK BASE: {stock_estante_congelado} | EN REPISA: {botellas_en_estante}",
                        (X_TEXTO, Y_LINEA_2), fuente, F_MEDIO, (0, 255, 0), GROSOR_HUD, suavizado)

        else:
            results_pose = model_pose(frame_inf, stream=False, verbose=False, conf=0.5)

            for r in results_pose:
                if r.keypoints is None or len(r.keypoints.xy) == 0:
                    continue

                # REFACTORIZACIÓN MULTIHILO: Iteramos por cada individuo detectado
                num_personas = len(r.keypoints.xy)
                for p_idx in range(num_personas):
                    kpts      = r.keypoints.xy[p_idx].cpu().numpy()
                    kpts_conf = r.keypoints.conf[p_idx].cpu().numpy()

                    if len(kpts) < 13:
                        continue

                    muneca_izq_ok       = kpts_conf[9]  > CONFIANZA_MIN_MUNECA
                    muneca_der_ok       = kpts_conf[10] > CONFIANZA_MIN_MUNECA
                    
                    if muneca_izq_ok or muneca_der_ok:
                        esqueleto_confiable = True

                    l_sh,    r_sh    = kpts[5],  kpts[6]
                    l_wrist, r_wrist = kpts[9],  kpts[10]
                    l_hip,   r_hip   = kpts[11], kpts[12]

                    distancia_hombros  = abs(l_sh[0] - r_sh[0])
                    dist_hombro_cadera = abs(min(l_sh[1], r_sh[1]) - max(l_hip[1], r_hip[1]))
                    centro_x           = (l_sh[0] + r_sh[0]) / 2.0
                    offset_y           = 5
                    radio_bolsillo     = 18

                    es_lateral = distancia_hombros < (dist_hombro_cadera * UMBRAL_LADO)

                    if es_lateral:
                        esta_de_lado = True
                        conf_izq = kpts_conf[5]
                        conf_der = kpts_conf[6]

                        ancho_pecho = dist_hombro_cadera * 0.45

                        if conf_izq > conf_der:
                            hombro_visible_x = l_sh[0]
                            min_x_torso = hombro_visible_x - (ancho_pecho * 1.3)
                            max_x_torso = hombro_visible_x + (ancho_pecho * 0.2)
                        else:
                            hombro_visible_x = r_sh[0]
                            min_x_torso = hombro_visible_x - (ancho_pecho * 0.2)
                            max_x_torso = hombro_visible_x + (ancho_pecho * 1.3)

                        min_y_torso = min(l_sh[1], r_sh[1]) + (dist_hombro_cadera * 0.05)
                        max_y_torso = max(l_hip[1], r_hip[1]) - (dist_hombro_cadera * 0.15)

                        bolsillo_izq = (l_hip[0], l_hip[1] + offset_y)
                        bolsillo_der = (r_hip[0], r_hip[1] + offset_y)

                        cv2.putText(frame, "MODO LATERAL",
                                    (DISP_W - 200, Y_LINEA_1), fuente, F_MEDIO, (255, 100, 0), GROSOR_HUD, suavizado)

                    else:
                        min_x_torso = centro_x - (distancia_hombros * 0.35)
                        max_x_torso = centro_x + (distancia_hombros * 0.35)
                        min_y_torso = min(l_sh[1], r_sh[1]) + (dist_hombro_cadera * 0.4)
                        max_y_torso = max(l_hip[1], r_hip[1]) - 10
                        bolsillo_izq = (l_hip[0], l_hip[1] + offset_y)
                        bolsillo_der = (r_hip[0], r_hip[1] + offset_y)

                    if min_x_torso > 0 and min_y_torso > 0:
                        cv2.rectangle(frame,
                                    (int(min_x_torso * ESCALA_X), int(min_y_torso * ESCALA_Y)),
                                    (int(max_x_torso * ESCALA_X), int(max_y_torso * ESCALA_Y)),
                                    (255, 255, 255), 1)
                        cv2.circle(frame,
                                (int(bolsillo_izq[0] * ESCALA_X), int(bolsillo_izq[1] * ESCALA_Y)),
                                int(radio_bolsillo * ESCALA_X), (0, 165, 255), 1)
                        cv2.circle(frame,
                                (int(bolsillo_der[0] * ESCALA_X), int(bolsillo_der[1] * ESCALA_Y)),
                                int(radio_bolsillo * ESCALA_X), (0, 165, 255), 1)

                    for wrist, wrist_ok in [(l_wrist, muneca_izq_ok), (r_wrist, muneca_der_ok)]:
                        wx, wy = wrist

                        if wx <= 0 or wy <= 0 or not wrist_ok:
                            continue

                        en_estante  = colision_cajas([wx-15, wy-15, wx+15, wy+15], ROI_INF)
                        en_torso    = (min_x_torso <= wx <= max_x_torso and
                                    min_y_torso <= wy <= max_y_torso)
                        en_bolsillo = (math.hypot(wx - bolsillo_izq[0], wy - bolsillo_izq[1]) < radio_bolsillo or
                                    math.hypot(wx - bolsillo_der[0], wy - bolsillo_der[1]) < radio_bolsillo)

                        wx_d = int(wx * ESCALA_X)
                        wy_d = int(wy * ESCALA_Y)

                        if en_estante:
                            memoria_toco_estante = True
                            frames_sin_faltante  = 0
                            cv2.circle(frame, (wx_d, wy_d), 8, (255, 0, 255), -1)

                        elif en_torso or en_bolsillo:
                            if memoria_toco_estante and faltante_en_estante and not botella_visible_fuera:
                                manos_en_peligro = True
                                cv2.circle(frame, (wx_d, wy_d), 8, (0, 0, 255), -1)
                            else:
                                cv2.circle(frame, (wx_d, wy_d), 6, (255, 255, 0), -1)

                        else:
                            cv2.circle(frame, (wx_d, wy_d), 6, (0, 255, 0), -1)

            if manos_en_peligro:
                frames_ocultamiento_confirmado += 1
                frames_analisis_activo_sin_resolucion = 0
                cv2.putText(frame,
                            f"ALERTA HURTO ({frames_ocultamiento_confirmado}/{UMBRAL_GATILLO})",
                            (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 0, 255), GROSOR_TITULO, suavizado)

            else:
                frames_ocultamiento_confirmado = max(0, frames_ocultamiento_confirmado - 2)

                if faltante_en_estante and not botella_visible_fuera and memoria_toco_estante:
                    frames_analisis_activo_sin_resolucion += 1
                    cv2.putText(frame, f"ANALISIS CIEGO: BUSCANDO MANOS ({frames_analisis_activo_sin_resolucion}/{UMBRAL_GATILLO_CIEGO})",
                                (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 165, 255), GROSOR_HUD, suavizado)
                    
                    if frames_analisis_activo_sin_resolucion >= UMBRAL_GATILLO_CIEGO:
                        print("[GATILLO CIEGO] Tiempo limite alcanzado de espaldas al estante. Forzando alerta.")
                        frames_ocultamiento_confirmado = UMBRAL_GATILLO  
                        frames_analisis_activo_sin_resolucion = 0
                
                else:
                    frames_analisis_activo_sin_resolucion = 0

                    if not esqueleto_confiable:
                        cv2.putText(frame, "ESQUELETO PARCIAL: BARRA CONGELADA",
                                    (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 100, 255), GROSOR_HUD, suavizado)
                    elif faltante_en_estante and botella_visible_fuera:
                        cv2.putText(frame, "CLIENTE SOSTIENE PRODUCTO (SEGURO)",
                                    (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 255, 255), GROSOR_HUD, suavizado)
                    elif memoria_toco_estante:
                        cv2.putText(frame, "SEGUIMIENTO BIOMETRICO ACTIVO",
                                    (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 165, 255), GROSOR_HUD, suavizado)
                    else:
                        cv2.putText(frame, "ZONA BLOQUEADA (OCLUSION)",
                                    (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 165, 255), GROSOR_HUD, suavizado)

            cv2.putText(frame,
                        f"STOCK: {stock_estante_congelado} | REPISA: {botellas_en_estante} | "
                        f"FUERA: {botella_visible_fuera} | SKEL: {esqueleto_confiable} | "
                        f"LADO: {esta_de_lado}",
                        (X_TEXTO, Y_LINEA_2), fuente, F_MEDIO, (180, 180, 180), GROSOR_HUD, suavizado)

        if frames_ocultamiento_confirmado >= UMBRAL_GATILLO:
            if (time.time() - ultimo_disparo) > TIEMPO_COOLDOWN:
                print("[GATILLO] Condicion cumplida. Despachando evidencia...")
                threading.Thread(
                    target=procesar_y_despachar_sospecha,
                    args=(frame.copy(),),
                    daemon=True
                ).start()
                ultimo_disparo = time.time()
            frames_ocultamiento_confirmado = 0

        cv2.rectangle(frame,
                    (ESTANTE_ROI[0], ESTANTE_ROI[1]),
                    (ESTANTE_ROI[2], ESTANTE_ROI[3]),
                    (255, 255, 0), 1)

        with lock_frame:
            ultimo_frame_procesado = frame.copy()
        time.sleep(0.001)

    cap.release()

# ==========================================
# CONTROL DE CICLO DE VIDA DEL SERVIDOR
# ==========================================

@app.post("/api/alertas/{alerta_id}/confirmar")
def confirmar_alerta(alerta_id: str):
    try:
        # Obtener nombre del archivo
        res = supabase.table("alertas").select("metadata").eq("id", alerta_id).execute()
        nombre_archivo = res.data[0]['metadata']['archivo_storage']
        
        supabase.table("alertas").update({"estado_validacion": "riesgo_alto"}).eq("id", alerta_id).execute()
        
        # Ejecutar perfil forense en hilo separado
        def hilo():
            ejecutar_perfilamiento_forense(alerta_id, nombre_archivo)
        threading.Thread(target=hilo, daemon=True).start()
        
        return {"status": "ok", "mensaje": "Alerta confirmada como robo"}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

@app.post("/api/alertas/{alerta_id}/descartar")
def descartar_alerta(alerta_id: str):
    try:
        res = supabase.table("alertas").select("metadata").eq("id", alerta_id).execute()
        nombre_archivo = res.data[0]['metadata']['archivo_storage']
        
        # Borrar de Supabase Storage
        supabase.storage.from_("evidencia_biometrica").remove([nombre_archivo])
        
        # Borrar registro de la BD
        supabase.table("alertas").update({
            "estado_validacion": "falsa_alarma",
            "imagen_url": None
        }).eq("id", alerta_id).execute()
        
        return {"status": "ok", "mensaje": "Alerta descartada y foto eliminada"}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}


@app.on_event("startup")
def iniciar_servicios_segundo_plano():
    threading.Thread(target=bucle_vigilancia, daemon=True).start()
    threading.Thread(target=bucle_telegram_polling, daemon=True).start()

@app.on_event("shutdown")
def apagar_sistema():
    global sistema_activo
    print("[SISTEMA] Cerrando motores y cortando energia...")
    sistema_activo = False
    os._exit(0)

# ==========================================
# ENDPOINTS ADICIONALES LOGÍSTICOS
# ==========================================
@app.post("/api/reposicion/toggle")
def toggle_modo_reposicion():                 
    global modo_reposicion
    modo_reposicion = not modo_reposicion
    return {"status": "success", "modo_reposicion_activo": modo_reposicion}

@app.get("/api/reposicion/status")
def obtener_estado_reposicion():              
    global modo_reposicion                    
    return {"modo_reposicion_activo": modo_reposicion}

# ==========================================
# STREAMING ENDPOINT
# ==========================================
async def generar_frames_mjpeg():
    global ultimo_frame_procesado, sistema_activo 
    try:
        while sistema_activo:
            frame_a_enviar = None
            
            with lock_frame:
                if ultimo_frame_procesado is not None:
                    frame_a_enviar = ultimo_frame_procesado.copy()
            
            if frame_a_enviar is None:
                frame_a_enviar = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame_a_enviar, "Buscando senal de camara...", (100, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame_a_enviar, "Por favor espere.", (220, 280),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            ret, buffer = cv2.imencode('.jpg', frame_a_enviar)
            if ret:
                bytes_imagen = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + bytes_imagen + b'\r\n')
            await asyncio.sleep(0.04)
    except asyncio.CancelledError:
        pass

@app.get("/video_feed")
def video_feed():                             
    return StreamingResponse(generar_frames_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/")
def health_check():                           
    return {"status": "online"}