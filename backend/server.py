# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN INICIAL
# ==========================================
import os                                     # Trae herramientas básicas para que el código hable con tu computador
import sys                                    # Permite interactuar con configuraciones profundas del programa
os.environ["OPENCV_FFMPEG_THREADS"] = "1"     # Evita que el video se tranque limitando el esfuerzo de la tarjeta gráfica

import cv2                                    # Son los "ojos" del programa, lee y dibuja sobre las imágenes de la cámara
import io                                     # Ayuda a manejar las imágenes temporalmente en la memoria del computador
import time                                   # Reloj interno para medir pausas y saber a qué hora exacta ocurrió un evento
import json                                   # Traduce los datos a un formato de texto que Telegram puede entender
import PIL.Image                              # Herramienta extra para preparar y ajustar la foto antes de dársela a la IA
import threading                              # Crea "trabajadores": permite mirar la cámara y escuchar Telegram al mismo tiempo
import requests                               # Es el "cartero" virtual que envía los mensajes y fotos por internet
import asyncio                                # Permite que el video en vivo fluya sin congelar el resto del programa
import math                                   # Calculadora interna para medir distancias corporales (ej. mano al bolsillo)
import hashlib                                # Crea un sello de seguridad único (huella digital) para blindar la evidencia

# ==========================================
# STREAMING ENDPOINT CON UX DEFENSIVA
# ==========================================
import numpy as np                            # Herramienta matemática que ayuda a dibujar la pantalla negra si se cae la cámara
from pathlib import Path                      # Se encarga de buscar y unir las carpetas de tus archivos sin perderse
from pydantic import BaseModel, HttpUrl       # Un guardia de seguridad que revisa que los datos que entran sean correctos
from typing import Optional, Dict, Any        # Etiquetas para mantener el código ordenado y saber qué tipo de dato es cada cosa

# ==========================================
# CARGA BLINDADA DE VARIABLES DE ENTORNO
# ==========================================
from dotenv import load_dotenv                # La llave para poder leer tu archivo secreto .env con las contraseñas

BASE_DIR = Path(__file__).resolve().parent    # El programa descubre automáticamente en qué carpeta está guardado
ENV_PATH = BASE_DIR / ".env"                  # Arma el camino exacto para llegar a leer tu archivo .env

load_dotenv(dotenv_path=ENV_PATH, override=True) # Abre el archivo .env, memoriza las claves y pisa cualquier clave antigua

print(f"[SISTEMA] Archivo .env forzado desde: {ENV_PATH}") # Muestra un aviso en pantalla confirmando que encontró las claves

from fastapi import FastAPI                   # El motor web principal que permite que internet se conecte con este código
from fastapi.responses import StreamingResponse # Herramienta especial para enviar video continuo en vez de texto normal
from fastapi.middleware.cors import CORSMiddleware # Un portero que decide qué páginas web externas tienen permiso para entrar
from google import genai                      # Conecta tu programa con el cerebro en la nube de Google (para el perfil forense)
from ultralytics import YOLO                  # Conecta tu programa con la Inteligencia Artificial visual (para ver personas y objetos)

# ==========================================
# INICIALIZACIÓN DE SERVICIOS (MODO DIOS)
# ==========================================
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) # Enciende el motor de Google usando tu contraseña secreta

from supabase import create_client            # Trae la herramienta para conectarse a tu base de datos en la nube

SUPABASE_URL_ENV = os.getenv("SUPABASE_URL")  # Lee la dirección web de tu base de datos
SUPABASE_MASTER_KEY = os.getenv("SUPABASE_MASTER_KEY") # Lee la llave maestra que te da poder absoluto sobre la base de datos

supabase = create_client(SUPABASE_URL_ENV, SUPABASE_MASTER_KEY) # Conecta oficialmente el programa con tu base de datos

ORIGINES_PERMITIDOS = [                       # Lista VIP de quién puede ver el video de las cámaras
    "http://localhost:3000",                  # Permite que el diseño de prueba entre
    "http://127.0.0.1:3000",                  # Otra forma de escribir la dirección de prueba
    "http://localhost:8000",                  # Se da permiso a sí mismo para funcionar
    "http://localhost:5173",                  # Permite que la interfaz visual de React (Vite) se conecte
]

app = FastAPI(                                # Crea el servidor web, como si abrieras un local para atender clientes
    title="SmartGuard AI - Computer Vision Autonomous Engine", # Le pone el nombre oficial al proyecto
    description="Sistema biomecánico con detección autónoma de credenciales QR - v3.7", # Explica qué hace
    version="3.7.0"                           # Indica en qué versión va el desarrollo
)

app.add_middleware(                           # Le pone las reglas al portero web que creamos antes
    CORSMiddleware,                           # Activa el escudo de seguridad
    allow_origins=["*"],                      # El "*" significa que acepta visitas desde cualquier página (ideal para presentar)
    allow_credentials=True,                   # Permite que las visitas traigan credenciales o cookies
    allow_methods=["*"],                      # Permite cualquier tipo de orden (leer datos, borrar datos, etc.)
    allow_headers=["*"],                      # Permite recibir cualquier tipo de información extra en la conexión
)

# ==========================================
# CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Saca la contraseña del bot de Telegram desde el archivo .env
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Identifica a qué grupo específico de Telegram hay que mandar las alertas
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" # Arma la dirección web exacta para mandarle órdenes al bot

