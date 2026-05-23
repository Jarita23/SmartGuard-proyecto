import os
import sys
# Desactivamos el multihilo interno de FFmpeg para evitar colisiones
os.environ["OPENCV_FFMPEG_THREADS"] = "1"

import cv2
import io
import time
import json
import PIL.Image
import threading
import requests
import asyncio
import math
from pathlib import Path

# ==========================================
# 🔐 CARGA BLINDADA DE VARIABLES DE ENTORNO
# ==========================================
from dotenv import load_dotenv

# Forzamos la ruta absoluta: buscamos el .env exactamente al lado de server.py
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

print(f"🔍 [SISTEMA] Archivo .env forzado desde: {ENV_PATH}")
print(f"🔑 Verificando SUPABASE_URL: {'OK (Conectado)' if os.getenv('SUPABASE_URL') else 'ERROR (No encontrado)'}")

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from ultralytics import YOLO

# ==========================================
# 🔌 INICIALIZACIÓN DE SERVICIOS (MODO DIOS)
# ==========================================
# Inicialización de Gemini
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# 🚨 Ignoramos el Singleton local y creamos un Cliente Maestro puro
from supabase import create_client

SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")
SUPABASE_MASTER_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_MASTER_KEY:
    print("❌ ERROR FATAL: No encuentro SUPABASE_SERVICE_ROLE_KEY en el archivo .env")
    print("Por favor, asegúrate de haberla pegado correctamente.")
    sys.exit(1)

# Al inicializar con la llave Service Role, ignoramos todas las políticas RLS
supabase = create_client(SUPABASE_URL_ENV, SUPABASE_MASTER_KEY)

