# Documentación inicial que explica el propósito de este script y cómo debemos ejecutarlo en la terminal de nuestro proyecto.
"""
Lista modelos disponibles en la cuenta (Gemini API) para copiar el id exacto a GEMINI_MODEL.

Uso (desde la carpeta backend/):
  python list_models.py
"""

# Habilitamos características modernas de anotación de tipos de Python para mantener nuestro código más limpio y legible.
from __future__ import annotations

# Importamos 'sys' para poder manipular las rutas del sistema y asegurar que nuestras importaciones funcionen correctamente.
import sys
# Importamos 'Path' para manejar las rutas de los archivos de nuestro proyecto de forma segura sin importar el sistema operativo.
from pathlib import Path

# Calculamos la ruta absoluta exacta donde se encuentra este archivo dentro de la estructura de nuestro proyecto.
_ROOT = Path(__file__).resolve().parent
# Verificamos si la ruta raíz de nuestro proyecto ya está registrada en las rutas de búsqueda del sistema.
if str(_ROOT) not in sys.path:
    # Si no está, la agregamos al principio de la lista para que Python encuentre nuestros módulos locales sin problemas.
    sys.path.insert(0, str(_ROOT))

# Importamos el cliente oficial de Google para poder comunicarnos con los modelos de inteligencia artificial.
from google import genai

# Importamos las funciones personalizadas que creamos en nuestro proyecto para cargar y validar las variables de entorno.
from app.config.env_loader import load_environment, optional_env, require_env


# Definimos una función de apoyo interna para limpiar el nombre del modelo y dejar solo el ID que necesitamos usar.
def _short_model_id(full_name: str) -> str:
    # Quitamos los espacios en blanco que puedan venir al principio o al final del nombre original.
    n = full_name.strip()
    # Eliminamos el prefijo "models/" para dejar el texto limpio y lo retornamos listo para usar.
    return n.removeprefix("models/").strip()


# Definimos la función principal que contendrá toda la lógica de ejecución de este script en nuestro sistema.
def main() -> None:
    # Llamamos a nuestra función para cargar las configuraciones del archivo .env en la memoria del programa.
    load_environment()
    # Obtenemos nuestra clave de Google, exigiendo que exista; si falta, el sistema detendrá la ejecución aquí.
    api_key = require_env("GOOGLE_API_KEY")
    # Intentamos obtener la versión de la API configurada, o le asignamos "v1" por defecto si no pusimos ninguna.
    api_version = optional_env("GEMINI_API_VERSION", "v1").strip() or "v1"

    # Inicializamos el cliente de conexión pasándole nuestra clave de acceso y la versión específica de la API.
    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": api_version},
    )

    # Mostramos en pantalla qué versión de la API estamos utilizando para tener contexto al revisar la consola.
    print(f"API version: {api_version}\n")
    # Solicitamos a Google la lista de modelos, configurando la petición para que nos traiga hasta 100 resultados de una vez.
    pager = client.models.list(config={"page_size": 100, "query_base": True})

    # Iniciamos un contador en cero para ir enumerando ordenadamente los modelos que vamos a mostrar.
    n = 0
    # Recorremos uno por uno los modelos que nos devolvió la consulta a la API de Google.
    for m in pager:
        # Aumentamos nuestro contador en 1 por cada modelo procesado.
        n += 1
        # Guardamos el nombre técnico del modelo, o ponemos un texto de aviso si por alguna razón el nombre viene vacío.
        name = m.name or "(sin nombre)"
        # Imprimimos un separador visual con el número actual para distinguir cada modelo en la consola.
        print(f"--- [{n}] ---")
        # Mostramos el nombre técnico completo que la API le asigna a este recurso.
        print(f"  name (recurso):  {name}")
        # Comprobamos si el modelo incluye un nombre amigable o comercial para mostrar.
        if m.display_name:
            # Si lo incluye, lo imprimimos en pantalla.
            print(f"  display_name:    {m.display_name}")
        # Verificamos si Google nos entregó una descripción de lo que hace este modelo.
        if m.description:
            # Limpiamos la descripción quitando saltos de línea y espacios extra para que quede en una sola línea de texto.
            desc = " ".join(m.description.split())
            # Revisamos si la descripción es demasiado larga (más de 280 caracteres).
            if len(desc) > 280:
                # Si es muy larga, la recortamos y agregamos puntos suspensivos para no saturar nuestra lectura.
                desc = desc[:280] + "…"
            # Imprimimos la descripción ya formateada y adaptada a nuestra consola.
            print(f"  descripcion:     {desc}")
        # Guardamos la lista de acciones o capacidades que este modelo nos informa que puede realizar.
        actions = m.supported_actions
        # Comprobamos si efectivamente hay acciones en la lista.
        if actions:
            # Si las hay, las unimos separadas por comas y las mostramos en pantalla.
            print(f"  capacidades:     {', '.join(actions)}")
        # Si el modelo no nos informó ninguna capacidad específica.
        else:
            # Mostramos un mensaje aclarando que no tenemos esa información por parte de la API.
            print("  capacidades:     (no informadas por la API para este modelo)")
        # Revisamos si el modelo nos indica explícitamente sus límites de tokens de entrada o de salida.
        if m.input_token_limit is not None or m.output_token_limit is not None:
            # Imprimimos esos límites para saber cuánta información podemos enviarle y recibir de él en nuestras pruebas.
            print(
                f"  limites tokens:  entrada={m.input_token_limit}  salida={m.output_token_limit}"
            )
        # Usamos nuestra función de apoyo para obtener el ID limpio del modelo en el que estamos iterando.
        sid = _short_model_id(name)
        # Destacamos con una flecha el ID exacto que debemos copiar en nuestro archivo .env.
        print(f"  → GEMINI_MODEL:  {sid}")
        # Imprimimos un salto de línea vacío para separar visualmente este bloque del siguiente modelo.
        print()

    # Si después de todo el proceso nuestro contador sigue en cero, significa que no obtuvimos datos.
    if n == 0:
        # Imprimimos un aviso para que revisemos si hay un problema con nuestra clave, cuota o versión de la API.
        print("No se devolvió ningún modelo (revisa clave, cuota o GEMINI_API_VERSION).")


# Comprobamos si estamos ejecutando este archivo directamente desde la terminal (y no importándolo desde otro archivo).
if __name__ == "__main__":
    # Si es una ejecución directa, llamamos a la función principal para que arranque nuestro script.
    main()
