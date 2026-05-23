import os
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
import re  # <-- Agregado para limpieza de respuestas JSON
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from ultralytics import YOLO

# Cargar variables de entorno (.env)
load_dotenv()

# Inicialización de Gemini y Supabase
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
from app.db.supabase_client import insert_alerta_row

app = FastAPI(
    title="SmartGuard AI - Biometric Engine",
    description="Sistema de análisis biomecánico anti-hurtos - v3.2",
    version="3.2.0"
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

def enviar_alerta_telegram(mensaje: str, imagen_bytes: bytes = None):
    try:
        if not imagen_bytes:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje})
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            archivos = {'photo': ('evidencia.jpg', imagen_bytes, 'image/jpeg')}
            datos = {'chat_id': TELEGRAM_CHAT_ID, 'caption': mensaje}
            res = requests.post(url, data=datos, files=archivos)
            
        print(f"📱 [TELEGRAM] Notificación de hurto enviada con éxito.")
    except Exception as e:
        print(f"❌ Error de red con Telegram: {e}")

# ==========================================
# 📡 VARIABLES GLOBALES Y CONTROL DE ESTADO
# ==========================================
model_obj = YOLO('yolov8n.pt')      
model_pose = YOLO('yolov8n-pose.pt') 

ESTANTE_ROI = [450, 100, 630, 450] 

fuente_env = os.getenv("WEBCAM_INDEX", "0")

if fuente_env.isdigit():
    fuente_video = int(fuente_env)
    print("📸 [HARDWARE] SmartGuard configurado en modo: WEBCAM INTEGRADA LOCAL.")
else:
    fuente_video = "rtsp://admin:L2BCD08A@192.168.1.22:554/cam/realmonitor?channel=1&subtype=0"
    print("📡 [HARDWARE] SmartGuard configurado en modo: CÁMARA IP DAHUA (RTSP).")

ultimo_frame_procesado = None
lock_frame = threading.Lock()
sistema_activo = True 
ultimo_disparo = 0.0  

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
                break

    def read(self):
        return self.ret, self.frame.copy() if self.ret else None

    def release(self):
        self.corriendo = False
        if self.hilo.is_alive():
            self.hilo.join(timeout=1.0)
        self.cap.release()

# ==========================================
# 🧠 PIPELINE DE COGNICIÓN EN LA NUBE (GEMINI)
# ==========================================
def ejecutar_analisis_alerta(frame_evidencia):
    print("🚨 [SISTEMA] Disparo Biométrico confirmado. Procesando evidencia...")
    try:
        ret, buffer = cv2.imencode('.jpg', frame_evidencia)
        if not ret: return
        request_object_content = buffer.tobytes()

        img = PIL.Image.open(io.BytesIO(request_object_content))

        print("🧠 [SISTEMA] Consultando al Juez Semántico...")
        prompt = """
        Eres el 'Juez Semántico' en la nube de SmartGuard, un sistema anti-robos de supermercado enfocado en licores.
        El modelo local YOLOv8 detectó que un producto desapareció y las manos del sujeto se movieron a una zona de ocultamiento.
        
        Tu única función es confirmar la intencionalidad de la persona en la foto.
        REGLAS ESTRICTAS:
        1. Si el cliente solo sostiene la botella de forma abierta y visible en sus manos para mirarla o examinarla, es una INTERACCIÓN NORMAL (Severidad baja).
        2. Si ves evidencia clara de que el sujeto está ocultando activamente la botella dentro de su polerón, vestimenta, mochila o bolso, es un ROBO EN PROGRESO (Severidad alta).

        Responde ESTRICTAMENTE en este formato JSON limpio, sin textos adicionales:
        {
            "etiqueta": "ROBO EN PROGRESO" o "INTERACCIÓN NORMAL",
            "descripcion": "Descripción táctica de máximo 15 palabras.",
            "severidad": "alta" o "baja"
        }
        """
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, img])
        
        text_response = response.text.strip()
        match = re.search(r'\{.*\}', text_response, re.DOTALL)
        clean_response = match.group(0) if match else text_response
            
        analisis_ia = json.loads(clean_response)
        severidad = analisis_ia.get("severidad", "baja").lower()
        etiqueta = analisis_ia.get("etiqueta", "").upper()

        # 🔥 🔥 FILTRO DE CONTENCIÓN CRÍTICO 🔥 🔥
        # Si la IA determina que es un cliente honesto revisando el producto, bloqueamos la alerta
        if severidad not in ["alta", "media"] or "NORMAL" in etiqueta:
            print(f"ℹ️ [SISTEMA] Falsa alarma filtrada con éxito: {analisis_ia.get('descripcion')} (Severidad: {severidad.upper()})")
            return  # Abortamos el flujo aquí. No se envía a Telegram ni a Supabase.

        # --- TODO LO DE ABAJO SÓLO SE EJECUTA SI ES UN ROBO CONFIRMADO ---
        print("☁️ [SISTEMA] Guardando evento de hurto en Supabase...")
        camara_id = 1
        resultado_final = {
            "camara_id": camara_id,
            "etiqueta": analisis_ia.get("etiqueta", "ROBO EN PROGRESO"),
            "descripcion": analisis_ia.get("descripcion", "Sin detalles"),
            "severidad": severidad,
            "tipo": "biometria_ia_3.2",
            "metadata": {"model": "gemini-2.5-flash", "filtro_seguridad": "activo"}
        }
        insert_alerta_row(resultado_final)

        print("📱 [SISTEMA] Despachando evidencia criminal a Telegram...")
        mensaje_tg = f"🚨 SMARTGUARD ALERT - Cámara {camara_id} 🚨\n\n⚠️ {resultado_final['etiqueta']}\n📝 {resultado_final['descripcion']}"
        enviar_alerta_telegram(mensaje_tg, request_object_content)
        print("✅ [SISTEMA] Alerta despachada limpiamente.")

    except Exception as e:
        print(f"❌ [SISTEMA] Error en procesamiento de nube: {e}")