app = FastAPI(
    title="SmartGuard AI - Human in the Loop Engine",
    description="Sistema de análisis biomecánico con validación humana forense - v3.5",
    version="3.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 📱 CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8848721200:AAGbvjLg51ng6CLxpatz7pnAbvteHg3JN1k"
TELEGRAM_CHAT_ID = "-1003790783396"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ==========================================
# 📡 VARIABLES GLOBALES Y CONTROL DE ESTADO
# ==========================================
model_obj = YOLO('yolov8n.pt')      
model_pose = YOLO('yolov8n-pose.pt') 

ESTANTE_ROI = [450, 100, 630, 450] 
RTSP_URL = "rtsp://admin:L2BCD08A@192.168.1.22:554/cam/realmonitor?channel=1&subtype=0"

ultimo_frame_procesado = None
lock_frame = threading.Lock()
sistema_activo = True 
ultimo_disparo = 0.0  

class CamaraAsincrona:
    def __init__(self, src):
        self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        self.ret, self.frame = self.cap.read()
        self.corriendo = True
        self.hilo = threading.Thread(target=self._actualizar, daemon=True)
        self.hilo.start()

    def _actualizar(self):
        while self.corriendo:
            try:
                ret, frame = self.cap.read()
                if ret:
                    self.ret = ret
                    self.frame = frame
            except Exception:
                break

    def read(self):
        return self.ret, self.frame.copy() if self.ret else None

    def release(self):
        self.corriendo = False
        if self.hilo.is_alive():
            self.hilo.join(timeout=1.0)
        self.cap.release()

# ==========================================
# ☁️ FLUJO PIPELINE: REGISTRO, STORAGE Y TELEGRAM
# ==========================================
def procesar_y_despachar_sospecha(frame_evidencia):
    global ultimo_disparo
    print("🚨 [EDGE] Despachando sospecha biométrica local...")
    try:
        # 1. Convertir frame a bytes
        ret, buffer = cv2.imencode('.jpg', frame_evidencia)
        if not ret: return
        imagen_bytes = buffer.tobytes()

        # 2. Subir de forma inmediata al Bucket de Supabase Storage
        nombre_archivo = f"evidencia_{int(time.time())}.jpg"
        bucket_name = "evidencia_biometrica"
        
        # Guardamos en storage de Supabase
        supabase.storage.from_(bucket_name).upload(nombre_archivo, imagen_bytes, {"content-type": "image/jpeg"})
        imagen_url = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo)
        
        # 3. Insertar fila inicial en Supabase con estado 'pendiente'
        alerta_data = {
            "camara_id": 1,
            "etiqueta": "SOSPECHA DE OCULTAMIENTO",
            "descripcion": "Análisis biométrico local detectó movimiento anómalo de manos.",
            "severidad": "media",
            "tipo": "biometria_ia_3.5",
            "estado_validacion": "pendiente",
            "imagen_url": imagen_url,
            "metadata": {"archivo_storage": nombre_archivo}
        }
        
        # Guardamos en la base de datos usando el Singleton de Supabase
        res_db = supabase.table("alertas").insert(alerta_data).execute()
        alerta_id = res_db.data[0]['id'] if res_db.data else int(time.time())

        # 4. Construir Mensaje de Telegram con Botones Interactivos (Inline Keyboard)
        payload_telegram = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"⚠️ **SMARTGUARD LIVE** ⚠️\n\n📌 **Evento:** Alerta Biométrica Local\n🆔 **ID Registro:** {alerta_id}\n\nEl sistema Edge detectó que las manos del sujeto interactuaron con el área de riesgo. Valide la intencionalidad:",
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [
                        {"text": "🔴 Riesgo Alto (Robo)", "callback_data": f"alto:{alerta_id}:{nombre_archivo}"},
                        {"text": "🟢 Falsa Alarma", "callback_data": f"falsa:{alerta_id}:{nombre_archivo}"}
                    ]
                ]
            })
        }
        
        url_photo = f"{TELEGRAM_API_URL}/sendPhoto"
        res_tg = requests.post(url_photo, data=payload_telegram, files={'photo': ('evidencia.jpg', imagen_bytes)})
        
        if res_tg.status_code == 200:
            tg_data = res_tg.json()
            msg_id = tg_data['result']['message_id']
            # Guardamos el ID del mensaje de Telegram para poder editarlo después
            supabase.table("alertas").update({"telegram_message_id": msg_id}).eq("id", alerta_id).execute()
            print(f"📡 Alerta enviada a Telegram. Message ID registrado: {msg_id}")

    except Exception as e:
        print(f"❌ [BACKEND] Error al despachar sospecha: {e}")

# ==========================================
# 🧠 CAPA CLOUD FORENSE (GEMINI BAJO DEMANDA)
# ==========================================
def ejecutar_perfilamiento_forense(alerta_id, nombre_archivo):
    print(f"🧠 [CLOUD] Activando Gemini para análisis forense del registro {alerta_id}...")
    try:
        # Descargamos los bytes guardados desde el bucket de Supabase
        imagen_bytes = supabase.storage.from_("evidencia_biometrica").download(nombre_archivo)
        img = PIL.Image.open(io.BytesIO(imagen_bytes))

        prompt = """
        Actúa como un perfilador forense de seguridad para supermercados. 
        Se ha confirmado un hurto en esta imagen capturada por SmartGuard.
        Tu labor es generar una descripción física estricta y corta del sospechoso para entregar a las autoridades.
        
        CONCENTRATE EXCLUSIVAMENTE EN:
        - Tipo y color de prendas superiores e inferiores (ej. Polerón negro con capucha, jeans azules).
        - Accesorios visibles (gorros, mascarillas, mochilas, bolsos).
        
        Responde estrictamente en un máximo de 15 palabras. Ve directo al grano sin introducciones.
        """
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        descripcion_forense = response.text.strip()
        
        # Actualizamos la base de datos con la descripción de la IA y subimos severidad a alta
        supabase.table("alertas").update({
            "descripcion_ia": descripcion_forense,
            "severidad": "alta"
        }).eq("id", alerta_id).execute()
        
        print(f"✅ [CLOUD] Perfil forense guardado en Supabase: {descripcion_forense}")
        return descripcion_forense
    except Exception as e:
        print(f"❌ [CLOUD] Error en el perfilamiento forense de Gemini: {e}")
        return "Error al generar perfil forense."

