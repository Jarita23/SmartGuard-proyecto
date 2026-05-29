# Importación de módulos del sistema operativo y de ejecución
import os
import sys

# Desactivamos el multihilo interno de FFmpeg para evitar colisiones
# Esto asegura que la lectura del stream RTSP (las cámaras individuales) sea estable
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
# 🛣️ STREAMING ENDPOINT CON UX DEFENSIVA
# ==========================================
import numpy as np                            # Para crear arrays numéricos (matrices de imágenes)
from pathlib import Path                      # Para manejar rutas de archivos de forma segura
from pydantic import BaseModel, HttpUrl       # Para la validación estricta de datos
from typing import Optional, Dict, Any        # Para definir tipos de datos en los esquemas

# ==========================================
# 🔐 CARGA BLINDADA DE VARIABLES DE ENTORNO
# ==========================================
from dotenv import load_dotenv                # Para cargar secretos desde el archivo .env

# Forzamos la ruta absoluta: buscamos el .env exactamente al lado de este script
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Cargamos las variables de entorno, sobreescribiendo las existentes en memoria
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Printeos de control para confirmar que el entorno se cargó bien al iniciar
print(f"🔍 [SISTEMA] Archivo .env forzado desde: {ENV_PATH}")
print(f"🔑 Verificando SUPABASE_URL: {'OK (Conectado)' if os.getenv('SUPABASE_URL') else 'ERROR (No encontrado)'}")

# Importaciones de FastAPI (Backend) y Google GenAI/Ultralytics (Inteligencia Artificial)
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from ultralytics import YOLO

# ==========================================
# 🔌 INICIALIZACIÓN DE SERVICIOS (SINGLETON)
# ==========================================
# Inicialización de Gemini
# ==========================================
# 🔌 INICIALIZACIÓN DE SERVICIOS (MODO DIOS)
# ==========================================
# Inicialización del cliente de Gemini usando la llave de Google
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# 🚨 Ignoramos el Singleton local y creamos un Cliente Maestro puro
from supabase import create_client

# Obtenemos credenciales de Supabase del entorno
SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")
SUPABASE_MASTER_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Validación defensiva: Si no hay llave de administrador, matamos el proceso para evitar errores silenciosos
if not SUPABASE_MASTER_KEY:
    print("❌ ERROR FATAL: No encuentro SUPABASE_SERVICE_ROLE_KEY en el archivo .env")
    print("Por favor, asegúrate de haberla pegado correctamente.")
    sys.exit(1)

# Al inicializar con la llave Service Role, ignoramos todas las políticas RLS (Row Level Security)
supabase = create_client(SUPABASE_URL_ENV, SUPABASE_MASTER_KEY)

# 🛡️ UPGRADE DE SEGURIDAD: Restricción de Orígenes (CORS)
# Solo el Dashboard de React y el servidor local tienen permiso de conectarse al backend
ORIGINES_PERMITIDOS = [
    "http://localhost:3000",      # Dashboard en desarrollo
    "http://127.0.0.1:3000",      # Alternativa localhost
    "http://localhost:8000"       # FastAPI mismo
    # "https://midashboard-produccion.com" # Se activará en la defensa final
]

# ==========================================
# 🚀 AQUÍ ESTÁ LA LÍNEA QUE FALTABA
# ==========================================
# Creación de la instancia principal de la aplicación FastAPI
app = FastAPI(
    title="SmartGuard AI - Human in the Loop Engine",
    description="Sistema de análisis biomecánico con validación humana forense - v3.5",
    version="3.5.0"
)

# Aplicamos el middleware de CORS para bloquear peticiones de dominios no autorizados
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINES_PERMITIDOS, # ❌ Ya no es "*", ahora es una lista blanca (Whitelist)
    allow_credentials=True,            # Permite el envío de cookies/credenciales
    allow_methods=["GET", "POST", "OPTIONS"], # Limitamos los verbos HTTP permitidos por seguridad
    allow_headers=["*"],               # Permite todos los encabezados HTTP
)

# ==========================================
# 📱 CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
# Credenciales quemadas en el código (se recomienda pasar esto a .env en el futuro)
TELEGRAM_TOKEN = "8848721200:AAGbvjLg51ng6CLxpatz7pnAbvteHg3JN1k"
TELEGRAM_CHAT_ID = "-1003790783396"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ==========================================
# 📡 VARIABLES GLOBALES Y CONTROL DE ESTADO
# ==========================================
# Cargamos los modelos YOLOv8 para objetos y pose biométrica
model_obj = YOLO('yolov8n.pt')      
model_pose = YOLO('yolov8n-pose.pt') 