# ==========================================
# VARIABLES GLOBALES Y CONTROL DE ESTADO
# ==========================================
model_obj = YOLO(str(BASE_DIR / 'models' / 'yolov8n.pt')) # Carga el cerebro visual que sabe reconocer objetos cotidianos
model_pose = YOLO(str(BASE_DIR / 'models' / 'yolov8n-pose.pt')) # Carga el cerebro visual que sabe leer el esqueleto humano

qr_detector = cv2.QRCodeDetector()            # Enciende el escáner especial para leer los códigos QR del personal

ESTANTE_ROI = [450, 100, 630, 450]            # Dibuja una caja imaginaria en la pantalla que define la zona de peligro (el estante)

fuente_env = os.getenv("WEBCAM_INDEX", "0")   # Revisa si le dijiste al sistema qué cámara usar en el .env

if fuente_env.isdigit():                      # Si le pusiste un número simple (como "0")...
    fuente_video = int(fuente_env)            # ...entiende que quieres usar la cámara web de tu propio notebook
    print("[HARDWARE] SmartGuard configurado en modo: WEBCAM INTEGRADA LOCAL.") # Te avisa que usará la cámara local
else:                                         # Si le pusiste un texto largo (una URL)...
    fuente_video = fuente_env                 # ...entiende que es una cámara de seguridad externa por internet
    print("[HARDWARE] SmartGuard configurado en modo: CAMARA IP DAHUA (RTSP).") # Te avisa que está conectado a la cámara Dahua

ultimo_frame_procesado = None                 # Una pizarra en blanco donde guardaremos la foto más reciente de la cámara
lock_frame = threading.Lock()                 # Un candado virtual para que no se mezcle el video al enviar la imagen a internet
sistema_activo = True                         # Un interruptor maestro: si dice True, el sistema vigila; si dice False, se apaga
ultimo_disparo = 0.0                          # Recuerda a qué hora fue la última alarma para no saturar Telegram con mensajes

modo_reposicion = False                       # Interruptor logístico: si dice True, es porque entró un trabajador a reponer cosas

class CamaraAsincrona:                        # Crea un trabajador especial dedicado única y exclusivamente a mirar la cámara
    def __init__(self, src):                  # Instrucciones para cuando el trabajador empieza su turno
        if isinstance(src, int):              # Si la cámara es local...
            self.cap = cv2.VideoCapture(src)  # ...enciende la cámara del notebook
        else:                                 # Si es una cámara por internet...
            self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG) # ...se conecta a la red usando herramientas especiales para evitar lag
            
        self.ret, self.frame = self.cap.read() # Saca la primera foto de prueba
        self.corriendo = True                 # Le dice al trabajador que su turno comenzó
        self.hilo = threading.Thread(target=self._actualizar, daemon=True) # Lo manda a hacer su trabajo en segundo plano
        self.hilo.start()                     # Le da la orden de partir

    def _actualizar(self):                    # El trabajo repetitivo que hace este trabajador
        while self.corriendo:                 # Mientras esté en su turno...
            try:                              # ...intenta hacer lo siguiente:
                ret, frame = self.cap.read()  # ...sacar una foto nueva de la cámara
                if ret:                       # ...si la foto salió bien:
                    self.ret = ret            # ...avisa que hubo éxito
                    self.frame = frame        # ...y guarda la foto fresca
                time.sleep(0.03)              # ...descansa un par de milisegundos para no quemar el procesador del computador
            except Exception:                 # Si algo explota (se corta el internet o el cable)...
                break                         # ...deja de intentar y renuncia al trabajo

    def read(self):                           # Si el programa principal le pide la foto a este trabajador...
        return self.ret, self.frame.copy() if self.ret else None # ...le entrega una copia exacta de la última foto buena

    def release(self):                        # Cuando queremos que el trabajador termine su turno y se vaya
        self.corriendo = False                # Le dice que ya no corra más
        if self.hilo.is_alive():              # Si el trabajador sigue haciendo cosas...
            self.hilo.join(timeout=1.0)       # ...le da 1 segundo de gracia para que termine
        self.cap.release()                    # Apaga el lente de la cámara físicamente

