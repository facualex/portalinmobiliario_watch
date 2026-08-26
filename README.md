<p align="center">
  <img src="./img/lindero-logo.svg" width="96" alt="Logo de Lindero" />
</p>

<h1 align="center">Lindero</h1>

<p align="center">
  Watchdog self-hosted que vigila propiedades específicas en Portal Inmobiliario<br/>
  y te avisa por Telegram apenas cambia la disponibilidad.
</p>

---

Le dibujas un polígono a un edificio puntual en el mapa de Portal Inmobiliario, se lo pasas a Lindero, y listo: cada vez que cambia el número de unidades disponibles ahí, te llega un mensaje de Telegram. Nada de revisar un dashboard: la notificación es el producto.

## Arquitectura

Este repo es un monorepo con tres piezas, pensadas para correr juntas vía Docker:

- **`apps/worker`**: el scraper. Un solo proceso de larga duración que revisa, cada minuto, qué propiedades tienen una corrida pendiente (según su propia frecuencia), y las procesa: scrapea con reintentos y backoff exponencial, compara contra el último recuento conocido, y notifica por Telegram si corresponde. La notificación solo se da por enviada (y el recuento se persiste) si Telegram confirmó la entrega; si falla, se reintenta en la próxima corrida en vez de perderse.
- **`apps/api`**: backend FastAPI. Administra las propiedades y los chats de Telegram a los que notifican (alta, baja, pausar/reanudar, editar). Sin autenticación: está pensado para correr en tu propia red, no expuesto a internet.
- **`apps/web`**: la interfaz (React). Es un panel puramente administrativo: conectar propiedades, ver su estado operativo (activo / pausado / error), gestionar a qué chat de Telegram notifica cada una. No es un dashboard de métricas: si quieres ver cuántas unidades hay, esa información ya te la mandó Telegram.
- **`packages/lindero_core`**: lógica compartida entre el worker y la API (scraping, notificación, modelos de datos, acceso a la base).

Todo el estado vive en una base **SQLite** compartida (`data/lindero.db`), sin infraestructura adicional.

## Instalación con Docker (recomendado)

### Requisitos

