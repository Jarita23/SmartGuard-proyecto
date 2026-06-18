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
from fastapi import FastAPI                   # El motor web principal que permite que internet se conecte con este código
from fastapi.middleware.cors import CORSMiddleware # Un portero que decide qué páginas web externas tienen permiso para entrar

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
    "http://localhost:8000",
    "http://127.0.0.1:5173",                  # Se da permiso a sí mismo para funcionar
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
model_obj = YOLO(str(BASE_DIR / 'models' / 'yolov8m.pt')).to('cuda')# Carga el cerebro visual que sabe reconocer objetos cotidianos
model_pose = YOLO(str(BASE_DIR / 'models' / 'yolov8m-pose.pt')).to('cuda') # Carga el cerebro visual que sabe leer el esqueleto humano

qr_detector = cv2.QRCodeDetector()            # Enciende el escáner especial para leer los códigos QR del personal

ESTANTE_ROI = [950, 320, 1250, 640]            # Dibuja una caja imaginaria en la pantalla que define la zona de peligro (el estante)

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
            
        # 🚀 LA SOLUCIÓN DEL HARDWARE: Obligar a Windows a usar HD Panorámico sin recortes
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        self.ret, self.frame = self.cap.read() # Saca la primera foto de prueba (ahora será panorámica)
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
# 📐 MOTOR GEOMÉTRICO DE COLISIONES (AABB)
# ==========================================
def colision_cajas(box1, box2):
    """
    Detecta si dos recuadros se están tocando o superponiendo.
    Formatos esperados: [x1, y1, x2, y2]
    """
    # Calculamos los bordes de la zona de intersección
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    # Si el lado derecho de la intersección es mayor al izquierdo, y el inferior mayor al superior... hay choque.
    if x_right > x_left and y_bottom > y_top:
        return True
    return False


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
# MOTOR BIOMÉTRICO LOCAL (EDGE) - v6.1
#
# CAMBIOS vs v6.0:
#   [NEW] Inferencia en resolución reducida (320x240) para modelos M sin lag
#   [NEW] Escalado de coordenadas de vuelta a 640x480 para dibujar correctamente
#   [NEW] Opción 4: confianza de keypoints — si no ve las muñecas, congela la barra
#         en lugar de bajarla (evita que el ladrón escape girándose de lado)
#
# LÓGICA MAESTRA DE HURTO (posicional, no por conteo):
#   [1] memoria_toco_estante   → la mano tocó el ROI en algún momento
#   [2] faltante_en_estante    → la botella ya no está en la repisa
#   [3] not botella_visible_fuera → la botella no se ve en ningún otro lugar
#                                   (la ocultó bajo la ropa, no la sostiene visible)
# ==========================================
# ==========================================
# MOTOR BIOMÉTRICO LOCAL (EDGE) - v7.0
#
# CAMBIOS vs v6.1:
#   [FIX]  GPU forzada via .to('cuda') en los modelos (fuera del bucle, en server.py)
#   [NEW]  Detección de orientación lateral con ajuste dinámico del rectángulo de torso
#          y bolsillos hacia el borde frontal del cuerpo (no el centro)
#
# LÓGICA MAESTRA DE HURTO (posicional):
#   [1] memoria_toco_estante     → la mano tocó el ROI en algún momento
#   [2] faltante_en_estante      → la botella ya no está en la repisa
#   [3] not botella_visible_fuera → la botella no se ve en ningún lugar de la cámara
#
# ORIENTACIÓN:
#   Si distancia_hombros < 25% de altura torso → persona de lado
#   El torso y bolsillos se desplazan al borde frontal según el hombro más visible
# ==========================================
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo, modo_reposicion
 
    cap = CamaraAsincrona(fuente_video)
 
    # ---- RESOLUCIÓN (Panorámico 16:9 Real) ----
    INF_W, INF_H   = 640, 360  # La IA analiza en panorámico
    DISP_W, DISP_H = 1280, 720 # Se dibuja en panorámico gigante
    ESCALA_X = DISP_W / INF_W   
    ESCALA_Y = DISP_H / INF_H
 
    # ---- CONTADORES ----
    frames_ocultamiento_confirmado = 0
    UMBRAL_GATILLO          = 15
    TIEMPO_COOLDOWN         = 15.0
    FRAME_ACTUAL            = 0
    FRAMES_DE_CALENTAMIENTO = 60
 
    # ---- CONTROL QR ----
    frames_desde_ultimo_qr = 999
    UMBRAL_MEMORIA_QR       = 90
 
    # ---- MEMORIA DE ESTADO ----
    memoria_toco_estante = False
    frames_sin_faltante  = 0
    UMBRAL_PERDON        = 20
 
    # ---- CONFIANZA DE KEYPOINTS ----
    CONFIANZA_MIN_MUNECA = 0.4
 
    # ---- DETECCIÓN DE ORIENTACIÓN LATERAL ----
    UMBRAL_LADO = 0.38
 
    # ---- STOCK BASE ----
    stock_estante_congelado = 0
    frames_para_nuevo_stock = 0
 
    # ---- ESTILOS DE TEXTO UI ----
    fuente    = cv2.FONT_HERSHEY_DUPLEX
    suavizado = cv2.LINE_AA

    # ---- TAMAÑOS DE FUENTE PARA 1280x720 ----
    F_GRANDE  = 0.85   # Título principal (estado del sistema)
    F_MEDIO   = 0.65   # Subtítulo / HUD secundario
    F_PEQUEÑO = 0.50   # Etiquetas sobre bounding boxes
    GROSOR_TITULO = 2
    GROSOR_HUD    = 1

    # ---- POSICIONES Y DE TEXTO EN LA BARRA NEGRA (altura 80px) ----
    Y_LINEA_1 = 32     # Primera línea (estado principal)
    Y_LINEA_2 = 62     # Segunda línea (datos de stock / HUD)
    X_TEXTO   = 20     # Margen izquierdo de todos los textos
 
    # ---- ROI ESCALADO A RESOLUCIÓN DE INFERENCIA ----
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
 
        # 🚀 OPTIMIZACIÓN: Solo redimensiona el display si la cámara entrega un tamaño distinto a 1280x720
        if frame.shape[1] != DISP_W or frame.shape[0] != DISP_H:
            frame = cv2.resize(frame, (DISP_W, DISP_H))
            
        # Creamos la imagen de inferencia panorámica reducida para YOLO (640x360)
        frame_inf = cv2.resize(frame, (INF_W,  INF_H))
        FRAME_ACTUAL += 1
 
        # ========================================================
        # FASE 0: CALENTAMIENTO
        # ========================================================
        if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO:
            cv2.putText(frame, "CALIBRANDO SENSORES...", (X_TEXTO, Y_LINEA_1),
                        fuente, F_GRANDE, (0, 255, 255), GROSOR_TITULO, suavizado)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.03)
            continue
 
        # ========================================================
        # FASE 1: ESCÁNER QR
        # ========================================================
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
            memoria_toco_estante           = False
            frames_sin_faltante            = 0
            stock_estante_congelado        = 0
            cv2.rectangle(frame, (0, 0), (DISP_W, 80), (0, 0, 0), -1)
            cv2.putText(frame, "MODO REPOSICION: VIGILANCIA PASIVA",
                        (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 140, 255), GROSOR_TITULO, suavizado)
            cv2.rectangle(frame,
                          (ESTANTE_ROI[0], ESTANTE_ROI[1]),
                          (ESTANTE_ROI[2], ESTANTE_ROI[3]), (0, 140, 255), 1)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            time.sleep(0.01)
            continue
 
        # ========================================================
        # FASE 2: DETECCIÓN DE OBJETOS
        # ========================================================
        obj_results = model_obj.track(frame_inf, persist=True, conf=0.25, verbose=False)
 
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
 
                elif cls in [39, 41]:
                    if colision_cajas(box_inf_int, ROI_INF):
                        botellas_en_estante += 1
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (0, 255, 0), 2)
                    else:
                        botella_visible_fuera = True
                        cv2.rectangle(frame, (xd1, yd1), (xd2, yd2), (255, 165, 0), 2)
 
        if not persona_en_camara:
            memoria_toco_estante = False
            frames_sin_faltante  = 0
 
        cv2.rectangle(frame, (0, 0), (DISP_W, 80), (0, 0, 0), -1)
 
        # ========================================================
        # FASE 3: STOCK BASE (MÁXIMO HISTÓRICO CON ANTI-REBOTE)
        # ========================================================
        if botellas_en_estante > stock_estante_congelado:
            frames_para_nuevo_stock += 1
            if frames_para_nuevo_stock >= 10:
                stock_estante_congelado = botellas_en_estante
                frames_para_nuevo_stock = 0
                print(f"[STOCK] Nuevo maximo confirmado en estante: {stock_estante_congelado}")
        else:
            frames_para_nuevo_stock = 0
 
        # ========================================================
        # FASE 4: FALTANTE Y REGLA DE PERDÓN
        # ========================================================
        faltante_en_estante = (botellas_en_estante < stock_estante_congelado)
 
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
 
        # ========================================================
        # FASE 5: MÁQUINA DE ESTADOS
        # ========================================================
 
        # ESTADO 1: PASIVO
        if not faltante_en_estante and not memoria_toco_estante:
            if frames_ocultamiento_confirmado > 0:
                frames_ocultamiento_confirmado = max(0, frames_ocultamiento_confirmado - 2)
            cv2.putText(frame, "MONITOREO PASIVO...",
                        (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (255, 255, 255), GROSOR_TITULO, suavizado)
            cv2.putText(frame, f"STOCK BASE: {stock_estante_congelado} | EN REPISA: {botellas_en_estante}",
                        (X_TEXTO, Y_LINEA_2), fuente, F_MEDIO, (0, 255, 0), GROSOR_HUD, suavizado)
 
        # ESTADO 2: BIOMETRÍA ACTIVA
        else:
            results_pose = model_pose(frame_inf, stream=False, verbose=False, conf=0.5)
 
            for r in results_pose:
                if r.keypoints is None or len(r.keypoints.xy) == 0:
                    continue
 
                kpts      = r.keypoints.xy[0].cpu().numpy()
                kpts_conf = r.keypoints.conf[0].cpu().numpy()
 
                if len(kpts) < 13:
                    continue
 
                # ---- CONFIANZA DE MUÑECAS ----
                muneca_izq_ok       = kpts_conf[9]  > CONFIANZA_MIN_MUNECA
                muneca_der_ok       = kpts_conf[10] > CONFIANZA_MIN_MUNECA
                esqueleto_confiable = muneca_izq_ok or muneca_der_ok
 
                # ---- PUNTOS CLAVE (escala INF) ----
                l_sh,    r_sh    = kpts[5],  kpts[6]
                l_wrist, r_wrist = kpts[9],  kpts[10]
                l_hip,   r_hip   = kpts[11], kpts[12]
 
                # ---- MÉTRICAS CORPORALES BASE ----
                distancia_hombros  = abs(l_sh[0] - r_sh[0])
                dist_hombro_cadera = abs(min(l_sh[1], r_sh[1]) - max(l_hip[1], r_hip[1]))
                centro_x           = (l_sh[0] + r_sh[0]) / 2.0
                offset_y           = 5
                radio_bolsillo     = 18
 
                esta_de_lado = distancia_hombros < (dist_hombro_cadera * UMBRAL_LADO)
 
                if esta_de_lado:
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
                    # ---- MODO FRONTAL ----
                    min_x_torso = centro_x - (distancia_hombros * 0.35)
                    max_x_torso = centro_x + (distancia_hombros * 0.35)
                    min_y_torso = min(l_sh[1], r_sh[1]) + (dist_hombro_cadera * 0.4)
                    max_y_torso = max(l_hip[1], r_hip[1]) - 10
                    bolsillo_izq = (l_hip[0], l_hip[1] + offset_y)
                    bolsillo_der = (r_hip[0], r_hip[1] + offset_y)
 
                # ---- DIBUJO DE ZONAS (escalado a display) ----
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
 
                # ---- ANÁLISIS DE MUÑECAS ----
                for wrist, wrist_ok in [(l_wrist, muneca_izq_ok), (r_wrist, muneca_der_ok)]:
                    wx, wy = wrist
 
                    if wx <= 0 or wy <= 0 or not wrist_ok:
                        continue
 
                    en_estante  = colision_cajas([wx-3, wy-3, wx+3, wy+3], ROI_INF)
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
 
            # ---- GATILLO ANTI-PARPADEO ----
            if manos_en_peligro:
                frames_ocultamiento_confirmado += 1
                cv2.putText(frame,
                            f"ALERTA HURTO ({frames_ocultamiento_confirmado}/{UMBRAL_GATILLO})",
                            (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 0, 255), GROSOR_TITULO, suavizado)
 
            elif not esqueleto_confiable:
                cv2.putText(frame, "ESQUELETO PARCIAL: BARRA CONGELADA",
                            (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 100, 255), GROSOR_HUD, suavizado)
 
            else:
                frames_ocultamiento_confirmado = max(0, frames_ocultamiento_confirmado - 2)
 
                if faltante_en_estante and botella_visible_fuera:
                    cv2.putText(frame, "CLIENTE SOSTIENE PRODUCTO (SEGURO)",
                                (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (0, 255, 255), GROSOR_HUD, suavizado)
                elif faltante_en_estante and not botella_visible_fuera and memoria_toco_estante:
                    cv2.putText(frame, "ANALISIS ACTIVO: BUSCANDO MANOS",
                                (X_TEXTO, Y_LINEA_1), fuente, F_GRANDE, (255, 100, 0), GROSOR_HUD, suavizado)
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
 
        # ========================================================
        # FASE 6: GATILLO FINAL → TELEGRAM
        # ========================================================
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
        time.sleep(0.01)
 
    cap.release()                                                     # Apaga la cámara al terminar                                                             # Apaga la cámara al terminar el turno

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