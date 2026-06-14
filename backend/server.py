# Importación de módulos del sistema operativo y de ejecución
import os
import sys
# Desactivamos el multihilo interno de FFmpeg para evitar colisiones gráficos
os.environ["OPENCV_FFMPEG_THREADS"] = "1"

# Importación de librerías esenciales para visión, manejo de datos y concurrencia
import cv2            # OpenCV para procesamiento de imágenes y lectura de video
import io             # Para manejo de flujos de bytes en memoria (imágenes)
import time           # Para control de tiempos, cooldowns y timestamps
import json           # Para estructurar los payloads que se envían a Telegram
import PIL.Image      # Pillow para procesar la imagen antes de enviarla a Gemini
import threading      # Para ejecutar la cámara, vigilancia y Telegram en paralelo
import requests       # Para hacer peticiones HTTP a la API de Telegram
import asyncio        # Para el endpoint de streaming de video asíncrono
import math           # Para cálculos matemáticos (ej. calcular distancias biométricas)
import hashlib        # Para generar el hash criptográfico (SHA-256) de la evidencia

# ==========================================
# STREAMING ENDPOINT CON UX DEFENSIVA
# ==========================================
import numpy as np                            # Para crear arrays numéricos (matrices de imágenes)
from pathlib import Path                      # Para manejar rutas de archivos de forma segura
from pydantic import BaseModel, HttpUrl       # Para la validación estricta de datos
from typing import Optional, Dict, Any        # Para definir tipos de datos en los esquemas

# ==========================================
# CARGA BLINDADA DE VARIABLES DE ENTORNO
# ==========================================
from dotenv import load_dotenv                # Para cargar secretos desde el archivo .env

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Cargamos las variables de entorno, sobreescribiendo las existentes en memoria
load_dotenv(dotenv_path=ENV_PATH, override=True)

print(f"[SISTEMA] Archivo .env forzado desde: {ENV_PATH}")

# Importaciones de FastAPI (Backend) y Google GenAI/Ultralytics (Inteligencia Artificial)
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

# Obtenemos credenciales de Supabase del entorno
SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")
# [CORRECCIÓN CRÍTICA 1]: Llave maestra oculta en el .env
SUPABASE_MASTER_KEY = os.getenv("SUPABASE_MASTER_KEY") 

supabase = create_client(SUPABASE_URL_ENV, SUPABASE_MASTER_KEY)

# UPGRADE DE SEGURIDAD: Restricción de Orígenes (CORS)
# Solo el Dashboard de React y el servidor local tienen permiso de conectarse al backend
ORIGINES_PERMITIDOS = [
    "http://localhost:3000",      # Dashboard en desarrollo
    "http://127.0.0.1:3000",      # Alternativa localhost
    "http://localhost:8000",      # FastAPI mismo
    "http://localhost:5173",      # Entorno de Vite
    # "https://midashboard-produccion.com" # Se activará en la defensa final
]

# ==========================================
# AQUÍ ESTÁ LA LÍNEA QUE FALTABA
# ==========================================
# Creación de la instancia principal de la aplicación FastAPI
app = FastAPI(
    title="SmartGuard AI - Computer Vision Autonomous Engine",
    description="Sistema biomecánico con detección autónoma de credenciales QR - v3.7",
    version="3.7.0"
)

# Aplicamos el middleware de CORS para bloquear peticiones de dominios no autorizados
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción, cambia este "*" por la URL de tu frontend en Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
# [CORRECCIÓN CRÍTICA 2]: Tokens ocultos en el .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ==========================================
# VARIABLES GLOBALES Y CONTROL DE ESTADO
# ==========================================
# [CORRECCIÓN CRÍTICA 3]: Rutas apuntando a la nueva carpeta 'models'
model_obj = YOLO(str(BASE_DIR / 'models' / 'yolov8n.pt'))
model_pose = YOLO(str(BASE_DIR / 'models' / 'yolov8n-pose.pt'))

qr_detector = cv2.QRCodeDetector()

ESTANTE_ROI = [450, 100, 630, 450]