# ==========================================
# FLUJO PIPELINE: REGISTRO, STORAGE Y TELEGRAM
# ==========================================
def procesar_y_despachar_sospecha(frame_evidencia): # El protocolo que se activa cuando alguien roba
    global ultimo_disparo                     # Llama al recuerdo de la última alarma
    print("[EDGE] Despachando sospecha biometrica local...") # Avisa por pantalla que empezó el papeleo del robo
    try:                                      # Intenta hacer esto sin que el programa colapse:
        ret, buffer = cv2.imencode('.jpg', frame_evidencia) # Comprime la foto del robo para que no pese tanto
        if not ret: return                    # Si la compresión falla, cancela la alarma y se rinde
        imagen_bytes = buffer.tobytes()       # Convierte la foto en código puro de computador (ceros y unos)

        firma_sha256 = hashlib.sha256(imagen_bytes).hexdigest() # Le pone un candado matemático inviolable a la foto para que sea prueba legal

        nombre_archivo = f"evidencia_{int(time.time())}.jpg" # Le inventa un nombre al archivo basado en la fecha y hora exacta
        bucket_name = "evidencia_biometrica"  # El nombre de la carpeta en la nube de Supabase donde se guardará
        
        supabase.storage.from_(bucket_name).upload(nombre_archivo, imagen_bytes, {"content-type": "image/jpeg"}) # Sube la foto a internet
        imagen_url = supabase.storage.from_(bucket_name).get_public_url(nombre_archivo) # Pide el enlace web para poder ver la foto subida
        
        alerta_data = {                       # Crea la ficha policial del evento con todos los detalles
            "camara_id": 1,                   # Qué cámara lo vio
            "etiqueta": "SOSPECHA DE OCULTAMIENTO", # El título del delito
            "descripcion": "Analisis biometrico local detecto movimiento anomalo de manos.", # Lo que hizo el sospechoso
            "severidad": "media",             # Qué tan grave es (parte en media porque falta que el humano lo confirme)
            "tipo": "biometria_ia_3.5",       # La tecnología que lo pilló
            "estado_validacion": "pendiente", # Avisa que un guardia real tiene que revisarlo
            "imagen_url": imagen_url,         # Adjunta el link a la foto
            "metadata": {                     # Información técnica extra
                "archivo_storage": nombre_archivo, # El nombre del archivo en la nube
                "sha256_hash": firma_sha256   # Guarda la firma matemática para demostrar que la foto no fue alterada
            }
        }
        
        res_db = supabase.table("alertas").insert(alerta_data).execute() # Mete esta ficha policial a tu base de datos
        alerta_id = res_db.data[0]['id'] if res_db.data else int(time.time()) # Anota el número de folio de este delito

        payload_telegram = {                  # Prepara el mensaje de WhatsApp/Telegram para el guardia
            "chat_id": TELEGRAM_CHAT_ID,      # A qué grupo enviarlo
            "caption": f"**SMARTGUARD LIVE** \n\n**Evento:** Alerta Biometrica Local\n**ID Registro:** {alerta_id}\n\nEl sistema Edge detecto que las manos del sujeto interactuaron con el area de riesgo. Valide la intencionalidad:", # El texto de alerta
            "parse_mode": "Markdown",         # Permite poner negritas y cursivas en el texto
            "reply_markup": json.dumps({      # Crea los botones interactivos abajo de la foto
                "inline_keyboard": [
                    [
                        {"text": "Riesgo Alto (Robo)", "callback_data": f"alto:{alerta_id}:{nombre_archivo}"}, # Botón para confirmar robo
                        {"text": "Falsa Alarma", "callback_data": f"falsa:{alerta_id}:{nombre_archivo}"}       # Botón para perdonar a la persona
                    ]
                ]
            })
        }
        
        url_photo = f"{TELEGRAM_API_URL}/sendPhoto" # La dirección secreta de Telegram para enviar imágenes
        res_tg = requests.post(url_photo, data=payload_telegram, files={'photo': ('evidencia.jpg', imagen_bytes)}) # Envía el mensaje y la foto al celular del guardia
        
        if res_tg.status_code == 200:         # Si Telegram responde "Recibido sin problemas"...
            tg_data = res_tg.json()           # ...lee la boleta de confirmación de Telegram
            msg_id = tg_data['result']['message_id'] # ...guarda el número de mensaje que le dio Telegram
            supabase.table("alertas").update({"telegram_message_id": msg_id}).eq("id", alerta_id).execute() # Actualiza la base de datos con este número
            print(f"[TELEGRAM] Alerta enviada a Telegram. Message ID registrado: {msg_id}") # Celebra en pantalla que el mensaje llegó

    except Exception as e:                    # Si cualquier cosa falla en este proceso...
        print(f"[BACKEND] Error al despachar sospecha: {e}") # ...imprime el error sin apagar el programa

# ==========================================
# CAPA CLOUD FORENSE (GEMINI BAJO DEMANDA)
# ==========================================
def ejecutar_perfilamiento_forense(alerta_id, nombre_archivo): # Protocolo que se activa solo si el guardia aprieta el botón de "Robo"
    print(f"[CLOUD] Activando Gemini para analisis forense del registro {alerta_id}...") # Avisa que llamó a la IA de Google
    try:                                      # Intenta hacer lo siguiente:
        imagen_bytes = supabase.storage.from_("evidencia_biometrica").download(nombre_archivo) # Descarga la foto del robo desde la nube
        img = PIL.Image.open(io.BytesIO(imagen_bytes)) # Prepara la foto para que Google la pueda ver

        prompt = """
        Actúa como un perfilador forense de seguridad para supermercados. 
        Se ha confirmado un hurto en esta imagen capturada por SmartGuard.
        Tu labor es generar una descripción física estricta y corta del sospechoso para entregar a las autoridades.
        
        CONCENTRATE EXCLUSIVAMENTE EN:
        - Tipo y color de prendas superiores e inferiores (ej. Polerón negro con capucha, jeans azules).
        - Accesorios visibles (gorros, mascarillas, mochilas, bolsos).
        
        Responde estrictamente en un máximo de 15 palabras. Ve directo al grano sin introducciones.
        """                                   # Estas son las instrucciones estrictas que le damos a la IA para que analice la ropa
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img]) # Manda la foto y las instrucciones a Google
        descripcion_forense = response.text.strip() # Recibe la respuesta de Google y le limpia los espacios en blanco
        
        supabase.table("alertas").update({    # Va a la base de datos a modificar la alerta original...
            "descripcion_ia": descripcion_forense, # ...y le pega la descripción que hizo Google
            "severidad": "alta"               # ...y cambia el nivel de peligro a "Alto" definitivo
        }).eq("id", alerta_id).execute()      # Especifica a qué alerta se le deben hacer estos cambios
        
        print(f"[CLOUD] Perfil forense guardado en Supabase: {descripcion_forense}") # Avisa que todo salió bien
        return descripcion_forense            # Devuelve el texto para usarlo en Telegram
    except Exception as e:                    # Si Google falla o no hay internet...
        print(f"[CLOUD] Error en el perfilamiento forense de Gemini: {e}") # ...muestra el error
        return "Error al generar perfil forense." # ...y devuelve un mensaje genérico para que no explote nada

