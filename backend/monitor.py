import cv2
from ultralytics import YOLO
import requests
import time
import numpy as np

# Configuración
API_URL = "http://127.0.0.1:8000/analizar/1"
model_obj = YOLO('yolov8n.pt')      
model_pose = YOLO('yolov8n-pose.pt') 

ESTANTE_ROI = [450, 100, 630, 450] 

cap = cv2.VideoCapture(0)
frame_buffer = []
last_analysis_time = 0

# --- NUEVOS PARÁMETROS DE INGENIERÍA ---
frames_desaparecido = 0 
UMBRAL_ROBO = 45 # Aumentamos a 45 frames (~1.5 a 2 segundos de "espera")
objeto_es_de_la_tienda = False 
visto_fuera_del_estante = 0 # Para asegurar que realmente lo tienes en la mano

print("🛡️ SmartGuard Pro: Filtro de manipulación activo. Tolerancia 2s.")

while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    frame_buffer.append(frame.copy())
    if len(frame_buffer) > 60: frame_buffer.pop(0) 

    # 1. ¿Hay alguien?
    pose_results = model_pose(frame, stream=True, verbose=False)
    persona_presente = any(r.keypoints is not None and len(r.keypoints.xy) > 0 for r in pose_results)

    # 2. Rastrear Objeto
    obj_results = model_obj(frame, stream=True, verbose=False, conf=0.3, imgsz=640)
    objeto_ahora_visible = False
    
    for res in obj_results:
        for box in res.boxes:
            cls = int(box.cls[0])
            if cls in [67, 73]: # Kindle/Libro
                objeto_ahora_visible = True
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Check: ¿Está en el estante o ya salió?
                en_estante = (x1 > ESTANTE_ROI[0] and x1 < ESTANTE_ROI[2]) and (y1 > ESTANTE_ROI[1] and y1 < ESTANTE_ROI[3])
                
                if en_estante:
                    objeto_es_de_la_tienda = True
                    visto_fuera_del_estante = 0 # Reset si vuelve al estante
                else:
                    if objeto_es_de_la_tienda:
                        visto_fuera_del_estante += 1 # Contamos cuánto tiempo lo llevas en la mano

                color = (0, 255, 255) if en_estante else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # --- LÓGICA DE DISPARO CON PACIENCIA ---
    if objeto_es_de_la_tienda and persona_presente:
        # Si el objeto no se ve...
        if not objeto_ahora_visible:
            # Y SOLO si ya lo habíamos visto fuera del estante (confirmación de posesión)
            if visto_fuera_del_estante > 5:
                frames_desaparecido += 1
                
                # Dibujar barra de carga de sospecha (Visual Feedback)
                progreso = int((frames_desaparecido / UMBRAL_ROBO) * 200)
                cv2.rectangle(frame, (10, 400), (10 + progreso, 430), (0, 0, 255), -1)
                cv2.putText(frame, "VALIDANDO OCULTAMIENTO...", (10, 390), 1, 1, (0, 0, 255), 2)

                if frames_desaparecido > UMBRAL_ROBO:
                    if time.time() - last_analysis_time > 20:
                        print("🚨 ROBO CONFIRMADO: El objeto desapareció permanentemente.")
                        cv2.imwrite("evidencia.jpg", frame_buffer[0]) # Foto de hace 2 segundos
                        requests.post(API_URL, files={'file': open("evidencia.jpg", 'rb')})
                        last_analysis_time = time.time()
                        objeto_es_de_la_tienda = False 
                        frames_desaparecido = 0
        else:
            # Si el objeto reaparece antes del umbral, TODO SE RESETEA. No hay robo.
            frames_desaparecido = 0

    # UI
    cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1)
    cv2.imshow("SmartGuard - Anti-Falsos Positivos", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()