fuente_env = os.getenv("WEBCAM_INDEX", "0")

if fuente_env.isdigit():
    fuente_video = int(fuente_env)
    print("[HARDWARE] SmartGuard configurado en modo: WEBCAM INTEGRADA LOCAL.")
else:
    fuente_video = fuente_env # [MEJORA]: Lee directo del .env por si cambian la IP de Dahua
    print("[HARDWARE] SmartGuard configurado en modo: CAMARA IP DAHUA (RTSP).")

ultimo_frame_procesado = None
lock_frame = threading.Lock()
sistema_activo = True
ultimo_disparo = 0.0  

modo_reposicion = False

class CamaraAsincrona:
    def __init__(self, src):
        if isinstance(src, int):
            self.cap = cv2.VideoCapture(src)
        else:
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
                time.sleep(0.03)
            except Exception:
                break # Rompe si hay un fallo crítico de red

    def read(self):
        # Retorna una copia del frame más reciente leído por el hilo
        return self.ret, self.frame.copy() if self.ret else None

    def release(self):
        # Cierra la cámara limpiamente y mata el hilo
        self.corriendo = False
        if self.hilo.is_alive():
            self.hilo.join(timeout=1.0)
        self.cap.release()

# ==========================================
# FLUJO PIPELINE: REGISTRO, STORAGE Y TELEGRAM
# ==========================================
# Función que empaqueta la evidencia y dispara las alertas cuando el Edge detecta un robo
def procesar_y_despachar_sospecha(frame_evidencia):
    global ultimo_disparo
    print("[EDGE] Despachando sospecha biometrica local...")
    try:
        ret, buffer = cv2.imencode('.jpg', frame_evidencia)
        if not ret: return
        imagen_bytes = buffer.tobytes()

        # Generar firma sha256
        firma_sha256 = hashlib.sha256(imagen_bytes).hexdigest()

        nombre_archivo = f"evidencia_{int(time.time())}.jpg"
        bucket_name = "evidencia_biometrica"
        
        supabase.storage.from_(bucket_name).upload(nombre_archivo, imagen_bytes, {"content-type": "image/jpeg"})
        # Genera el link público para insertarlo en la DB
        imagen_url = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo)
        
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
                "sha256_hash": firma_sha256  # GUARDAMOS LA HUELLA DACTILAR EN SUPABASE
            }
        }
        
        res_db = supabase.table("alertas").insert(alerta_data).execute()
        alerta_id = res_db.data[0]['id'] if res_db.data else int(time.time())

        payload_telegram = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"**SMARTGUARD LIVE** \n\n**Evento:** Alerta Biometrica Local\n**ID Registro:** {alerta_id}\n\nEl sistema Edge detecto que las manos del sujeto interactuaron con el area de riesgo. Valide la intencionalidad:",
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [
                        {"text": "Riesgo Alto (Robo)", "callback_data": f"alto:{alerta_id}:{nombre_archivo}"},
                        {"text": "Falsa Alarma", "callback_data": f"falsa:{alerta_id}:{nombre_archivo}"}
                    ]
                ]
            })
        }
        
        # Enviar petición POST a Telegram para mandar la foto con los botones integrados
        url_photo = f"{TELEGRAM_API_URL}/sendPhoto"
        res_tg = requests.post(url_photo, data=payload_telegram, files={'photo': ('evidencia.jpg', imagen_bytes)})
        
        if res_tg.status_code == 200:
            tg_data = res_tg.json()
            # Si el envío fue exitoso, guardamos la ID del mensaje de Telegram
            msg_id = tg_data['result']['message_id']
            supabase.table("alertas").update({"telegram_message_id": msg_id}).eq("id", alerta_id).execute()
            print(f"[TELEGRAM] Alerta enviada a Telegram. Message ID registrado: {msg_id}")

    except Exception as e:
        print(f"[BACKEND] Error al despachar sospecha: {e}")