# ==========================================
# HILO TELEGRAM INTERACTIVE POLLING (HITL)
# ==========================================
def bucle_telegram_polling():                 # Un vigilante que solo se dedica a leer qué botones presiona el guardia en su celular
    print("[TELEGRAM BOT] Escuchador interactivo de validacion humana activado.") # Avisa que el vigilante llegó a su puesto
    offset = 0                                # Un marcador para saber qué mensajes de Telegram ya leímos y no repetirlos
    global sistema_activo                     # Revisa si el sistema entero sigue encendido
    
    while sistema_activo:                     # Mientras todo esté prendido...
        try:                                  # ...intenta:
            url = f"{TELEGRAM_API_URL}/getUpdates?offset={offset}&timeout=10" # Preguntarle a Telegram si alguien apretó un botón en los últimos 10 segundos
            res = requests.get(url, timeout=12) # Espera pacientemente la respuesta de Telegram
            if res.status_code != 200:        # Si Telegram está caído o no responde...
                time.sleep(2)                 # ...descansa 2 segundos
                continue                      # ...y vuelve a preguntar
                
            updates = res.json().get("result", []) # Si Telegram responde, lee la lista de cosas que pasaron
            for update in updates:            # Por cada cosa nueva que pasó...
                offset = update["update_id"] + 1 # ...mueve el marcador para no volver a leerla nunca más
                
                if "callback_query" in update: # Si lo que pasó fue que un guardia apretó un botón...
                    cb_query = update["callback_query"] # ...extrae la información de ese toque de pantalla
                    cb_data = cb_query["data"] # ...saca los datos secretos que escondimos en el botón
                    msg_id = cb_query["message"]["message_id"] # ...anota en qué mensaje exacto apretaron el botón
                    chat_id = cb_query["message"]["chat"]["id"] # ...anota el número del chat grupal
                    cb_query_id = cb_query["id"] # ...anota el ID único de este click
                    
                    partes = cb_data.split(":") # Corta los datos ocultos del botón usando los dos puntos como tijera
                    accion = partes[0]        # La primera parte dice si fue "alto" (robo) o "falsa" (error)
                    alerta_id = int(partes[1]) # La segunda parte dice el número de folio del delito
                    nombre_archivo = partes[2] # La tercera parte es el nombre de la foto
                    
                    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb_query_id}) # Le avisa a Telegram que ya registramos el click (apaga el relojito de carga en el celular)
                    
                    if accion == "alto":      # Si el guardia apretó el botón de Robo Real...
                        print(f"[TELEGRAM] Guardia reporta RIESGO ALTO para alerta {alerta_id}.") # ...avisa en pantalla
                        supabase.table("alertas").update({"estado_validacion": "riesgo_alto"}).eq("id", alerta_id).execute() # ...anota en la base de datos que es un ladrón confirmado
                        
                        requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={ # Cambia el texto del mensaje viejo en Telegram...
                            "chat_id": chat_id, # ...en el grupo actual...
                            "message_id": msg_id, # ...en ese mensaje específico...
                            "caption": f"**HURTO CONFIRMADO**\n\nEl guardia valido la alerta {alerta_id}.\n*Procesando perfil forense con Inteligencia Artificial...*" # ...por este texto nuevo informando que la IA está pensando
                        })
                        
                        def hilo_forense():   # Crea un mini-trabajador para pedirle el perfil a Google sin congelar el programa
                            perfil = ejecutar_perfilamiento_forense(alerta_id, nombre_archivo) # Le pide el análisis de ropa a Gemini
                            requests.post(f"{TELEGRAM_API_URL}/editMessageCaption", json={ # Vuelve a cambiar el texto de Telegram...
                                "chat_id": chat_id, # ...
                                "message_id": msg_id, # ...
                                "caption": f"**PROCEDIMIENTO EN DESARROLLO**\n\nEl guardia confirmo el hurto.\n\n**Informe Forense IA:**\n{perfil}" # ...y ahora pega el análisis físico final abajo de la foto
                            })
                        threading.Thread(target=hilo_forense, daemon=True).start() # Manda a ese mini-trabajador a empezar ya
                        
                    elif accion == "falsa":   # Si el guardia apretó el botón de Falsa Alarma (era una persona inocente)...
                        print(f"[TELEGRAM] Guardia reporta FALSA ALARMA para alerta {alerta_id}. Aplicando privacidad absoluta.") # ...avisa que protegerán al cliente
                        supabase.table("alertas").update({ # Cambia la base de datos...
                            "estado_validacion": "falsa_alarma", # ...marca el evento como error...  
                            "imagen_url": None  # ...y BORRA el link de la foto para proteger su identidad
                        }).eq("id", alerta_id).execute()
                        
                        try:                  # Intenta hacer limpieza profunda:
                            supabase.storage.from_("evidencia_biometrica").remove([nombre_archivo]) # Borra el archivo físico JPG de la nube de forma permanente
                            print(f"[STORAGE] Archivo {nombre_archivo} eliminado de Supabase Storage de forma definitiva.") # Confirma que se eliminó
                        except Exception as storage_err: # Si falla el borrado...
                            print(f"[STORAGE] Advertencia al borrar del storage: {storage_err}") # ...avisa del error
                        
                        url_delete = f"{TELEGRAM_API_URL}/deleteMessage" # Prepara una orden destructiva para Telegram
                        res_del = requests.post(url_delete, json={ # Le ordena a Telegram que elimine el mensaje entero
                            "chat_id": chat_id, # ...en este grupo...
                            "message_id": msg_id, # ...y borre este mensaje con foto incluida
                        })
                        
                        if res_del.status_code == 200: # Si Telegram lo borró con éxito...
                            print(f"[PRIVACIDAD] Mensaje {msg_id} y foto eliminados de Telegram.") # ...celebra la protección de datos
                        
            time.sleep(0.5)                   # Descansa medio segundo antes de volver a preguntarle a Telegram
        except Exception as e:                # Si Telegram se cae por completo...
            print(f"Error en bucle de polling Telegram: {e}") # ...avisa del error...
            time.sleep(3)                     # ...y espera 3 segundos para no quemar el servidor antes de reintentar

