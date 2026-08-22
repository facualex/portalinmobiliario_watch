# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime

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
DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
NOMBRE_ARCHIVO_ESTADO = os.path.join(DIRECTORIO_SCRIPT, "ultimo_recuento.txt")
# Selector CSS para todos los marcadores de precio/unidades
SELECTOR_UNIDADES = "span.ui-search-map-marker--price__label"
# Reintentos ante fallos transitorios de scraping (timeouts, bloqueos momentáneos, etc.)
MAX_INTENTOS_SCRAPING = 4
ESPERA_INICIAL_SEGUNDOS = 5  # backoff exponencial: 5s, 10s, 20s...


def log_message(message):
    """
    Imprime un mensaje en la consola con un timestamp.
    """
    timestamp = datetime.now().strftime("[%d-%m-%Y %H:%M:%S]")
    print(f"{timestamp} {message}")


def enviar_notificacion_telegram(mensaje):
    """Envía un mensaje a través del bot de Telegram."""
    url_telegram_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        response = requests.post(url_telegram_api, data=payload)
        if response.status_code == 200:
            log_message("Notificación enviada exitosamente.")
        else:
            log_message(
                f"Error al enviar notificación: {response.status_code} - {response.text}"
            )
    except requests.exceptions.RequestException as e:
        log_message(f"Error de conexión al enviar notificación: {e}")


def obtener_recuento_anterior():
    """Lee el último recuento guardado. Devuelve None si no existe."""
    if not os.path.exists(NOMBRE_ARCHIVO_ESTADO):
        return None
    try:
        with open(NOMBRE_ARCHIVO_ESTADO, "r") as f:
            return f.read().strip() or None
    except IOError as e:
        log_message(f"Error al leer el archivo de estado: {e}")
        return None


def guardar_recuento_actual(recuento):
    """Guarda el recuento actual en el archivo de estado."""
    try:
        with open(NOMBRE_ARCHIVO_ESTADO, "w") as f:
            f.write(str(recuento))
        log_message(f"Recuento actualizado guardado: {recuento}")
    except IOError as e:
        log_message(f"Error al guardar el nuevo recuento: {e}")


def _intentar_scraping_unidades():
    """
    Un único intento de scraping: abre el navegador, espera el contenido dinámico,
    encuentra TODOS los marcadores de unidades y los suma.
    Devuelve el número total de unidades como int. Lanza una excepción si el intento falla
    (timeout, elementos ausentes, error de Selenium, etc.); el llamante decide si reintentar.
    """
    log_message("Configurando el navegador Selenium en modo headless...")
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

        log_message("Accediendo a la URL...")
        driver.get(URL_A_MONITOREAR)

        log_message(
            f"Esperando un máximo de 20 segundos a que aparezcan los elementos '{SELECTOR_UNIDADES}'..."
        )
        # Estrategia de espera explícita: esperar a que AL MENOS un elemento aparezca.
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_UNIDADES)))

        # Una vez que sabemos que hay al menos uno, buscamos TODOS los elementos que coincidan.
        span_elements = driver.find_elements(By.CSS_SELECTOR, SELECTOR_UNIDADES)

        if not span_elements:
            raise RuntimeError(
                "La espera fue exitosa pero no se encontraron elementos."
            )

        total_unidades = 0
        log_message(
            f"Se encontraron {len(span_elements)} elementos de marcador. Procesando cada uno..."
        )

        for span in span_elements:
            texto = (
                span.text.strip().lower()
            )  # Convertir a minúsculas para una comparación robusta

            # Lógica para sumar unidades
            if "unidades" in texto:
                # Es un grupo de unidades, ej: "3 unidades"
                try:
                    numero_str = texto.split()[0]
                    total_unidades += int(numero_str)
                    log_message(f"  -> '{texto}' -> Sumando {numero_str} unidades.")
                except (ValueError, IndexError):
                    log_message(
                        f"  -> ADVERTENCIA: No se pudo extraer el número de '{texto}'. Contando como 1."
                    )
                    total_unidades += 1
            else:
                # Es una unidad individual (con precio), cuenta como 1.
                total_unidades += 1
                log_message(f"  -> '{texto}' -> Contando como 1 unidad.")

        log_message(f"Recuento total de unidades calculado: {total_unidades}")
        return total_unidades
    finally:
        if driver:
            log_message("Cerrando el navegador Selenium.")
            driver.quit()