# Región de Interés (ROI) donde están las botellas/licores (x1, y1, x2, y2)
ESTANTE_ROI = [450, 100, 630, 450] 
# Enlace RTSP de la cámara individual que vigila el pasillo
RTSP_URL = 0

# Variables para manejar el flujo asíncrono y la memoria del sistema
ultimo_frame_procesado = None          # Guarda el último frame renderizado para el streaming web
lock_frame = threading.Lock()          # Evita que múltiples hilos modifiquen la variable al mismo tiempo
sistema_activo = True                  # Variable de control (kill-switch) para los bucles
ultimo_disparo = 0.0                   # Timestamp del último hurto detectado (para manejar cooldown)
qr_detector = cv2.QRCodeDetector()     # Inicializa el motor de lectura QR
modo_reposicion = False                # Bandera lógica para suspender las alarmas si hay un reponedor

# ==========================================
# 📐 ESQUEMAS DE VALIDACIÓN DE DATOS (PYDANTIC)
# ==========================================
# Este esquema asegura que los datos insertados en Supabase siempre tengan la estructura correcta
class AlertaBiometricaSchema(BaseModel):
    camara_id: int
    etiqueta: str
    descripcion: str
    severidad: str
    tipo: str
    estado_validacion: str
    imagen_url: Optional[str] = None   # Puede ser nula si la borramos por privacidad (falsa alarma)
    metadata: Dict[str, Any]           # Diccionario para meter el hash y el nombre del archivo