# ==========================================
# MOTOR BIOMÉTRICO LOCAL (EDGE)
# ==========================================
def bucle_vigilancia():                       # Este es el verdadero corazón del programa. Mira, analiza y juzga todo el tiempo.
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo, modo_reposicion # Trae a la memoria las variables generales importantes
    
    cap = CamaraAsincrona(fuente_video)       # Pide al trabajador de la cámara que empiece a mandarle el video en vivo
    frame_buffer = []                         # Una memoria a corto plazo para guardar los últimos segunditos de video
    
    stock_esperado = {73: 1, "BOTELLA": 1}    # Lo que debería haber en la repisa (1 libro o 1 botella)
    frames_ocultamiento_confirmado = 0        # Un contador de tiempo que mide cuánto rato lleva escondiendo las manos
    UMBRAL_GATILLO = 20                       # Si esconde las manos por 20 "fotos" seguidas, es un robo seguro
    TIEMPO_COOLDOWN = 15.0                    # Tiempo de enfriamiento: Espera 15 segundos antes de mandar otra alarma al celular

    FRAME_ACTUAL = 0                          # Un contador general de todo lo que ha visto
    FRAMES_DE_CALENTAMIENTO = 60              # Tiempo de ceguera inicial para que la cámara enfoque y aclare la imagen
    
    frames_desde_ultimo_qr = 999              # Tiempo transcurrido desde que vio una credencial válida
    UMBRAL_MEMORIA_QR = 90                    # Le da 90 fotogramas (aprox 3 segundos) de gracia al reponedor si se da vuelta y tapa su QR

    print("[SISTEMA] SmartGuard Biometrico Preciso Activado.") # ¡El centinela está vivo y mirando!

    while cap.corriendo and sistema_activo:   # Mientras el sistema y la cámara estén encendidos...
        success, frame = cap.read()           # ...pide la foto más actual a la cámara
        if not success:                       # Si la cámara tiró error...
            time.sleep(0.03)                  # ...espera un poquito...
            continue                          # ...y vuelve a pedirle foto

        frame = cv2.resize(frame, (640, 480)) # Achica la imagen para que el cerebro de IA analice todo más rápido
        
        FRAME_ACTUAL += 1                     # Suma 1 al historial de fotos vistas
        if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO: # Si todavía estamos en los primeros segundos de calentamiento...
            cv2.putText(frame, "CALIBRANDO SENSORES OPTICOS...", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2) # ...escribe en amarillo que está calentando
            with lock_frame:                  # ...asegura la memoria...
                ultimo_frame_procesado = frame.copy() # ...y guarda la imagen para que el frontend la muestre
            time.sleep(0.03)                  # ...descansa...
            continue                          # ...y salta todo el análisis de abajo porque aún no está listo

        frame_buffer.append(frame.copy())     # Guarda esta foto en la memoria corta
        if len(frame_buffer) > 30: frame_buffer.pop(0) # Si hay más de 30 fotos viejas, borra la más antigua

        # ========================================================
        # FASE EXTRA: ESCÁNER AUTÓNOMO DE CREDENCIAL QR  
        # ========================================================
        data_qr, bbox_qr, _ = qr_detector.detectAndDecode(frame) # Busca si hay códigos QR dibujados en la pantalla
        
        if data_qr == "STAFF_SMARTGUARD":     # Si encontró un QR válido que diga la contraseña secreta...
            frames_desde_ultimo_qr = 0        # ...reinicia el contador de gracia a cero
            modo_reposicion = True            # ...y activa el modo "Soy trabajador, no dispares"
            
            if bbox_qr is not None and len(bbox_qr) > 0: # Si además de leer el código sabe dónde está dibujado...
                pts = bbox_qr[0].astype(int)  # ...saca las esquinas del cuadrito
                for i in range(4):            # ...y dibuja un marco verde tecnológico alrededor del QR
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i+1)%4]), (0, 255, 0), 2)
                cv2.putText(frame, "STAFF VERIFICADO", (pts[0][0], pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2) # ...y le pone un título bonito encima
        else:                                 # Si no hay ningún código QR a la vista...
            frames_desde_ultimo_qr += 1       # ...empieza a correr el reloj en contra del reponedor
            if frames_desde_ultimo_qr > UMBRAL_MEMORIA_QR: # ...si pasa mucho rato sin ver su QR...
                modo_reposicion = False       # ...le quita la inmunidad y vuelve a tratarlo como un cliente sospechoso

        # ========================================================
        # INTERRUPTOR LOGÍSTICO DE COMPORTAMIENTO
        # ========================================================
        if modo_reposicion:                   # Si estamos con inmunidad de trabajador...
            frames_ocultamiento_confirmado = 0 # ...olvida cualquier actitud sospechosa previa
            color_ui = (0, 140, 255)          # ...cambia los dibujos de la pantalla a color Naranjo Corporativo
            mensaje = f"MODO REPOSICION: VIGILANCIA PASIVA ({max(0, (UMBRAL_MEMORIA_QR - frames_desde_ultimo_qr)//30)}s)" # ...escribe un mensaje avisando cuántos segundos de inmunidad le quedan
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2) # ...y lo pega en la pantalla
            
            cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (0, 140, 255), 1) # Pinta el estante naranjo
            with lock_frame:                  # ...bloquea la variable compartida...
                ultimo_frame_procesado = frame.copy() # ...y guarda la imagen para mostrarla en el Dashboard
            time.sleep(0.01)                  # ...descansa un pelito...
            continue                          # ...y SALTA TODO EL ANÁLISIS DE SEGURIDAD de abajo (es la ventaja de ser staff)

        # --- FLUJO NORMAL DE SEGURIDAD ---
        manos_en_peligro = False              # Bandera: asume que las manos se portan bien
        persona_presente = False              # Bandera: asume que la tienda está vacía

        results_pose = model_pose(frame, stream=True, verbose=False, conf=0.5) # Le manda la foto a la IA para que detecte huesos y articulaciones
        
        for r in results_pose:                # Por cada persona detectada en la imagen...
            if r.keypoints is not None and len(r.keypoints.xy) > 0: # ...si realmente encontró puntos clave válidos...
                kpts = r.keypoints.xy[0].cpu().numpy() # ...los extrae a una lista matemática
                if len(kpts) >= 13:           # ...y si al menos encontró la mitad superior del cuerpo...
                    persona_presente = True   # ...avisa que hay alguien frente a la cámara
                    l_sh, r_sh = kpts[5], kpts[6] # ...busca dónde están los hombros (izquierdo y derecho)
                    l_wrist, r_wrist = kpts[9], kpts[10] # ...busca dónde están las muñecas
                    l_hip, r_hip = kpts[11], kpts[12] # ...busca dónde están las caderas

                    distancia_hombros = abs(l_sh[0] - r_sh[0]) # Mide qué tan ancho es el cliente
                    centro_x = (l_sh[0] + r_sh[0]) / 2.0 # Encuentra exactamente la mitad de su pecho
                    
                    min_x_torso = centro_x - (distancia_hombros * 0.35) # Dibuja la pared izquierda de una caja imaginaria alrededor del cuerpo
                    max_x_torso = centro_x + (distancia_hombros * 0.35) # Dibuja la pared derecha de la caja imaginaria 
                    min_y_torso = min(l_sh[1], r_sh[1]) + 20 # Dibuja el techo de la caja (cerca del cuello)
                    max_y_torso = max(l_hip[1], r_hip[1]) - 20 # Dibuja el piso de la caja (cerca de la cintura)
                    
                    radio_bolsillo = 35       # Tamaño en píxeles de los círculos que representarán los bolsillos
                    offset_y = 10             # Mueve los círculos de los bolsillos un poquito más abajo de la cadera real
                    
                    bolsillo_izq_x = l_hip[0] # Centro horizontal del bolsillo izquierdo
                    bolsillo_der_x = r_hip[0] # Centro horizontal del bolsillo derecho
                    bolsillo_izq_y = l_hip[1] + offset_y # Centro vertical del bolsillo izquierdo
                    bolsillo_der_y = r_hip[1] + offset_y # Centro vertical del bolsillo derecho

                    if min_x_torso > 0 and min_y_torso > 0: # Si la persona está bien cuadrada en la cámara...
                        cv2.rectangle(frame, (int(min_x_torso), int(min_y_torso)), (int(max_x_torso), int(max_y_torso)), (255, 255, 255), 1) # ...dibuja en la pantalla la caja blanca del torso
                        cv2.circle(frame, (int(bolsillo_izq_x), int(bolsillo_izq_y)), radio_bolsillo, (0, 165, 255), 1) # ...dibuja el círculo del bolsillo izquierdo
                        cv2.circle(frame, (int(bolsillo_der_x), int(bolsillo_der_y)), radio_bolsillo, (0, 165, 255), 1) # ...dibuja el círculo del bolsillo derecho

                    for wrist in [l_wrist, r_wrist]: # Ahora, analiza por separado la muñeca izquierda y la derecha:
                        wx, wy = wrist        # Anota la posición X e Y de la muñeca
                        if wx > 0 and wy > 0: # Si la cámara realmente está viendo la muñeca (y no está escondida tras algo gigante)...
                            en_torso = (min_x_torso <= wx <= max_x_torso) and (min_y_torso <= wy <= max_y_torso) # ...pregunta: ¿la mano está tocando el pecho/guata?
                            dist_bolsillo_izq = math.hypot(wx - bolsillo_izq_x, wy - bolsillo_izq_y) # ...mide con regla imaginaria la distancia al bolsillo izquierdo
                            dist_bolsillo_der = math.hypot(wx - bolsillo_der_x, wy - bolsillo_der_y) # ...mide con regla imaginaria la distancia al bolsillo derecho
                            en_bolsillo = (dist_bolsillo_izq < radio_bolsillo) or (dist_bolsillo_der < radio_bolsillo) # ...pregunta: ¿la mano cruzó el perímetro del círculo de algún bolsillo?

                            if en_torso or en_bolsillo: # Si tiene la mano en la guata (ocultando algo) o metida en el bolsillo...
                                manos_en_peligro = True # ...¡Levanta la bandera roja!
                                cv2.circle(frame, (int(wx), int(wy)), 8, (0, 0, 255), -1) # ...y pinta la muñeca de color ROJO
                            else:             # Si tiene los brazos normales a los lados...
                                cv2.circle(frame, (int(wx), int(wy)), 6, (0, 255, 0), -1) # ...pinta la muñeca de VERDE, todo en orden

        obj_results = model_obj.track(frame, persist=True, conf=0.30, verbose=False) # Al mismo tiempo, le pasa la foto a la OTRA IA para que cuente los objetos
        conteo_actual = {73: 0, "BOTELLA": 0} # Inicializa los contadores de la repisa en cero
        
        if obj_results[0].boxes.id is not None: # Si la IA logró detectar cosas concretas...
            clases_obj = obj_results[0].boxes.cls.cpu().numpy().astype(int) # ...saca el número de categoría (ej. 39 es botella)
            boxes_obj = obj_results[0].boxes.xyxy.cpu().numpy().astype(int) # ...saca las coordenadas del objeto

            for box, cls in zip(boxes_obj, clases_obj): # Por cada objeto y su tipo...
                x1, y1, x2, y2 = box          # ...saca los puntos para dibujar un rectángulo sobre la botella
                toca_estante = not (x2 < ESTANTE_ROI[0] or x1 > ESTANTE_ROI[2] or y2 < ESTANTE_ROI[1] or y1 > ESTANTE_ROI[3]) # ...analiza geométricamente si el producto sigue dentro de la repisa (ROI)

                if cls in [73, 67]:           # Si es un objeto genérico...
                    conteo_actual[73] += 1    # ...suma 1 a la lista
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2) # ...lo dibuja verde si está en el estante, o amarillo si se lo llevaron
                elif cls in [39, 64]:         # Si la IA sabe específicamente que es una botella o taza...
                    conteo_actual["BOTELLA"] += 1 # ...suma 1 al contador de botellas
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if toca_estante else (0, 255, 255), 2) # ...la dibuja de color según dónde esté

        hay_faltante = (conteo_actual[73] < stock_esperado[73]) or (conteo_actual["BOTELLA"] < stock_esperado["BOTELLA"]) # Revisa las matemáticas: ¿Hay menos objetos que el stock esperado?

        # LÓGICA CORE DE SMARTGUARD (El cerebro tomador de decisiones)
        if persona_presente:                  # Si hay un cliente...
            if hay_faltante and manos_en_peligro: # Y además se perdió un producto Y además tiene las manos sospechosas...
                frames_ocultamiento_confirmado += 1 # ...empieza a llenar la barra de peligro sumando tiempo
                color_ui = (0, 0, 255)        # ...prepara letras color rojo sangre
                mensaje = "ALERTA BIOMETRICA: OCULTAMIENTO" # ...prepara el título del delito
            elif hay_faltante and not manos_en_peligro: # Si falta un producto PERO sus manos están a la vista de todos...
                frames_ocultamiento_confirmado = 0 # ...es un comprador normal caminando, reinicia el peligro a cero
                color_ui = (255, 255, 0)      # ...prepara letras amarillas
                mensaje = "CLIENTE SOSTENIENDO OBJETO" # ...y avisa que está vitrineando
            else:                             # Si no falta nada...
                frames_ocultamiento_confirmado = 0 # ...relaja el nivel de peligro
                color_ui = (0, 255, 0)        # ...letras verdes
                mensaje = "STOCK SEGURO"      # ...todo pacífico
            
            if frames_ocultamiento_confirmado >= UMBRAL_GATILLO: # Si la barra de peligro se llenó por esconder el producto mucho rato...
                tiempo_actual = time.time()   # ...mira la hora exacta
                if (tiempo_actual - ultimo_disparo) > TIEMPO_COOLDOWN: # ...y si no ha mandado alarmas en los últimos 15 segundos...
                    print("[GATILLO BIOMETRICO] Despachando evidencia local...") # ...Grita por consola
                    frame_copia = frame.copy() # ...saca una fotocopia impecable del cuadro actual
                    threading.Thread(target=procesar_y_despachar_sospecha, args=(frame_copia,), daemon=True).start() # ...le tira la foto a un trabajador nuevo para que llame a la policía por Telegram sin pausar el video
                    ultimo_disparo = tiempo_actual # ...anota la hora en que mandó la alarma
                    time.sleep(5.0)           # ...respira profundo por 5 segundos para que la cámara no se sature procesando el robo
                frames_ocultamiento_confirmado = 0 # ...vuelve la barra de peligro a cero para buscar el siguiente robo
                
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2) # Pega el gran letrero de estado arriba a la izquierda
        else:                                 # Si la tienda está vacía...
            frames_ocultamiento_confirmado = 0 # ...la barra de robo está en cero
            cv2.putText(frame, "MONITOREO PASIVO...", (10, 35), 1, 1.2, (255, 255, 255), 2) # ...y letrero blanco de aburrimiento

        cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1) # Vuelve a dibujar la línea del estante en amarillo pálido
        
        with lock_frame:                      # Cierra la puerta con seguro temporalmente...
            ultimo_frame_procesado = frame.copy() # ...y guarda este fotograma terminado, lleno de dibujos IA, para que FastAPI se lo muestre a React

        time.sleep(0.01)                      # Pequeña micro-siesta para darle ritmo al bucle

    cv2.destroyAllWindows()                   # Cierra cualquier ventana que haya quedado abierta si se apaga el sistema
    cap.release()                             # Apaga y suelta el cable de la cámara amigablemente