# ==========================================
# 🔄 HILO TELEGRAM INTERACTIVE POLLING (HITL)
# ==========================================
def bucle_telegram_polling():
    print("📱 [TELEGRAM BOT] Escuchador interactivo de validación humana activado.")
    offset = 0
    global sistema_activo
    
    while sistema_activo:
        try:
            url = f"{TELEGRAM_API_URL}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=12)
            if res.status_code != 200:
                time.sleep(2)
                continue
                
            updates = res.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                
                # Buscamos si la actualización es un click de botón (callback_query)
                if "callback_query" in update:
                    cb_query = update["callback_query"]
                    cb_data = cb_query["data"]  # Formato: "accion:alerta_id:nombre_archivo"
                    msg_id = cb_query["message"]["message_id"]
                    chat_id = cb_query["message"]["chat"]["id"]
                    cb_query_id = cb_query["id"]
                    
                    partes = cb_data.split(":")
                    accion = partes[0]
                    alerta_id = int(partes[1])
                    nombre_archivo = partes[2]
                    
                    # Avisamos a Telegram que recibimos el click para quitar el reloj de arena del botón
                    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb_query_id})
                    
                    if accion == "alto":
                        print(f"🔴 Guardia reporta RIESGO ALTO para alerta {alerta_id}.")
                        # 1. Actualizar estado en Supabase
                        supabase.table("alertas").update({"estado_validacion": "riesgo_alto"}).eq("id", alerta_id).execute()
                        
                        # 2. Notificar cambio inmediato en Telegram
                        requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "caption": f"🔴 **HURTO CONFIRMADO** 🔴\n\nEl guardia validó la alerta {alerta_id}.\n🧠 *Procesando perfil forense con Inteligencia Artificial...*"
                        })
                        
                        # 3. Disparar Gemini en segundo plano para no bloquear el bot
                        def hilo_forense():
                            perfil = ejecutar_perfilamiento_forense(alerta_id, nombre_archivo)
                            # Edita el mensaje final en Telegram con el informe de la IA
                            requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                                "chat_id": chat_id,
                                "message_id": msg_id,
                                "caption": f"🔴 **PROCEDIMIENTO EN DESARROLLO** 🔴\n\nEl guardia confirmó el hurto.\n\n📝 **Informe Forense IA:**\n{perfil}"
                            })
                        threading.Thread(target=hilo_forense, daemon=True).start()
                        
                    elif accion == "falsa":
                        print(f"🟢 Guardia reporta FALSA ALARMA para alerta {alerta_id}. Aplicando privacidad absoluta.")
                        # 1. Actualizar estado en Supabase (Guardamos el registro de texto para estadística, pero sin datos personales)
                        supabase.table("alertas").update({
                            "estado_validacion": "falsa_alarma",
                            "imagen_url": None  # Destruimos el enlace en la base de datos
                        }).eq("id", alerta_id).execute()
                        
                        # 2. Borrar archivo físico del Storage de Supabase
                        try:
                            supabase.storage.from_("evidencia_biometrica").remove([nombre_archivo])
                            print(f"🧹 Archivo {nombre_archivo} eliminado de Supabase Storage de forma definitiva.")
                        except Exception as storage_err:
                            print(f"Advertencia al borrar del storage: {storage_err}")
                        
                        # 3. 🔥 EL PURGADO LEGAL: Eliminar por completo el mensaje y la foto del chat de Telegram
                        url_delete = f"{TELEGRAM_API_URL}/deleteMessage"
                        res_del = requests.post(url_delete, json={
                            "chat_id": chat_id,
                            "message_id": msg_id
                        })
                        
                        if res_del.status_code == 200:
                            print(f"🗑️ [PRIVACIDAD] Mensaje {msg_id} y foto eliminados de Telegram. Cero rastro legal.")
                        else:
                            print(f"⚠️ Advertencia al borrar mensaje de Telegram: {res_del.text}")
                        
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Error en bucle de polling Telegram: {e}")
            time.sleep(3)