# ==========================================
# 🛡️ MOTOR BIOMÉTRICO DE VIGILANCIA
# ==========================================
def bucle_vigilancia():
    global ultimo_frame_procesado, sistema_activo, ultimo_disparo
    
    cap = CamaraAsincrona(fuente_video)
    
    stock_esperado = {73: 1, "BOTELLA": 1} 
    frames_ocultamiento_confirmado = 0 
    UMBRAL_GATILLO = 20  
    TIEMPO_COOLDOWN = 15.0 

    FRAME_ACTUAL = 0
    FRAMES_DE_CALENTAMIENTO = 60  

    print("🛡️ SmartGuard Biométrico Preciso Activado.")

    while cap.corriendo and sistema_activo:
        success, frame = cap.read()
        if not success:
            time.sleep(0.03)
            continue

        frame = cv2.resize(frame, (640, 480))
        
        FRAME_ACTUAL += 1
        if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO:
            cv2.putText(frame, "CALIBRANDO SENSORES OPTICOS...", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            with lock_frame:
                ultimo_frame_procesado = frame.copy()
            cv2.imshow("SmartGuard Pro - Local View", frame)
            cv2.waitKey(1)
            time.sleep(0.03)
            continue

        manos_en_peligro = False
        persona_presente = False

        # --- FASE 1: ANÁLISIS ANATÓMICO (POSE) ---
        results_pose = model_pose(frame, stream=True, verbose=False, conf=0.5)
        
        for r in results_pose:
            if r.keypoints is not None and len(r.keypoints.xy) > 0:
                kpts = r.keypoints.xy[0].cpu().numpy()
                if len(kpts) >= 13: 
                    persona_presente = True
                    l_sh, r_sh = kpts[5], kpts[6]     
                    l_wrist, r_wrist = kpts[9], kpts[10] 
                    l_hip, r_hip = kpts[11], kpts[12]    

                    # 1. LA CAJA DEL TORSO
                    distancia_hombros = abs(l_sh[0] - r_sh[0])
                    centro_x = (l_sh[0] + r_sh[0]) / 2.0
                    
                    min_x_torso = centro_x - (distancia_hombros * 0.35)
                    max_x_torso = centro_x + (distancia_hombros * 0.35)
                    min_y_torso = min(l_sh[1], r_sh[1]) + 20 
                    max_y_torso = max(l_hip[1], r_hip[1]) - 20
                    
                    # 2. LOS BOLSILLOS
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

        # --- FASE 2: RASTREO DE INVENTARIO ---
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
                    color = (0, 255, 0) if toca_estante else (0, 255, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                elif cls in [39, 64]: 
                    conteo_actual["BOTELLA"] += 1
                    color = (0, 255, 0) if toca_estante else (0, 255, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # --- FASE 3: EL GATILLO MATEMÁTICO ---
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
                    frame_copia = frame.copy()
                    # Despachamos al análisis asíncrono
                    threading.Thread(target=ejecutar_analisis_alerta, args=(frame_copia,), daemon=True).start()
                    ultimo_disparo = tiempo_actual
                    time.sleep(1.0)
                    
                frames_ocultamiento_confirmado = 0
                
            cv2.putText(frame, mensaje, (10, 35), 1, 1.2, color_ui, 2)
        else:
            frames_ocultamiento_confirmado = 0
            cv2.putText(frame, "MONITOREO PASIVO...", (10, 35), 1, 1.2, (255, 255, 255), 2)

        cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1)
        
        with lock_frame:
            ultimo_frame_procesado = frame.copy()
            
        cv2.imshow("SmartGuard Pro - Local View", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        time.sleep(0.03) 

    print("🛑 Cámara liberada correctamente.")
    cv2.destroyAllWindows()
    cap.release()

# ==========================================
# ⚡ EVENTOS DEL SERVIDOR FASTAPI
# ==========================================
@app.on_event("startup")
def iniciar_hilo_vigilancia():
    t = threading.Thread(target=bucle_vigilancia, daemon=True)
    t.start()

@app.on_event("shutdown")
def apagar_sistema():
    global sistema_activo
    print("🛑 [SISTEMA] Orden de apagado manual (Ctrl+C). Cortando energía...")
    sistema_activo = False
    os._exit(0) 

# ==========================================
# 🛣️ ENDPOINTS WEB ASÍNCRONOS
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