- [Docker](https://docs.docker.com/get-docker/) con Docker Compose.

### Pasos

1. Clona el proyecto y crea tu `.env`:
   ```bash
   git clone https://github.com/facualex/portalinmobiliario_watch
   cd portalinmobiliario_watch
   cp .env.example .env
   ```
2. Crea un bot de Telegram: en Telegram, busca a `@BotFather`, envía `/newbot` y sigue las instrucciones. Copia el **Token HTTP API** y pégalo en `.env` como `TELEGRAM_BOT_TOKEN`. Es el único secreto que necesitas configurar a mano; todo lo demás (qué propiedades vigilar, a qué chat notificar) se configura después, desde la interfaz web.
3. Levanta los servicios:
   ```bash
   docker compose up -d --build
   ```
   Esto construye y arranca dos contenedores: `worker` (el scraper) y `web` (la API + la interfaz), ambos compartiendo la misma base de datos.
4. Abre **http://localhost:8000** en tu navegador.
5. Antes de conectar tu primera propiedad, necesitas tu **Chat ID** de Telegram:
   - Inicia una conversación con tu bot (haz clic en "Start").
   - Ejecuta, sin necesidad de tener Python instalado en tu máquina:
     ```bash
     docker compose run --rm worker uv run --package worker python get_chat_id.py
     ```
     Copia el Chat ID que te devuelve.
6. En la interfaz, haz clic en **"Conectar propiedad"** y completa:
   - **Nombre**: como quieras identificar el edificio.
   - **URL del polígono**: la URL del mapa de Portal Inmobiliario con el polígono dibujado (ver más abajo cómo obtenerla).
   - **Notificar en**: pega tu Chat ID para conectar tu chat de Telegram (el bot te manda un mensaje de prueba antes de guardarlo).
   - **Frecuencia**: una hora fija diaria (con su propia zona horaria) o cada N horas.
7. Revisa los logs del worker en cualquier momento:
   ```bash
   docker compose logs -f worker
   ```
   (también quedan en `logs/` en tu máquina, montado como volumen).
8. Para detenerlo:
   ```bash
   docker compose down
   ```

El estado (`data/lindero.db`) y los logs (`logs/`) se guardan en tu máquina vía volúmenes, así que persisten aunque reconstruyas o reinicies los contenedores.

### Obtener la URL del polígono de un edificio

1. Visita la página de arriendos (vista mapa) de [Portal Inmobiliario](https://www.portalinmobiliario.com/arriendo/departamento/_DisplayType_M).
2. Navega en el mapa hasta encontrar el edificio que deseas monitorear.
3. En la parte superior derecha del mapa, haz clic en la herramienta **`Dibujar área`**.

   ![Herramienta 'Dibujar área' en el mapa de Portal Inmobiliario](./img/1.png)

4. Dibuja un polígono lo más ajustado posible alrededor del edificio. Esto es **crucial** para que el scraping solo cuente las unidades de esa ubicación específica.

   ![Ejemplo de un polígono dibujado alrededor de un edificio específico](./img/2.png)

5. Una vez que dibujes el área, la página generará una nueva URL en tu navegador. **Copia esa URL completa**: es la que pegas en "URL del polígono" al conectar la propiedad.

## Desarrollo (sin Docker)

Para trabajar en el código sin reconstruir contenedores en cada cambio.

### Requisitos

- Python 3.12+ y [uv](https://docs.astral.sh/uv/).
- Node.js 20+ (para el frontend).

### Backend (worker + API)

```bash
uv sync --all-packages         # instala todo el workspace (worker, api, lindero_core)
cp .env.example .env          # completa al menos TELEGRAM_BOT_TOKEN

# Correr el worker (bucle infinito, revisa propiedades cada 60s):
uv run --package worker python -m worker.scheduler

# Correr la API (recarga en caliente), en otra terminal:
uv run --package api uvicorn api.main:app --reload --app-dir apps/api/src
```

### Frontend

En otra terminal:

```bash
cd apps/web
npm install
npm run dev
```

Abre **http://localhost:5173**. Vite reenvía las llamadas a `/api` hacia la API en el puerto 8000, así que ambas corren a la vez sin configuración adicional.

### Tests

```bash
uv run pytest packages/lindero_core/tests/
```

## Registro de Ejecuciones (Logs)

El **worker** gestiona sus propios logs, independientemente de si corre con Docker o localmente:

- Cada corrida con al menos una propiedad procesada crea un archivo dentro de `logs/`, nombrado con el timestamp de inicio: `logs/AAAA-MM-DD_HHMMSS.log` (los ticks sin nada que hacer no generan archivo, para no llenar la carpeta).
- Cada línea del archivo también incluye su propio timestamp interno.
- El mismo contenido se imprime en consola.
- Solo se conservan los **10 logs más recientes**; al iniciar una nueva corrida se eliminan automáticamente los más antiguos.

## Estructura del Proyecto

```
.
├── .env / .env.example      # TELEGRAM_BOT_TOKEN, DB_PATH, LINDERO_TICK_SEGUNDOS
├── docker-compose.yml       # 2 servicios: worker, web
├── pyproject.toml / uv.lock # workspace de uv (worker + api + lindero_core)
├── get_chat_id.py           # utilidad para obtener tu Chat ID de Telegram
├── img/                     # logo y capturas de la documentación
├── data/                    # lindero.db (SQLite), montado como volumen
├── logs/                    # logs del worker, últimos 10 (se genera solo)
│
├── packages/
│   └── lindero_core/        # lógica compartida: scraping, telegram, modelos, DB
│       ├── src/lindero_core/{scraping,telegram,models,db,repository}.py
│       └── tests/
│
└── apps/
    ├── worker/               # el scraper (Dockerfile: Python + Chromium + chromedriver)
    │   └── src/worker/{scheduler,runner,logger_config}.py
    ├── api/                  # backend FastAPI (Dockerfile: multi-stage, build del frontend incluido)
    │   └── src/api/{main,deps}.py + routers/{propiedades,chats_telegram}.py
    └── web/                  # frontend React + Vite (sin Dockerfile propio)
        └── src/{App.tsx, pages/, components/, api/, styles/}
```