# ==========================================
# CONTROL DE CICLO DE VIDA DEL SERVIDOR
# ==========================================
@app.on_event("startup")                      # Cuando prendas el servidor con Uvicorn...
def iniciar_servicios_segundo_plano():        # ...ejecuta esta función automáticamente
    threading.Thread(target=bucle_vigilancia, daemon=True).start() # ...y enciende el corazón biométrico en segundo plano
    threading.Thread(target=bucle_telegram_polling, daemon=True).start() # ...y manda a despertar al vigilante de Telegram

@app.on_event("shutdown")                     # Cuando presiones Ctrl+C para matar el servidor...
def apagar_sistema():                         # ...haz esto rápido antes de morir
    global sistema_activo                     # ...avisa a todo el mundo...
    print("[SISTEMA] Cerrando motores y cortando energia...") # ...grita por consola...
    sistema_activo = False                    # ...baja el interruptor general para que las cámaras y los ciclos "While" se detengan
    os._exit(0)                               # ...y finaliza el proceso de Python con un corte de guillotina limpio

# ==========================================
# ENDPOINTS ADICIONALES LOGÍSTICOS
# ==========================================
@app.post("/api/reposicion/toggle")           # Una puerta web para que el Dashboard o el celular active el modo reposición a mano
def toggle_modo_reposicion():                 
    global modo_reposicion                    # Busca la variable logística...
    modo_reposicion = not modo_reposicion     # ...y si estaba en falso, la pone en verdadero (como un botón de on/off)
    return {"status": "success", "modo_reposicion_activo": modo_reposicion} # ...y responde con cara feliz que lo hizo