# ==========================================
# CAPA CLOUD FORENSE (GEMINI BAJO DEMANDA)
# ==========================================
# Función asincrónica que delega el perfilamiento a Gemini 2.5 SOLO si el humano confirma el robo
def ejecutar_perfilamiento_forense(alerta_id, nombre_archivo):
    print(f"[CLOUD] Activando Gemini para analisis forense del registro {alerta_id}...")
    try:
        imagen_bytes = supabase.storage.from_("evidencia_biometrica").download(nombre_archivo)
        # Convertimos los bytes en un objeto PIL compatible con la API de Google
        img = PIL.Image.open(io.BytesIO(imagen_bytes))

        # Prompt hiper-enfocado para extraer metadata policial del sujeto
        prompt = """
        Actúa como un perfilador forense de seguridad para supermercados. 
        Se ha confirmado un hurto en esta imagen capturada por SmartGuard.
        Tu labor es generar una descripción física estricta y corta del sospechoso para entregar a las autoridades.
        
        CONCENTRATE EXCLUSIVAMENTE EN:
        - Tipo y color de prendas superiores e inferiores (ej. Polerón negro con capucha, jeans azules).
        - Accesorios visibles (gorros, mascarillas, mochilas, bolsos).
        
        Responde estrictamente en un máximo de 15 palabras. Ve directo al grano sin introducciones.
        """
        # Hacemos el llamado a Gemini pasando tanto el texto como la imagen
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        descripcion_forense = response.text.strip()
        
        supabase.table("alertas").update({
            "descripcion_ia": descripcion_forense,
            "severidad": "alta"           
        }).eq("id", alerta_id).execute()
        
        print(f"[CLOUD] Perfil forense guardado en Supabase: {descripcion_forense}")
        return descripcion_forense
    except Exception as e:
        print(f"[CLOUD] Error en el perfilamiento forense de Gemini: {e}")
        return "Error al generar perfil forense."

# ==========================================
# HILO TELEGRAM INTERACTIVE POLLING (HITL)
# ==========================================
# Bucle que "escucha" las acciones que el guardia hace desde su celular en Telegram
def bucle_telegram_polling():
    print("[TELEGRAM BOT] Escuchador interactivo de validacion humana activado.")
    offset = 0
    global sistema_activo
    
    while sistema_activo:
        try:
            # Long-polling: esperamos hasta 10 segundos por actualizaciones de la API de Telegram
            url = f"{TELEGRAM_API_URL}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=12)
            if res.status_code != 200:
                time.sleep(2)
                continue
                
            updates = res.json().get("result", [])
            for update in updates:
                # Actualizamos el offset para marcar este mensaje como "leído"
                offset = update["update_id"] + 1
                
                if "callback_query" in update:
                    cb_query = update["callback_query"]
                    cb_data = cb_query["data"]
                    msg_id = cb_query["message"]["message_id"]
                    chat_id = cb_query["message"]["chat"]["id"]
                    cb_query_id = cb_query["id"]
                    
                    # Separamos los parámetros del payload inyectado en el botón
                    partes = cb_data.split(":")
                    accion = partes[0]
                    alerta_id = int(partes[1])
                    nombre_archivo = partes[2]
                    
                    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb_query_id})
                    
                    if accion == "alto":
                        print(f"[TELEGRAM] Guardia reporta RIESGO ALTO para alerta {alerta_id}.")
                        supabase.table("alertas").update({"estado_validacion": "riesgo_alto"}).eq("id", alerta_id).execute()
                        
                        requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "caption": f"**HURTO CONFIRMADO**\n\nEl guardia valido la alerta {alerta_id}.\n*Procesando perfil forense con Inteligencia Artificial...*"
                        })
                        
                        def hilo_forense():
                            perfil = ejecutar_perfilamiento_forense(alerta_id, nombre_archivo)
                            requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                                "chat_id": chat_id,
                                "message_id": msg_id,
                                "caption": f"**PROCEDIMIENTO EN DESARROLLO**\n\nEl guardia confirmo el hurto.\n\n**Informe Forense IA:**\n{perfil}"
                            })
                        threading.Thread(target=hilo_forense, daemon=True).start()
                        
                    elif accion == "falsa":
                        print(f"[TELEGRAM] Guardia reporta FALSA ALARMA para alerta {alerta_id}. Aplicando privacidad absoluta.")
                        supabase.table("alertas").update({
                            "estado_validacion": "falsa_alarma",   
                            "imagen_url": None  
                        }).eq("id", alerta_id).execute()
                        
                        try:
                            supabase.storage.from_("evidencia_biometrica").remove([nombre_archivo])
                            print(f"[STORAGE] Archivo {nombre_archivo} eliminado de Supabase Storage de forma definitiva.")
                        except Exception as storage_err:
                            print(f"[STORAGE] Advertencia al borrar del storage: {storage_err}")
                        
                        url_delete = f"{TELEGRAM_API_URL}/deleteMessage"
                        res_del = requests.post(url_delete, json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                        })
                        
                        if res_del.status_code == 200:
                            print(f"[PRIVACIDAD] Mensaje {msg_id} y foto eliminados de Telegram.")                        
                        
            time.sleep(0.5)
        except Exception as e:
            print(f"Error en bucle de polling Telegram: {e}")
            time.sleep(3)

