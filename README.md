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

- [Docker Desktop](https://docs.docker.com/get-docker/) instalado **y abierto**. Docker Desktop tiene que quedar corriendo en segundo plano (vas a ver su ícono, una ballena, en la barra de tareas o menu bar); si está cerrado, los comandos de más abajo van a fallar con un error como "Cannot connect to the Docker daemon".
- Una cuenta de Telegram, para crear el bot y recibir los avisos.
- Saber abrir la terminal de tu sistema (en Mac: la aplicación "Terminal"; en Windows: "PowerShell" o "Símbolo del sistema"). No hace falta experiencia previa: cada comando que tienes que escribir está indicado abajo, tal cual.

### Pasos

1. Abre una terminal y clona el proyecto:
   ```bash
   git clone https://github.com/facualex/portalinmobiliario_watch
   cd portalinmobiliario_watch
   cp .env.example .env
   ```

   > 💡 **Importante:** el `cd portalinmobiliario_watch` de arriba te deja parado dentro de la carpeta del proyecto, y **todos los comandos de esta guía asumen que estás ahí**. Si en algún momento cierras la terminal o abres una nueva, tienes que volver a entrar a esa carpeta antes de seguir. Un truco que funciona en Mac y Windows: escribe `cd ` (con un espacio al final, sin presionar Enter) y luego arrastra la carpeta `portalinmobiliario_watch` desde el explorador de archivos hacia la ventana de la terminal; la ruta se completa sola. Ahí sí, presiona Enter.

2. Crea un bot de Telegram: en Telegram, busca a `@BotFather`, envíale `/newbot` y sigue sus instrucciones (te va a pedir un nombre y un usuario para tu bot). Al final te entrega un **Token HTTP API**, una cadena larga de letras y números: cópiala.

   Ahora abre el archivo `.env` que se creó en el paso anterior (está dentro de la carpeta del proyecto) con un editor de texto simple, como el Bloc de notas en Windows o TextEdit en Mac. Busca la línea `TELEGRAM_BOT_TOKEN=` y pega el token justo después del signo `=`, sin espacios ni comillas alrededor. Guarda el archivo.

   Este es el único secreto que necesitas configurar a mano; todo lo demás (qué propiedades vigilar, a qué chat notificar) se configura después, desde la interfaz web.

3. En la misma terminal (todavía dentro de la carpeta del proyecto), levanta los servicios:
   ```bash
   docker compose up -d --build
   ```
   La primera vez puede tardar unos minutos: está descargando y construyendo las piezas necesarias. Esto arranca dos contenedores: `worker` (el scraper) y `web` (la API + la interfaz), ambos compartiendo la misma base de datos.
4. Abre **http://localhost:8000** en tu navegador.
5. Antes de conectar tu primera propiedad, necesitas tu **Chat ID** de Telegram:
   - Inicia una conversación con tu bot (búscalo por el usuario que le pusiste y haz clic en "Start").
   - En tu terminal, dentro de la carpeta del proyecto, ejecuta (no necesitas tener Python instalado en tu máquina, el comando corre dentro de Docker):
     ```bash
     docker compose run --rm worker uv run --package worker python get_chat_id.py
     ```
     El comando te va a devolver un número: ese es tu Chat ID, cópialo.
6. En la interfaz, haz clic en **"Conectar propiedad"** y completa:
   - **Nombre**: como quieras identificar el edificio.
   - **URL del polígono**: la URL del mapa de Portal Inmobiliario con el polígono dibujado (ver más abajo cómo obtenerla).
   - **Notificar en**: pega tu Chat ID para conectar tu chat de Telegram (el bot te manda un mensaje de prueba antes de guardarlo).
   - **Frecuencia**: una hora fija diaria (con su propia zona horaria) o cada N horas.
7. Si quieres revisar qué está haciendo el worker (por ejemplo, para confirmar que efectivamente está revisando tu propiedad), desde la carpeta del proyecto:
   ```bash
   docker compose logs -f worker
   ```
   Vas a ver texto apareciendo en la terminal a medida que el worker corre; para dejar de mirarlo, presiona `Ctrl+C` (esto no detiene el servicio, solo deja de mostrarte el registro). Los mismos logs también quedan guardados en la carpeta `logs/` de tu proyecto.
8. Para detener la aplicación (por ejemplo, si quieres apagar tu computador), desde la carpeta del proyecto:
   ```bash
   docker compose down
   ```
   Para volver a levantarla más adelante, repite el paso 3 (`docker compose up -d --build`); no hace falta repetir el resto de los pasos, tus propiedades y configuración quedan guardadas.

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

> Esta sección es solo para quienes quieran modificar el código de Lindero. Si únicamente quieres usarlo, no necesitas nada de lo que sigue: con la instalación con Docker de arriba ya tienes todo funcionando.

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