# ==========================================
# 🛡️ MOTOR BIOMÉTRICO LOCAL (EDGE)
# ==========================================
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo
    
    cap = CamaraAsincrona(RTSP_URL)
    frame_buffer = []
    
    stock_esperado = {73: 1, "BOTELLA": 1} 
    frames_ocultamiento_confirmado = 0 
    UMBRAL_GATILLO = 15
    TIEMPO_COOLDOWN = 15.0 

    print("🛡️ SmartGuard Biométrico Preciso Activado.")

    while cap.corriendo and sistema_activo:
        success, frame = cap.read()
        if not success:
            time.sleep(0.03)
            continue

        frame = cv2.resize(frame, (640, 480))
        frame_buffer.append(frame.copy())
        if len(frame_buffer) > 30: frame_buffer.pop(0) 

        manos_en_peligro = False
        persona_presente = False

        results_pose = model_pose(frame, stream=True, verbose=False, conf=0.5)
        
        for r in results_pose:
            if r.keypoints is not None and len(r.keypoints.xy) > 0:
                kpts = r.keypoints.xy[0].cpu().numpy()
                if len(kpts) >= 13: 
                    persona_presente = True
                    l_sh, r_sh = kpts[5], kpts[6]     
                    l_wrist, r_wrist = kpts[9], kpts[10] 
                    l_hip, r_hip = kpts[11], kpts[12]    

                    distancia_hombros = abs(l_sh[0] - r_sh[0])
                    centro_x = (l_sh[0] + r_sh[0]) / 2.0
                    
                    min_x_torso = centro_x - (distancia_hombros * 0.35)
                    max_x_torso = centro_x + (distancia_hombros * 0.35)
                    min_y_torso = min(l_sh[1], r_sh[1]) + 20 
                    max_y_torso = max(l_hip[1], r_hip[1]) - 20
                    
                    radio_bolsillo = 35 
                    offset_y = 10
                    
                    bolsillo_izq_x = l_hip[0]
                    bolsillo_der_x = r_hip[0]
                    bolsillo_izq_y = l_hip[1] + offset_y
                    bolsillo_der_y = r_hip[1] + offset_y

                    if min_x_torso > 0 and min_y_torso > 0:
                        cv2.rectangle(frame, (int(min_x_torso), int(min_y_torso)), (int(max_x_torso), int(max_y_torso)), (255, 255, 255), 1)
                        cv2.circle(frame, (int(bolsillo_izq_x), int(bolsillo_izq_y)), radio_bolsillo, (0, 165, 255), 1)
                        cv2.circle(frame, (int(bolsillo_der_x), int(bolsillo_der_y)), radio_bolsillo, (0, 165, 255), 1)

                    for wrist in [l_wrist, r_wrist]:
                        wx, wy = wrist
                        if wx > 0 and wy > 0:
                            en_torso = (min_x_torso <= wx <= max_x_torso) and (min_y_torso <= wy <= max_y_torso)
                            dist_bolsillo_izq = math.hypot(wx - bolsillo_izq_x, wy - bolsillo_izq_y)
                            dist_bolsillo_der = math.hypot(wx - bolsillo_der_x, wy - bolsillo_der_y)
                            en_bolsillo = (dist_bolsillo_izq < radio_bolsillo) or (dist_bolsillo_der < radio_bolsillo)

                            if en_torso or en_bolsillo:
                                manos_en_peligro = True
                                cv2.circle(frame, (int(wx), int(wy)), 8, (0, 0, 255), -1) 
                            else:
                                cv2.circle(frame, (int(wx), int(wy)), 6, (0, 255, 0), -1) 

        obj_results = model_obj.track(frame, persist=True, conf=0.30, verbose=False)
        conteo_actual = {73: 0, "BOTELLA": 0}
        
        if obj_results[0].boxes.id is not None:
            clases_obj = obj_results[0].boxes.cls.cpu().numpy().astype(int)
            boxes_obj = obj_results[0].boxes.xyxy.cpu().numpy().astype(int)

            for box, cls in zip(boxes_obj, clases_obj):
                x1, y1, x2, y2 = box
                toca_estante = not (x2 < ESTANTE_ROI[0] or x1 > ESTANTE_ROI[2] or y2 < ESTANTE_ROI[1] or y1 > ESTANTE_ROI[3])

                if cls in [73, 67]: 
                    conteo_actual[73] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2)
                elif cls in [39, 64]: 
                    conteo_actual["BOTELLA"] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2)

        hay_faltante = (conteo_actual[73] < stock_esperado[73]) or (conteo_actual["BOTELLA"] < stock_esperado["BOTELLA"])

        if persona_presente:
            if hay_faltante and manos_en_peligro:
                frames_ocultamiento_confirmado += 1
                color_ui = (0, 0, 255)
                mensaje = "ALERTA BIOMETRICA: OCULTAMIENTO"
            elif hay_faltante and not manos_en_peligro:
                frames_ocultamiento_confirmado = 0
                color_ui = (255, 255, 0)
                mensaje = "CLIENTE SOSTENIENDO OBJETO"
            else:
                frames_ocultamiento_confirmado = 0
                color_ui = (0, 255, 0)
                mensaje = "STOCK SEGURO"
            
            if frames_ocultamiento_confirmado >= UMBRAL_GATILLO:
                tiempo_actual = time.time()
                if (tiempo_actual - ultimo_disparo) > TIEMPO_COOLDOWN:
                    print("📸 [GATILLO BIOMÉTRICO] Despachando evidencia local a Supabase y Telegram...")
                    # 📸 Captura el frame EXACTO del impacto, incluyendo la interfaz roja para el guardia
                    frame_copia = frame.copy()
                    
                    threading.Thread(target=procesar_y_despachar_sospecha, args=(frame_copia,), daemon=True).start()
                    ultimo_disparo = tiempo_actual
                    
                    print("⏳ [COOLDOWN] Congelando análisis local por 5 segundos...")
                    time.sleep(5.0)
                frames_ocultamiento_confirmado = 0
                
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2)
        else:
            frames_ocultamiento_confirmado = 0
            cv2.putText(frame, "MONITOREO PASIVO...", (10, 35), 1, 1.2, (255, 255, 255), 2)

        cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1)
        
        with lock_frame:
            ultimo_frame_procesado = frame.copy()
        time.sleep(0.01)

    cap.release()

# ==========================================
# ⚡ CONTROL DE CICLO DE VIDA DEL SERVIDOR
# ==========================================
@app.on_event("startup")
def iniciar_servicios_segundo_plano():
    # Lanzamos el motor de visión local
    threading.Thread(target=bucle_vigilancia, daemon=True).start()
    # Lanzamos el bot interactivo HITL de Telegram
    threading.Thread(target=bucle_telegram_polling, daemon=True).start()

@app.on_event("shutdown")
def apagar_sistema():
    global sistema_activo
    print("🛑 [SISTEMA] Cerrando motores y cortando energía...")
    sistema_activo = False
    os._exit(0)

# ==========================================
# 🛣️ STREAMING ENDPOINT
# ==========================================
async def generar_frames_mjpeg():
    global ultimo_frame_procesado, sistema_activo
    try:
        while sistema_activo:
            if ultimo_frame_procesado is not None:
                with lock_frame:
                    ret, buffer = cv2.imencode('.jpg', ultimo_frame_procesado)
                    if not ret: continue
                    bytes_imagen = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + bytes_imagen + b' \r\n')
            await asyncio.sleep(0.04) 
    except asyncio.CancelledError:
        pass

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generar_frames_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/")
def health_check():
    return {"status": "online"}