import os

import requests
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Lee solo el BOT_TOKEN
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("ERROR: No se encontró el TELEGRAM_BOT_TOKEN en el archivo .env")
else:
    # Esta es la URL del método 'getUpdates' de la API de Telegram
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    print("Script de diagnóstico iniciado.")
    print("-" * 20)

    try:
        # Hacemos una petición para ver las "actualizaciones" (mensajes nuevos)
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()

        if data["ok"] and data["result"]:
            # Tomamos el último mensaje recibido
            ultimo_mensaje = data["result"][-1]
            chat_id = ultimo_mensaje["message"]["chat"]["id"]

            print("\n¡Información recibida exitosamente!")
            print(f"✅ TU CHAT_ID DEFINITIVO ES: {chat_id}")
            print(
                "\nCopia este número y pégalo en tu archivo .env como el valor de TELEGRAM_CHAT_ID."
            )

            # Opcional: Limpiar las actualizaciones para que no se muestren la próxima vez
            requests.get(f"{url}?offset={ultimo_mensaje['update_id'] + 1}")

        else:
            print(
                "\nNo se han recibido nuevos mensajes. Asegúrate de haberle enviado un mensaje al bot antes de ejecutar este script."
            )

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
    except Exception as e:
        print(f"Un error inesperado ocurrió: {e}")