# Clase personalizada para leer la cámara de seguridad en un hilo separado sin bloquear el análisis
class CamaraAsincrona:
    def __init__(self, src):
        # 🚀 FIX: Detección inteligente de hardware
        if isinstance(src, int) or src == "0":
            # Si es 0 (Webcam local), usamos el motor DirectShow de Windows
            self.cap = cv2.VideoCapture(int(src), cv2.CAP_DSHOW)
        else:
            # Si es un texto RTSP (Cámara IP), usamos el motor FFMPEG
            self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
            
        self.ret, self.frame = self.cap.read()
        self.corriendo = True
        self.hilo = threading.Thread(target=self._actualizar, daemon=True)
        self.hilo.start()
    def _actualizar(self):
        # Bucle infinito del hilo: mantiene el frame actual siempre fresco
        while self.corriendo:
            try:
                ret, frame = self.cap.read()
                if ret:
                    self.ret = ret
                    self.frame = frame
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
# ☁️ FLUJO PIPELINE: REGISTRO, STORAGE Y TELEGRAM
# ==========================================
# Función que empaqueta la evidencia y dispara las alertas cuando el Edge detecta un robo
def procesar_y_despachar_sospecha(frame_evidencia):
    global ultimo_disparo
    print("🚨 [EDGE] Despachando sospecha biométrica local...")
    try:
        # 1. Convertir matriz de imagen OpenCV (frame) a bytes .jpg
        ret, buffer = cv2.imencode('.jpg', frame_evidencia)
        if not ret: return
        imagen_bytes = buffer.tobytes()

        # ==========================================
        #  UPGRADE LEGAL: HASH SHA-256 (Cadena de Custodia)
        # ==========================================
        # Genera una huella dactilar única de la foto para demostrar que no fue manipulada
        firma_sha256 = hashlib.sha256(imagen_bytes).hexdigest()
        print(f"🔐 [SEGURIDAD] Firma criptográfica de la evidencia generada: {firma_sha256}")

        # 2. Subir de forma inmediata al Bucket de Supabase Storage
        nombre_archivo = f"evidencia_{int(time.time())}.jpg"
        bucket_name = "evidencia_biometrica"
        
        # Sube el array de bytes directo al almacenamiento en la nube
        supabase.storage.from_(bucket_name).upload(nombre_archivo, imagen_bytes, {"content-type": "image/jpeg"})
        # Genera el link público para insertarlo en la DB
        imagen_url = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo)
        
        # 3. Validación Estricta de Datos y Creación de Fila
        datos_crudos = {
            "camara_id": 1,
            "etiqueta": "SOSPECHA DE OCULTAMIENTO",
            "descripcion": "Análisis biométrico local detectó movimiento anómalo de manos.",
            "severidad": "media",
            "tipo": "biometria_ia_3.5",
            "estado_validacion": "pendiente",
            "imagen_url": imagen_url,
            "metadata": {
                "archivo_storage": nombre_archivo,
                "sha256_hash": firma_sha256  # 👈 GUARDAMOS LA HUELLA DACTILAR EN SUPABASE
            }
        }
        
        # 🚨 VALIDACIÓN SENIOR: Pydantic verifica que los tipos de datos encajen en el modelo
        alerta_validada = AlertaBiometricaSchema(**datos_crudos)
        
        # Insertamos el registro validado a la base de datos de Supabase
        res_db = supabase.table("alertas").insert(alerta_validada.model_dump()).execute()
        
        # Rescatamos el ID autoincremental recién creado (o un timestamp de fallback)
        alerta_id = res_db.data[0]['id'] if res_db.data else int(time.time())

        # 4. Construir Mensaje de Telegram con Botones Interactivos (Inline Keyboard para HITL)
        payload_telegram = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"⚠️ **SMARTGUARD LIVE** ⚠️\n\n📌 **Evento:** Alerta Biométrica Local\n🆔 **ID Registro:** {alerta_id}\n\nEl sistema Edge detectó que las manos del sujeto interactuaron con el área de riesgo. Valide la intencionalidad:",
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [
                        # Inyectamos los datos del archivo en el callback para saber qué foto procesar luego
                        {"text": "🔴 Riesgo Alto (Robo)", "callback_data": f"alto:{alerta_id}:{nombre_archivo}"},
                        {"text": "🟢 Falsa Alarma", "callback_data": f"falsa:{alerta_id}:{nombre_archivo}"}
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
            # Actualizamos la fila de la BD agregando el ID de Telegram, para poder editarlo a posteriori
            supabase.table("alertas").update({"telegram_message_id": msg_id}).eq("id", alerta_id).execute()
            print(f"📡 Alerta enviada a Telegram. Message ID registrado: {msg_id}")

    except Exception as e:
        print(f"❌ [BACKEND] Error al despachar sospecha: {e}")
    

# ==========================================
# 🧠 CAPA CLOUD FORENSE (GEMINI BAJO DEMANDA)
# ==========================================
# Función asincrónica que delega el perfilamiento a Gemini 2.5 SOLO si el humano confirma el robo
def ejecutar_perfilamiento_forense(alerta_id, nombre_archivo):
    print(f"🧠 [CLOUD] Activando Gemini para análisis forense del registro {alerta_id}...")
    try:
        # Descargamos los bytes seguros de la foto directamente del storage de Supabase
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
        
        # Actualizamos la base de datos inyectando la conclusión forense de la IA y subiendo el nivel de alarma
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
# Bucle que "escucha" las acciones que el guardia hace desde su celular en Telegram
def bucle_telegram_polling():
    print("📱 [TELEGRAM BOT] Escuchador interactivo de validación humana activado.")
    offset = 0 # Puntero de Telegram para no procesar mensajes repetidos
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
                
                # Buscamos si la actualización es un click de botón (callback_query)
                # Buscamos si la actualización es un click de botón (callback_query)
                if "callback_query" in update:
                    cb_query = update["callback_query"]
                    cb_data = cb_query["data"]  # Formato: "accion:alerta_id:nombre_archivo"
                    msg_id = cb_query["message"]["message_id"]
                    chat_id = cb_query["message"]["chat"]["id"]
                    cb_query_id = cb_query["id"]
                    
                    # Separamos los parámetros del payload inyectado en el botón
                    partes = cb_data.split(":")
                    accion = partes[0]
                    alerta_id = int(partes[1])
                    nombre_archivo = partes[2]
                    
                    # ==========================================
                    # 🛡️ UX/UI UPGRADE: Retroalimentación Háptica
                    # ==========================================
                    # Avisamos a Telegram Y mostramos un pop-up nativo al guardia (Toast) confirmando su click
                    mensaje_ux = "🔴 Procesando Alerta y activando IA..." if accion == "alto" else "🟢 Eliminando alerta por privacidad..."
                    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={
                        "callback_query_id": cb_query_id,
                        "text": mensaje_ux,
                        "show_alert": False # Aparece como un toast sutil en la parte inferior en la app móvil
                    })
                    # ==========================================
                    
                    if accion == "alto":
                        # El guardia confirmó la amenaza de hurto
                        print(f"🔴 Guardia reporta RIESGO ALTO para alerta {alerta_id}.")
                        # 1. Actualizar estado en Supabase a riesgo_alto
                        supabase.table("alertas").update({"estado_validacion": "riesgo_alto"}).eq("id", alerta_id).execute()
                        
                        # 2. Editar el mensaje de Telegram eliminando los botones para evitar doble confirmación
                        requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "caption": f"🔴 **HURTO CONFIRMADO** 🔴\n\nEl guardia validó la alerta {alerta_id}.\n🧠 *Procesando perfil forense con Inteligencia Artificial...*"
                        })
                        
                        # 3. Disparar Gemini en segundo plano para no bloquear el bot
                        # Creamos un pequeño hilo huérfano para evitar colgar el polling de Telegram
                        def hilo_forense():
                            perfil = ejecutar_perfilamiento_forense(alerta_id, nombre_archivo)
                            # Edita el mensaje final en Telegram inyectando el informe devuelto por Gemini
                            requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={
                                "chat_id": chat_id,
                                "message_id": msg_id,
                                "caption": f"🔴 **PROCEDIMIENTO EN DESARROLLO** 🔴\n\nEl guardia confirmó el hurto.\n\n📝 **Informe Forense IA:**\n{perfil}"
                            })
                        threading.Thread(target=hilo_forense, daemon=True).start()
                        
                    elif accion == "falsa":
                        # El guardia determinó que fue un cliente actuando raro pero sin intenciones de robo
                        print(f"🟢 Guardia reporta FALSA ALARMA para alerta {alerta_id}. Aplicando privacidad absoluta.")
                        # 1. Actualizar estado en Supabase (Guardamos el registro de texto para estadística, pero sin datos personales)
                        supabase.table("alertas").update({
                            "estado_validacion": "falsa_alarma",
                            "imagen_url": None  # Destruimos el enlace en la base de datos
                        }).eq("id", alerta_id).execute()
                        
                        # 2. Borrar archivo físico del Storage de Supabase para cumplir normativa de privacidad
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
            time.sleep(0.5) # Respiro de CPU
        except Exception as e:
            print(f"⚠️ Error en bucle de polling Telegram: {e}")
            time.sleep(3) # Pausa en caso de desconexión