@app.get("/api/reposicion/status")            # Una ventana web solo para mirar en qué estado está la repisa
def obtener_estado_reposicion():              
    global modo_reposicion                    
    return {"modo_reposicion_activo": modo_reposicion} # Responde "Sí, reponiendo" o "No, asegurado"

# ==========================================
# STREAMING ENDPOINT
# ==========================================
async def generar_frames_mjpeg():             # El proyector de cine que empuja las fotos hacia el Dashboard de Vercel
    global ultimo_frame_procesado, sistema_activo 
    try:                                      # Intenta trabajar...
        while sistema_activo:                 # ...mientras estemos en turno
            frame_a_enviar = None             # ...parte con las manos vacías
            
            with lock_frame:                  # ...abre la puerta con llave rápido...
                if ultimo_frame_procesado is not None: # ...si hay un frame listo desde el motor biométrico...
                    frame_a_enviar = ultimo_frame_procesado.copy() # ...saca una copia rápido y cierra la puerta
            
            if frame_a_enviar is None:        # Si no había frame (por ej, cámara desenchufada)...
                frame_a_enviar = np.zeros((480, 640, 3), dtype=np.uint8) # ...crea un lienzo negro de 640x480 usando Matemáticas...
                cv2.putText(frame_a_enviar, "Buscando senal de camara...", (100, 240), # ...y le dibuja unas letras amarillas de auxilio
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame_a_enviar, "Por favor espere.", (220, 280), # ...con un subtítulo piola
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            ret, buffer = cv2.imencode('.jpg', frame_a_enviar) # Comprime esa foto para no gastar todo el internet del servidor
            if ret:                           # Si logró comprimirla...
                bytes_imagen = buffer.tobytes() # ...la vuelve lenguaje binario
                yield (b'--frame\r\n'         # ...y usa esta palabra clave mágica ("--frame") para que Google Chrome entienda que es un video en vivo y no una imagen plana
                       b'Content-Type: image/jpeg\r\n\r\n' + bytes_imagen + b'\r\n') # ...y pega la imagen en la pantalla del usuario
            await asyncio.sleep(0.04)         # ...descansa 0.04 segundos (aprox 25 fotogramas por segundo) para dar un video fluido sin explotar
    except asyncio.CancelledError:            # Si el humano cerró la pestaña de Chrome de golpe...
        pass                                  # ...no entres en pánico, simplemente hazte el loco y deja de emitir

@app.get("/video_feed")                       # La dirección principal del cine web. Aquí apunta React.
def video_feed():                             
    return StreamingResponse(generar_frames_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame") # Conecta la orden web con el proyector que creamos arriba

@app.get("/")                                 # La puerta principal de la casa, sirve para tocar la puerta y ver si hay alguien vivo
def health_check():                           
    return {"status": "online"}               # El servidor responde "¡ESTOY VIVO!" (súper útil para Render)