# ==========================================
# MOTOR BIOMÉTRICO LOCAL (EDGE)
# ==========================================
# Núcleo de Computer Vision de SmartGuard
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo, modo_reposicion
    
    cap = CamaraAsincrona(fuente_video)
    frame_buffer = []
    
    stock_esperado = {73: 1, "BOTELLA": 1}
    frames_ocultamiento_confirmado = 0
    UMBRAL_GATILLO = 20
    TIEMPO_COOLDOWN = 15.0

    FRAME_ACTUAL = 0
    FRAMES_DE_CALENTAMIENTO = 60
    
    frames_desde_ultimo_qr = 999
    UMBRAL_MEMORIA_QR = 90

    print("[SISTEMA] SmartGuard Biometrico Preciso Activado.")

    while cap.corriendo and sistema_activo:
        # Extraer el frame fresco del buffer
        success, frame = cap.read()
        if not success:
            time.sleep(0.03)
            continue

        # Normalizamos la resolución para procesar más rápido con YOLO
        frame = cv2.resize(frame, (640, 480))
        
        FRAME_ACTUAL += 1
        if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO:
            cv2.putText(frame, "CALIBRANDO SENSORES OPTICOS...", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.03)
            continue

        frame_buffer.append(frame.copy())
        if len(frame_buffer) > 30: frame_buffer.pop(0) 

        # ========================================================
        # FASE EXTRA: ESCÁNER AUTÓNOMO DE CREDENCIAL QR  
        # ========================================================
        data_qr, bbox_qr, _ = qr_detector.detectAndDecode(frame)
        
        if data_qr == "STAFF_SMARTGUARD":
            frames_desde_ultimo_qr = 0
            modo_reposicion = True
            
            if bbox_qr is not None and len(bbox_qr) > 0:
                pts = bbox_qr[0].astype(int)
                for i in range(4):
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i+1)%4]), (0, 255, 0), 2)
                cv2.putText(frame, "STAFF VERIFICADO", (pts[0][0], pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            frames_desde_ultimo_qr += 1
            if frames_desde_ultimo_qr > UMBRAL_MEMORIA_QR:
                modo_reposicion = False

        # ========================================================
        # INTERRUPTOR LOGÍSTICO DE COMPORTAMIENTO
        # ========================================================
        if modo_reposicion:
            frames_ocultamiento_confirmado = 0
            color_ui = (0, 140, 255)
            mensaje = f"MODO REPOSICION: VIGILANCIA PASIVA ({max(0, (UMBRAL_MEMORIA_QR - frames_desde_ultimo_qr)//30)}s)"
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2)
            
            cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (0, 140, 255), 1)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.01)
            continue

        # --- FLUJO NORMAL DE SEGURIDAD ---
        manos_en_peligro = False
        persona_presente = False

        # Inferencia de YOLOv8 Pose (buscando esqueleto humano)
        results_pose = model_pose(frame, stream=True, verbose=False, conf=0.5)
        
        for r in results_pose:
            # Validamos si encontró articulaciones válidas
            if r.keypoints is not None and len(r.keypoints.xy) > 0:
                kpts = r.keypoints.xy[0].cpu().numpy()
                if len(kpts) >= 13:
                    persona_presente = True
                    l_sh, r_sh = kpts[5], kpts[6]
                    l_wrist, r_wrist = kpts[9], kpts[10]
                    l_hip, r_hip = kpts[11], kpts[12]

                    # Cálculo geométrico de la proporción del torso basado en los hombros
                    distancia_hombros = abs(l_sh[0] - r_sh[0])
                    centro_x = (l_sh[0] + r_sh[0]) / 2.0
                    
                    # Generación de la caja virtual del torso
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

                    # Renderizado UI del sistema de rastreo corporal
                    if min_x_torso > 0 and min_y_torso > 0:
                        cv2.rectangle(frame, (int(min_x_torso), int(min_y_torso)), (int(max_x_torso), int(max_y_torso)), (255, 255, 255), 1) # Torso
                        cv2.circle(frame, (int(bolsillo_izq_x), int(bolsillo_izq_y)), radio_bolsillo, (0, 165, 255), 1) # Bolsillo Izquierdo
                        cv2.circle(frame, (int(bolsillo_der_x), int(bolsillo_der_y)), radio_bolsillo, (0, 165, 255), 1) # Bolsillo Derecho

                    # Evaluación del estado de las muñecas
                    for wrist in [l_wrist, r_wrist]:
                        wx, wy = wrist
                        if wx > 0 and wy > 0:
                            # Validar colisión: ¿La mano toca el centro del torso o la zona de bolsillos?
                            en_torso = (min_x_torso <= wx <= max_x_torso) and (min_y_torso <= wy <= max_y_torso)
                            dist_bolsillo_izq = math.hypot(wx - bolsillo_izq_x, wy - bolsillo_izq_y)
                            dist_bolsillo_der = math.hypot(wx - bolsillo_der_x, wy - bolsillo_der_y)
                            en_bolsillo = (dist_bolsillo_izq < radio_bolsillo) or (dist_bolsillo_der < radio_bolsillo)

                            if en_torso or en_bolsillo:
                                # Las manos cruzaron a zona de ocultamiento
                                manos_en_peligro = True
                                cv2.circle(frame, (int(wx), int(wy)), 8, (0, 0, 255), -1)
                            else:
                                cv2.circle(frame, (int(wx), int(wy)), 6, (0, 255, 0), -1)

        # Inferencia de YOLOv8 de detección de objetos en simultáneo
        obj_results = model_obj.track(frame, persist=True, conf=0.30, verbose=False)
        conteo_actual = {73: 0, "BOTELLA": 0}
        
        if obj_results[0].boxes.id is not None:
            clases_obj = obj_results[0].boxes.cls.cpu().numpy().astype(int)
            boxes_obj = obj_results[0].boxes.xyxy.cpu().numpy().astype(int)

            for box, cls in zip(boxes_obj, clases_obj):
                x1, y1, x2, y2 = box
                # Chequeo lógico AABB: ¿El objeto está tocando el estante ROI?
                toca_estante = not (x2 < ESTANTE_ROI[0] or x1 > ESTANTE_ROI[2] or y2 < ESTANTE_ROI[1] or y1 > ESTANTE_ROI[3])

                if cls in [73, 67]:
                    conteo_actual[73] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2)
                elif cls in [39, 64]:
                    conteo_actual["BOTELLA"] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2)

        # Si hay menos botellas vistas de lo normal, asumimos faltante (están en las manos del cliente)
        hay_faltante = (conteo_actual[73] < stock_esperado[73]) or (conteo_actual["BOTELLA"] < stock_esperado["BOTELLA"])

        # LÓGICA CORE DE SMARTGUARD
        if persona_presente:
            if hay_faltante and manos_en_peligro:
                # Faltan botellas Y las manos están escondidas = Potencial hurto
                frames_ocultamiento_confirmado += 1
                color_ui = (0, 0, 255) # UI Roja
                mensaje = "ALERTA BIOMETRICA: OCULTAMIENTO"
            elif hay_faltante and not manos_en_peligro:
                # Falta una botella pero las manos son visibles = Cliente normal
                frames_ocultamiento_confirmado = 0
                color_ui = (255, 255, 0) # UI Amarilla
                mensaje = "CLIENTE SOSTENIENDO OBJETO"
            else:
                # Nadie toca las botellas
                frames_ocultamiento_confirmado = 0
                color_ui = (0, 255, 0) # UI Verde
                mensaje = "STOCK SEGURO"
            
            # Si la postura anómala persiste suficientes frames seguidos (evita falsos positivos por parpadeos de la IA)
            if frames_ocultamiento_confirmado >= UMBRAL_GATILLO:
                tiempo_actual = time.time()
                # Verifica si ya pasó el cooldown antes de spamear el grupo de Telegram
                if (tiempo_actual - ultimo_disparo) > TIEMPO_COOLDOWN:
                    print("[GATILLO BIOMETRICO] Despachando evidencia local...")
                    frame_copia = frame.copy()
                    threading.Thread(target=procesar_y_despachar_sospecha, args=(frame_copia,), daemon=True).start()
                    ultimo_disparo = tiempo_actual
                    time.sleep(5.0)
                frames_ocultamiento_confirmado = 0
                
            # Escribe en la esquina superior la instrucción actual del sistema
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2)
        else:
            # Mantenimiento de estado base sin presencia humana
            frames_ocultamiento_confirmado = 0
            cv2.putText(frame, "MONITOREO PASIVO...", (10, 35), 1, 1.2, (255, 255, 255), 2)

        # Dibuja la ROI del pasillo (estante)
        cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1)
        
        # Bloquea la variable compartida e inyecta este frame procesado para que FastAPI lo tome
        with lock_frame:
            ultimo_frame_procesado = frame.copy()

        time.sleep(0.01)

    cv2.destroyAllWindows()          
    cap.release()