# ==========================================
# 🛡️ MOTOR BIOMÉTRICO LOCAL (EDGE)
# ==========================================
# Núcleo de Computer Vision de SmartGuard
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo
    
    # Inicializa el buffer RTSP en un hilo paralelo
    cap = CamaraAsincrona(RTSP_URL)
    frame_buffer = [] # Memoria temporal para guardar los últimos 30 frames
    
    # Parámetros biométricos y de inventario
    stock_esperado = {73: 1, "BOTELLA": 1} # Clase 73 = Botella, String "BOTELLA" = etiqueta extra
    frames_ocultamiento_confirmado = 0     # Contador de frames donde hay sospecha
    UMBRAL_GATILLO = 15                    # Número de frames anómalos seguidos para gatillar la foto
    TIEMPO_COOLDOWN = 15.0                 # Segundos de espera mínima antes de disparar otra alerta a Telegram

    # 👇 2. Agrega la memoria de frames para el QR 👇
    frames_desde_ultimo_qr = 999           # Inicia con un valor alto para asegurar que arranque en modo normal
    UMBRAL_MEMORIA_QR = 90                 # Si pasan 90 frames sin ver el QR (aprox 3 seg), vuelve a modo vigilancia

    print("🛡️ SmartGuard Biométrico Preciso Activado.")

    while cap.corriendo and sistema_activo:
        # Extraer el frame fresco del buffer
        success, frame = cap.read()
        if not success:
            time.sleep(0.03)
            continue

        # Normalizamos la resolución para procesar más rápido con YOLO
        frame = cv2.resize(frame, (640, 480))
        # Mantiene un historial de los frames por si necesitamos retrospectiva
        frame_buffer.append(frame.copy())
        if len(frame_buffer) > 30: frame_buffer.pop(0) 

        # 👇 INICIO DEL BLOQUE DE MAXI: ESCÁNER QR Y MODO REPOSICIÓN 👇
        # Búsqueda de códigos QR en el frame actual
        data_qr, bbox_qr, _ = qr_detector.detectAndDecode(frame)
        
        # Validamos si es una credencial de reponedor autorizada
        if data_qr == "STAFF_SMARTGUARD": 
            frames_desde_ultimo_qr = 0     # Reiniciamos el reloj de tolerancia
            modo_reposicion = True         # Pasamos el sistema a modo seguro
            
            # Dibujamos un polígono visual alrededor del QR detectado
            if bbox_qr is not None and len(bbox_qr) > 0: 
                pts = bbox_qr[0].astype(int) 
                for i in range(4): 
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i+1)%4]), (0, 255, 0), 2) 
                # Etiqueta visual de staff validado
                cv2.putText(frame, "STAFF VERIFICADO", (pts[0][0], pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2) 
        else: 
            # Si no vemos el QR, aumentamos el contador
            frames_desde_ultimo_qr += 1 
            # Si expira el tiempo de tolerancia, cancelamos el modo reponedor
            if frames_desde_ultimo_qr > UMBRAL_MEMORIA_QR: 
                modo_reposicion = False 

        if modo_reposicion: 
            # Lógica mientras un reponedor trabaja: no contamos ocultamientos
            frames_ocultamiento_confirmado = 0 
            color_ui = (0, 140, 255) # Color naranja
            # Calculamos los segundos restantes de tolerancia para mostrarlo en pantalla
            mensaje = f"MODO REPOSICION: PASIVO ({max(0, (UMBRAL_MEMORIA_QR - frames_desde_ultimo_qr)//30)}s)" 
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2) 
            
            # Pintamos el estante naranja para indicar zona de mantención
            cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (0, 140, 255), 1) 
            # Actualizamos el endpoint web y pasamos al siguiente ciclo de cámara
            with lock_frame: 
                ultimo_frame_procesado = frame.copy() 
            time.sleep(0.01) 
            continue # <--- Esto hace que se salte todo el análisis de robos
        # 👆 FIN DEL BLOQUE DE MAXI 👆

        # Banderas de estado para la lógica cruzada
        manos_en_peligro = False
        persona_presente = False

        # Inferencia de YOLOv8 Pose (buscando esqueleto humano)
        results_pose = model_pose(frame, stream=True, verbose=False, conf=0.5)
        
        for r in results_pose:
            # Validamos si encontró articulaciones válidas
            if r.keypoints is not None and len(r.keypoints.xy) > 0:
                kpts = r.keypoints.xy[0].cpu().numpy()
                # Exigimos al menos 13 keypoints detectados para asegurar un cuerpo visible
                if len(kpts) >= 13: 
                    persona_presente = True
                    # Extraemos coordenadas de hombros (5,6), muñecas (9,10) y caderas (11,12)
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
                    
                    # Generación de esferas virtuales de ocultamiento en los bolsillos
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
                                cv2.circle(frame, (int(wx), int(wy)), 8, (0, 0, 255), -1)  # Mano roja = Anómala
                            else:
                                cv2.circle(frame, (int(wx), int(wy)), 6, (0, 255, 0), -1)  # Mano verde = Segura

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

                # Mapeo de clases de la red neuronal COCO a lógica de licor
                if cls in [73, 67]: # Código 73=Botella
                    conteo_actual[73] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2)
                elif cls in [39, 64]: # Clases similares agrupadas como BOTELLA
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
                    print("📸 [GATILLO BIOMÉTRICO] Despachando evidencia local a Supabase y Telegram...")
                    # 📸 Captura el frame EXACTO del impacto, incluyendo la interfaz roja para el guardia
                    frame_copia = frame.copy()
                    
                    # Dispara el hilo de subida cloud sin bloquear la vigilancia
                    threading.Thread(target=procesar_y_despachar_sospecha, args=(frame_copia,), daemon=True).start()
                    ultimo_disparo = tiempo_actual
                    
                    print("⏳ [COOLDOWN] Congelando análisis local por 5 segundos...")
                    time.sleep(5.0) # Penalty timer al gatillar
                frames_ocultamiento_confirmado = 0 # Reiniciamos contador
                
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
        time.sleep(0.01) # Ligero descanso para no saturar 100% de CPU en un solo núcleo

    # Libera recursos al apagar el servidor
    cap.release()

# ==========================================
# ⚡ CONTROL DE CICLO DE VIDA DEL SERVIDOR
# ==========================================
# Hook de FastAPI que se ejecuta justo al momento de arrancar el servidor `uvicorn`
@app.on_event("startup")
def iniciar_servicios_segundo_plano():
    # Lanzamos el motor de visión local (Edge)
    threading.Thread(target=bucle_vigilancia, daemon=True).start()
    # Lanzamos el bot interactivo HITL de Telegram
    threading.Thread(target=bucle_telegram_polling, daemon=True).start()

# Hook de limpieza en caso de presionar Ctrl+C
@app.on_event("shutdown")
def apagar_sistema():
    global sistema_activo
    print("🛑 [SISTEMA] Cerrando motores y cortando energía...")
    sistema_activo = False # Modifica bandera global y rompe los whiles limpiamente
    os._exit(0)

# ==========================================
# 🛣️ STREAMING ENDPOINT
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
            
            # 🔥 MANEJO DE ERROR AMIGABLE: Si no hay frame (cámara desconectada)
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
                       b'Content-Type: image/jpeg\r\n\r\n' + bytes_imagen + b' \r\n')
                
            # Controla los FPS de transmisión a la interfaz web (25fps aprox)
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