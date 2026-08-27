# -*- coding: utf-8 -*-
"""Scraping de unidades disponibles en Portal Inmobiliario, con reintentos y backoff."""

import logging
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Reintentos ante fallos transitorios de scraping (timeouts, bloqueos momentáneos, etc.)
MAX_INTENTOS_SCRAPING_POR_DEFECTO = 4
ESPERA_INICIAL_SEGUNDOS_POR_DEFECTO = 5  # backoff exponencial: 5s, 10s, 20s...


def _intentar_scraping_unidades(url, selector_unidades, chrome_binary_path=None, chromedriver_path=None):
    """
    Un único intento de scraping: abre el navegador, espera el contenido dinámico,
    encuentra TODOS los marcadores de unidades en `url` que coinciden con
    `selector_unidades` y los suma.
    Devuelve el número total de unidades como int. Lanza una excepción si el intento falla
    (timeout, elementos ausentes, error de Selenium, etc.); el llamante decide si reintentar.

    Si se definen `chrome_binary_path`/`chromedriver_path` (típicamente dentro de un
    contenedor Docker con Chromium ya instalado), se usan en vez de dejar que
    webdriver-manager descargue un chromedriver por su cuenta.
    """
    logging.info("Configurando el navegador Selenium en modo headless...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    if chrome_binary_path:
        options.binary_location = chrome_binary_path

    driver = None
    try:
        if chromedriver_path:
            service = ChromeService(chromedriver_path)
        else:
            service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        logging.info("Accediendo a la URL...")
        driver.get(url)

        logging.info(
            f"Esperando un máximo de 20 segundos a que aparezcan los elementos '{selector_unidades}'..."
        )
        # Estrategia de espera explícita: esperar a que AL MENOS un elemento aparezca.
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector_unidades)))

        # Una vez que sabemos que hay al menos uno, buscamos TODOS los elementos que coincidan.
        span_elements = driver.find_elements(By.CSS_SELECTOR, selector_unidades)

        if not span_elements:
            raise RuntimeError(
                "La espera fue exitosa pero no se encontraron elementos."
            )

        total_unidades = 0
        logging.info(
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
                    logging.info(f"  -> '{texto}' -> Sumando {numero_str} unidades.")
                except (ValueError, IndexError):
                    logging.warning(
                        f"  -> ADVERTENCIA: No se pudo extraer el número de '{texto}'. Contando como 1."
                    )
                    total_unidades += 1
            else:
                # Es una unidad individual (con precio), cuenta como 1.
                total_unidades += 1
                logging.info(f"  -> '{texto}' -> Contando como 1 unidad.")

        logging.info(f"Recuento total de unidades calculado: {total_unidades}")
        return total_unidades
    finally:
        if driver:
            logging.info("Cerrando el navegador Selenium.")
            driver.quit()


def scrapear_unidades_disponibles(
    url,
    selector_unidades,
    chrome_binary_path=None,
    chromedriver_path=None,
    max_intentos=MAX_INTENTOS_SCRAPING_POR_DEFECTO,
    espera_inicial_segundos=ESPERA_INICIAL_SEGUNDOS_POR_DEFECTO,
):
    """
    Ejecuta _intentar_scraping_unidades() con reintentos y backoff exponencial ante
    fallos transitorios (timeouts, bloqueos momentáneos, problemas de red).
    Devuelve el número total de unidades como int, o None si todos los intentos fallan.
    """
    for intento in range(1, max_intentos + 1):
        try:
            return _intentar_scraping_unidades(
                url, selector_unidades, chrome_binary_path, chromedriver_path
            )
        except TimeoutException:
            motivo = (
                f"ningún elemento '{selector_unidades}' apareció en 20 segundos "
                "(bloqueo, cambio de la página o problema de red)"
            )
        except (WebDriverException, RuntimeError, OSError) as e:
            # Fallos transitorios del navegador, de red o de descarga del driver:
            # tiene sentido reintentar, a diferencia de un bug de programación.
            motivo = f"fallo transitorio del navegador o de red ({e})"
        except Exception as e:
            logging.error(
                f"Error inesperado y no transitorio durante el scraping, no se "
                f"reintenta (probable bug o configuración incorrecta): {e}"
            )
            return None

        if intento == max_intentos:
            logging.error(
                f"Intento {intento}/{max_intentos} falló ({motivo}). "
                "Se alcanzó el máximo de reintentos, se trata como error de scraping."
            )
            return None

        espera = espera_inicial_segundos * (2 ** (intento - 1))
        logging.warning(
            f"Intento {intento}/{max_intentos} falló ({motivo}). "
            f"Reintentando en {espera} segundos..."
        )
        time.sleep(espera)
