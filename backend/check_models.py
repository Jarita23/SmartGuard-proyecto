import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("--- LISTADO DE MODELOS DISPONIBLES EN TU CUENTA ---")
try:
    for model in client.models.list():
        # Solo imprimimos el nombre, que es lo que necesitamos para api.py
        print(f"-> {model.name}")
except Exception as e:
    print(f"Error al conectar con Google: {e}")