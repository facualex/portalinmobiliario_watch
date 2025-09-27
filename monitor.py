import os

# Requests para Telegram (es más ligero que usar Selenium para esto)
import requests
from dotenv import load_dotenv

# Selenium imports
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# --- CONFIGURACIÓN (leída desde el archivo .env) ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL_A_MONITOREAR = os.getenv("URL_A_MONITOREAR")
NOMBRE_PROPIEDAD = os.getenv("NOMBRE_PROPIEDAD")


# --- CONSTANTES DEL SCRIPT ---
NOMBRE_ARCHIVO_ESTADO = "ultimo_recuento.txt"
# Selector CSS del elemento a esperar y extraer
SELECTOR_UNIDADES = "span.ui-search-map-marker--price__label"


def enviar_notificacion_telegram(mensaje):
    """Envía un mensaje a través del bot de Telegram."""
    url_telegram_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        response = requests.post(url_telegram_api, data=payload)
        if response.status_code == 200:
            print("Notificación enviada exitosamente.")
        else:
            print(
                f"Error al enviar notificación: {response.status_code} - {response.text}"
            )
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión al enviar notificación: {e}")


def obtener_recuento_anterior():
    """Lee el último recuento guardado. Devuelve None si no existe."""
    if not os.path.exists(NOMBRE_ARCHIVO_ESTADO):
        return None
    try:
        with open(NOMBRE_ARCHIVO_ESTADO, "r") as f:
            return f.read().strip() or None
    except IOError as e:
        print(f"Error al leer el archivo de estado: {e}")
        return None


def guardar_recuento_actual(recuento):
    """Guarda el recuento actual en el archivo de estado."""
    try:
        with open(NOMBRE_ARCHIVO_ESTADO, "w") as f:
            f.write(str(recuento))
        print(f"Recuento actualizado guardado: {recuento}")
    except IOError as e:
        print(f"Error al guardar el nuevo recuento: {e}")


def scrapear_unidades_disponibles():
    """
    Utiliza Selenium para cargar la página, esperar el contenido dinámico y extraer el dato.
    Devuelve el número como string, o None si ocurre un error.
    """
    print("Configurando el navegador Selenium en modo headless...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        print(f"Accediendo a la URL: {URL_A_MONITOREAR}")
        driver.get(URL_A_MONITOREAR)

        print(
            f"Esperando un máximo de 20 segundos a que aparezca el elemento '{SELECTOR_UNIDADES}'..."
        )
        # Estrategia de espera explícita: la mejor práctica
        wait = WebDriverWait(driver, 20)
        span_unidades = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_UNIDADES))
        )

        recuento = span_unidades.text.strip()
        print(f"Recuento de unidades encontrado en la página: {recuento}")
        return recuento

    except TimeoutException:
        print(
            f"Error: El elemento '{SELECTOR_UNIDADES}' no apareció en 20 segundos. La estructura de la página puede haber cambiado o la carga fue muy lenta."
        )
        return None
    except Exception as e:
        print(f"Ocurrió un error inesperado durante el scraping con Selenium: {e}")
        return None
    finally:
        if driver:
            print("Cerrando el navegador Selenium.")
            driver.quit()


def main():
    """Función principal que orquesta todo el proceso."""
    print("--- Iniciando servicio de monitoreo ---")

    if not BOT_TOKEN or not CHAT_ID or not URL_A_MONITOREAR:
        print(
            "ERROR CRÍTICO: Las variables TELEGRAN_BOT_TOKEN, TELEGRAM_CHAT_ID y/o URL_A_MONITOREAR no están definidas. Revisa tu archivo .env."
        )
        return

    recuento_anterior = obtener_recuento_anterior()
    recuento_actual = scrapear_unidades_disponibles()

    if recuento_actual is None:
        mensaje_error = "🚨 **ERROR DE SCRAPING** 🚨\nNo se pudo obtener el número de unidades de Portal Inmobiliario. Revisa el script o la página web."
        enviar_notificacion_telegram(mensaje_error)
        return

    if recuento_anterior is None:
        print("Primera ejecución. Enviando notificación de bienvenida...")
        mensaje = (
            f"✅ **Servicio de Monitoreo Activado** ✅\n\n"
            f"Se ha iniciado el seguimiento para {NOMBRE_PROPIEDAD}\n\n"
            f"Actualmente hay <b>{recuento_actual}</b> disponibles.\n"
            f"Se te notificará sobre cualquier cambio futuro."
        )
        enviar_notificacion_telegram(mensaje)
    elif recuento_anterior != recuento_actual:
        print("¡Cambio detectado! Enviando notificación...")
        mensaje = (
            f"🔔 **¡Cambio en {NOMBRE_PROPIEDAD}!** 🔔\n\n"
            f"Unidades disponibles cambiaron de <b>{recuento_anterior}</b> a <b>{recuento_actual}</b>.\n\n"
            f"Revisa ahora: {URL_A_MONITOREAR}"
        )
        enviar_notificacion_telegram(mensaje)
    else:
        print("Sin cambios detectados. No se enviará notificación.")

    guardar_recuento_actual(recuento_actual)
    print("--- Servicio de monitoreo finalizado ---")


if __name__ == "__main__":
    main()