def scrapear_unidades_disponibles():
    """
    Ejecuta _intentar_scraping_unidades() con reintentos y backoff exponencial ante
    fallos transitorios (timeouts, bloqueos momentáneos, problemas de red).
    Devuelve el número total de unidades como int, o None si todos los intentos fallan.
    """
    for intento in range(1, MAX_INTENTOS_SCRAPING + 1):
        try:
            return _intentar_scraping_unidades()
        except TimeoutException:
            motivo = (
                f"ningún elemento '{SELECTOR_UNIDADES}' apareció en 20 segundos "
                "(bloqueo, cambio de la página o problema de red)"
            )
        except Exception as e:
            motivo = f"error inesperado durante el scraping: {e}"

        if intento == MAX_INTENTOS_SCRAPING:
            log_message(
                f"Intento {intento}/{MAX_INTENTOS_SCRAPING} falló ({motivo}). "
                "Se alcanzó el máximo de reintentos, se trata como error de scraping."
            )
            return None

        espera = ESPERA_INICIAL_SEGUNDOS * (2 ** (intento - 1))
        log_message(
            f"Intento {intento}/{MAX_INTENTOS_SCRAPING} falló ({motivo}). "
            f"Reintentando en {espera} segundos..."
        )
        time.sleep(espera)


def main():
    """Función principal que orquesta todo el proceso."""
    log_message("--- Iniciando servicio de monitoreo ---")

    if not BOT_TOKEN or not CHAT_ID or not URL_A_MONITOREAR:
        log_message(
            "ERROR CRÍTICO: Las variables TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID y/o URL_A_MONITOREAR no están definidas. Revisa tu archivo .env."
        )
        return

    recuento_anterior = obtener_recuento_anterior()
    recuento_actual = scrapear_unidades_disponibles()

    if recuento_actual is None:
        mensaje_error = "🚨 <b>ERROR DE SCRAPING</b> 🚨\nNo se pudo obtener el número de unidades de Portal Inmobiliario. Revisa el script o la página web."
        enviar_notificacion_telegram(mensaje_error)
        return

    # Convertimos recuento_actual a string para una comparación y guardado consistentes
    recuento_actual_str = str(recuento_actual)

    if recuento_anterior is None:
        log_message("Primera ejecución. Enviando notificación de bienvenida...")
        mensaje = (
            f"✅ <b>Servicio de Monitoreo Activado</b> ✅\n\n"
            f"Se ha iniciado el seguimiento para {NOMBRE_PROPIEDAD}\n\n"
            f"Actualmente hay <b>{recuento_actual_str}</b> disponibles.\n"
            f"Se te notificará sobre cualquier cambio futuro."
        )
        enviar_notificacion_telegram(mensaje)
    elif recuento_anterior != recuento_actual_str:
        log_message("¡Cambio detectado! Enviando notificación...")
        mensaje = (
            f"🔔 <b>¡Cambio en {NOMBRE_PROPIEDAD}!</b> 🔔\n\n"
            f"Unidades disponibles cambiaron de <b>{recuento_anterior}</b> a <b>{recuento_actual_str}</b>.\n\n"
            f"Revisa ahora: {URL_A_MONITOREAR}"
        )
        enviar_notificacion_telegram(mensaje)
    else:
        log_message("Sin cambios detectados. No se enviará notificación.")

    guardar_recuento_actual(recuento_actual_str)
    log_message("--- Servicio de monitoreo finalizado ---")


if __name__ == "__main__":
    main()
