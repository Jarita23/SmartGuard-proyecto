import cv2
from ultralytics import YOLO
import requests
import time

# --- CONFIGURACIÓNES ---
API_URL = "http://127.0.0.1:8000/analizar/1"
model_obj = YOLO('yolov8n.pt')      
model_pose = YOLO('yolov8n-pose.pt') 

# [x1, y1, x2, y2]
ESTANTE_ROI = [450, 100, 630, 450] 

cap = cv2.VideoCapture(0)
frame_buffer = []
last_analysis_time = 0

# --- PARÁMETROS DE INVENTARIO (FLEXIBLES) ---
stock_esperado = {73: 1, "BOTELLA": 1} 
frames_desaparicion = 0 
UMBRAL_ROBO = 70 

# Memoria de presencia
frames_presencia_memoria = 0 
MEMORIA_POSE_GRACIA = 30     

# --- NUEVAS VARIABLES DE CALENTAMIENTO ---
FRAME_ACTUAL = 0
FRAMES_DE_CALENTAMIENTO = 90  # ~3 segundos de espera inicial

print("🛡️ SmartGuard Pro: Sistema CONECTADO a la API. Vigilancia activa.")

while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    FRAME_ACTUAL += 1

    # 1. FASE DE CALENTAMIENTO (Evita el gatillo fácil al inicio)
    if FRAME_ACTUAL < FRAMES_DE_CALENTAMIENTO:
        cv2.putText(frame, "CALIBRANDO SENSORES...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow("SmartGuard Pro - Dashboard Link", frame)
        cv2.waitKey(1)
        continue  # Salta directo al siguiente frame sin analizar robos

    frame_buffer.append(frame.copy())
    if len(frame_buffer) > 90: frame_buffer.pop(0) 

    # 2. ¿Hay alguien?
    results_pose = model_pose(frame, stream=True, verbose=False)
    pose_detectada_este_frame = any(r.keypoints is not None and len(r.keypoints.xy) > 0 for r in results_pose)

    if pose_detectada_este_frame:
        frames_presencia_memoria = MEMORIA_POSE_GRACIA
        persona_presente_suavizada = True
    else:
        frames_presencia_memoria = max(0, frames_presencia_memoria - 1)
        persona_presente_suavizada = frames_presencia_memoria > 0

    # 3. Rastrear y Contar
    obj_results = model_obj.track(frame, persist=True, conf=0.25, verbose=False)
    
    conteo_actual = {73: 0, "BOTELLA": 0}
    objeto_visto_fuera = False 
    
    if obj_results[0].boxes.id is not None:
        clases_obj = obj_results[0].boxes.cls.cpu().numpy().astype(int)
        boxes_obj = obj_results[0].boxes.xyxy.cpu().numpy().astype(int)

        for box, cls in zip(boxes_obj, clases_obj):
            x1, y1, x2, y2 = box
            toca_estante = not (x2 < ESTANTE_ROI[0] or x1 > ESTANTE_ROI[2] or y2 < ESTANTE_ROI[1] or y1 > ESTANTE_ROI[3])

            if cls == 0: # Persona
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)
            
            elif cls == 73 or cls == 67: # Libro o Kindle
                if toca_estante:
                    conteo_actual[73] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                else:
                    objeto_visto_fuera = True
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

            elif cls == 39 or cls == 64: # Botella o Planta
                if toca_estante:
                    conteo_actual["BOTELLA"] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                else:
                    objeto_visto_fuera = True
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

    # 4. --- LÓGICA DE FALTANTES ---
    hay_faltante = (conteo_actual[73] < stock_esperado[73]) or (conteo_actual["BOTELLA"] < stock_esperado["BOTELLA"])

    # 5. --- DECISIÓN ---
    if persona_presente_suavizada:
        if hay_faltante and not objeto_visto_fuera:
            frames_desaparicion += 1
            color_ui, mensaje = (0, 0, 255), "SOSPECHA: OBJETO OCULTO"
        elif hay_faltante and objeto_visto_fuera:
            frames_desaparicion = max(0, frames_desaparicion - 10)
            color_ui, mensaje = (255, 255, 0), "CLIENTE REVISANDO"
        else:
            frames_desaparicion = max(0, frames_desaparicion - 20)
            color_ui, mensaje = (0, 255, 0), "STOCK SEGURO"

        # UI
        cv2.putText(frame, mensaje, (10, 35), 1, 1.3, color_ui, 2)
        txt_stock = f"Libro: {conteo_actual[73]}/1 | Botella: {conteo_actual['BOTELLA']}/1"
        cv2.putText(frame, txt_stock, (10, 65), 1, 1, (255, 255, 255), 1)

        if frames_desaparicion > 5:
            progreso = int((frames_desaparicion / UMBRAL_ROBO) * 200)
            cv2.rectangle(frame, (10, 400), (10 + min(progreso, 200), 430), (0, 0, 255), -1)

        # --- DISPARO DE ALERTA (ENVÍO REAL) ---
        if frames_desaparicion > UMBRAL_ROBO:
            if time.time() - last_analysis_time > 15:
                print("🚨 ALERTA: Faltante confirmado. Enviando evidencia...")
                cv2.imwrite("evidencia.jpg", frame_buffer[0]) 
                
                try:
                    with open("evidencia.jpg", 'rb') as f:
                        response = requests.post(API_URL, files={'file': f})
                    if response.status_code == 200:
                        print("✅ Alerta enviada con éxito a Supabase.")
                    else:
                        print(f"⚠️ API respondió con error: {response.status_code}")
                except Exception as e:
                    print(f"❌ No se pudo conectar con la API: {e}")

                last_analysis_time = time.time()
                frames_desaparicion = 0
    else:
        # CORRECCIÓN VITAL: Si no hay nadie, reiniciamos la sospecha a cero
        frames_desaparicion = 0
        cv2.putText(frame, "MONITOREO PASIVO...", (10, 35), 1, 1.3, (255, 255, 255), 2)

    cv2.rectangle(frame, (ESTANTE_ROI[0], ESTANTE_ROI[1]), (ESTANTE_ROI[2], ESTANTE_ROI[3]), (255, 255, 0), 1)
    cv2.imshow("SmartGuard Pro - Dashboard Link", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()