# ==========================================
# CONTROL DE CICLO DE VIDA DEL SERVIDOR
# ==========================================
# Hook de FastAPI que se ejecuta justo al momento de arrancar el servidor `uvicorn`
@app.on_event("startup")
def iniciar_servicios_segundo_plano():
    threading.Thread(target=bucle_vigilancia, daemon=True).start()
    threading.Thread(target=bucle_telegram_polling, daemon=True).start()

# Hook de limpieza en caso de presionar Ctrl+C
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
# Generador asíncrono para emitir vídeo en formato Multipart MJPEG directo al dashboard React
async def generar_frames_mjpeg():
    global ultimo_frame_procesado, sistema_activo
    try:
        while sistema_activo:
            frame_a_enviar = None
            
            # Lee de manera segura el frame modificado por el hilo de vigilancia
            with lock_frame:
                if ultimo_frame_procesado is not None:
                    frame_a_enviar = ultimo_frame_procesado.copy()
            
            # MANEJO DE ERROR AMIGABLE: Si no hay frame (cámara desconectada)
            if frame_a_enviar is None:
                # Generamos una "Carta de Ajuste" negra dinámicamente usando Numpy
                frame_a_enviar = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame_a_enviar, "Buscando senal de camara...", (100, 240), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame_a_enviar, "Por favor espere.", (220, 280), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            # Codificamos a formato jpeg
            ret, buffer = cv2.imencode('.jpg', frame_a_enviar)
            if ret:
                bytes_imagen = buffer.tobytes()
                # Construimos el protocolo de streaming multipart reemplazando de forma mixta (x-mixed-replace)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + bytes_imagen + b'\r\n')
            await asyncio.sleep(0.04)
    except asyncio.CancelledError:
        # Pasa en silencio cuando el usuario cierra la pestaña del navegador
        pass

# Ruta de la API encargada de entregar el feed de video
@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generar_frames_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

# Ruta de monitoreo de vida estándar
@app.get("/")
def health_check():
    return {"status": "online"}