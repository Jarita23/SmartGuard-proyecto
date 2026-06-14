# Importamos la librería 'os' para poder interactuar con las variables de entorno de nuestro sistema.
import os
# Importamos 'load_dotenv' para leer y cargar las credenciales que configuramos en nuestro archivo .env.
from dotenv import load_dotenv
# Importamos el módulo 'genai' de Google para conectar nuestro sistema con los modelos de inteligencia artificial.
from google import genai

# Ejecutamos la función que carga nuestras variables de entorno en la memoria para que el código pueda usarlas.
load_dotenv()
# Inicializamos el cliente de conexión, pasándole de forma segura nuestra API Key de Google obtenida del sistema.
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Imprimimos en la consola un encabezado visual para separar y dar contexto a los datos que vamos a mostrar.
print("--- LISTADO DE MODELOS DISPONIBLES EN TU CUENTA ---")
# Iniciamos un bloque de control de errores para evitar que el programa se caiga si falla la conexión a la API.
try:
    # Recorremos uno por uno todos los modelos de IA a los que tenemos acceso para usar en nuestro proyecto.
    for model in client.models.list():
        # Solo imprimimos el nombre, que es lo que necesitamos para api.py
        # Mostramos en pantalla el nombre exacto de cada modelo para saber cuáles podemos integrar en nuestra API.
        print(f"-> {model.name}")
# Si ocurre algún problema en el proceso anterior, atrapamos el error y lo guardamos en la variable 'e'.
except Exception as e:
    # Imprimimos un mensaje de alerta indicando que falló la conexión, junto con el detalle técnico del error.
    print(f"Error al conectar con Google: {e}")