import { useState } from "react";
import { ApiError, api } from "../api/client";
import type { ChatTelegram, Propiedad } from "../api/types";

// Mismas reglas que packages/lindero_core/src/lindero_core/models.py, para dar
// feedback inmediato sin ida y vuelta al servidor (que sigue siendo la fuente
// de verdad: si algo se le escapa a esta validación, el 422 del backend lo ataja).
const DOMINIO_URL_PERMITIDO = "portalinmobiliario.com";
const INTERVALO_MINIMO_HORAS = 1;

function validarUrlPoligono(url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return "La URL no es válida.";
  }
  const host = parsed.hostname.toLowerCase();
  const esDominioValido =
    host === DOMINIO_URL_PERMITIDO || host.endsWith(`.${DOMINIO_URL_PERMITIDO}`);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "La URL debe empezar con http:// o https://.";
  }
  if (!esDominioValido) {
    return `La URL debe ser de ${DOMINIO_URL_PERMITIDO} (ej: https://www.portalinmobiliario.com/...).`;
  }
  return null;
}

function validarHoraEjecucion(hora: string): string | null {
  if (!/^([01]\d|2[0-3]):([0-5]\d)$/.test(hora)) {
    return "La hora debe tener formato HH:MM (24 horas).";
  }
  return null;
}

function validarTz(tz: string): string | null {
  if (!tz.trim()) return "La zona horaria es obligatoria.";
  // Intl.supportedValuesOf está disponible en navegadores modernos (2022+); si
  // no lo está, dejamos que el 422 del servidor sea el que valide esto.
  if (typeof Intl.supportedValuesOf === "function") {
    const validas = Intl.supportedValuesOf("timeZone");
    if (!validas.includes(tz)) {
      return `"${tz}" no parece ser una zona horaria IANA válida (ej: America/Santiago).`;
    }
  }
  return null;
}

function validarIntervaloHoras(valor: string): string | null {
  const numero = Number(valor);
  if (!Number.isFinite(numero) || numero < INTERVALO_MINIMO_HORAS) {
    return `El intervalo debe ser de al menos ${INTERVALO_MINIMO_HORAS} hora(s).`;
  }
  return null;
}

interface Props {
  chats: ChatTelegram[];
  /** Si viene, el modal edita esta propiedad en vez de crear una nueva. */
  propiedad?: Propiedad;
  onClose: () => void;
  /** Al crear, recibe la propiedad recién creada (para poder seguirle el rastro). */
  onSaved: (creada?: Propiedad) => void;
}

export function PropertyModal({ chats, propiedad, onClose, onSaved }: Props) {
  const editando = propiedad !== undefined;

  const [nombre, setNombre] = useState(propiedad?.nombre ?? "");
  const [urlPoligono, setUrlPoligono] = useState(propiedad?.url_poligono ?? "");

  const [modoChat, setModoChat] = useState<"existente" | "nuevo">(
    chats.length > 0 ? "existente" : "nuevo",
  );
  const [chatSeleccionado, setChatSeleccionado] = useState<string>(
    (propiedad?.chat_telegram_id ?? chats[0]?.id)?.toString() ?? "",
  );
  const [nuevoChatId, setNuevoChatId] = useState("");
  const [nuevoChatNombre, setNuevoChatNombre] = useState("");

  const [frecuenciaTipo, setFrecuenciaTipo] = useState<"hora_fija" | "intervalo">(
    propiedad?.frecuencia_tipo ?? "hora_fija",
  );
  const [horaEjecucion, setHoraEjecucion] = useState(
    propiedad?.hora_ejecucion ?? "09:00",
  );
  const [tz, setTz] = useState(propiedad?.tz ?? "America/Santiago");
  const [intervaloHoras, setIntervaloHoras] = useState(
    propiedad?.intervalo_horas?.toString() ?? "24",
  );

  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function manejarSubmit(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);

    if (!nombre.trim() || !urlPoligono.trim()) {
      setError("Nombre y URL del polígono son obligatorios.");
      return;
    }

    const errorUrl = validarUrlPoligono(urlPoligono.trim());
    if (errorUrl) {
      setError(errorUrl);
      return;
    }

    if (modoChat === "nuevo" && (!nuevoChatId.trim() || !nuevoChatNombre.trim())) {
      setError("Completa el chat_id y un nombre para el chat nuevo.");
      return;
    }
    if (modoChat === "existente" && !chatSeleccionado) {
      setError("Selecciona un chat de Telegram.");
      return;
    }

    if (frecuenciaTipo === "hora_fija") {
      const errorHora = validarHoraEjecucion(horaEjecucion);
      if (errorHora) {
        setError(errorHora);
        return;
      }
      const errorTz = validarTz(tz);
      if (errorTz) {
        setError(errorTz);
        return;
      }
    } else {
      const errorIntervalo = validarIntervaloHoras(intervaloHoras);
      if (errorIntervalo) {
        setError(errorIntervalo);
        return;
      }
    }

    setEnviando(true);
    try {
      let chatTelegramId: number;
      if (modoChat === "nuevo") {
        const chat = await api.crearChat({
          chat_id: nuevoChatId.trim(),
          nombre: nuevoChatNombre.trim(),
        });
        chatTelegramId = chat.id;
      } else {
        chatTelegramId = Number(chatSeleccionado);
      }

      const payload = {
        nombre: nombre.trim(),
        url_poligono: urlPoligono.trim(),
        chat_telegram_id: chatTelegramId,
        frecuencia_tipo: frecuenciaTipo,
        hora_ejecucion: frecuenciaTipo === "hora_fija" ? horaEjecucion : null,
        intervalo_horas:
          frecuenciaTipo === "intervalo" ? Number(intervaloHoras) : null,
        tz,
      };

      if (editando) {
        await api.editarPropiedad(propiedad.id, payload);
        onSaved();
      } else {
        const creada = await api.crearPropiedad(payload);
        onSaved(creada);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ocurrió un error inesperado.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{editando ? "Editar propiedad" : "Conectar propiedad"}</h2>
          <button className="modal-close" onClick={onClose} type="button">
            ✕
          </button>
        </div>
        <p className="modal-sub">
          {editando
            ? "Los cambios se aplican desde la próxima verificación."
            : "Se agregará a tu bot y empezará a vigilarse en la próxima revisión."}
        </p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={manejarSubmit}>
          <div className="field">
            <label>Nombre</label>
            <input
              type="text"
              placeholder="Ej: Antonio Varas 1234"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
          </div>

          <div className="field">
            <label>URL del polígono</label>
            <input
              type="text"
              placeholder="https://www.portalinmobiliario.com/..."
              value={urlPoligono}
              onChange={(e) => setUrlPoligono(e.target.value)}
            />
            <span className="field-hint">
              Pega la URL del mapa de Portal Inmobiliario con el polígono
              dibujado.
            </span>
          </div>

          <div className="field">
            <label>Notificar en</label>
            {modoChat === "existente" ? (
              <>
                <select
                  value={chatSeleccionado}
                  onChange={(e) => setChatSeleccionado(e.target.value)}
                >
                  {chats.map((chat) => (
                    <option key={chat.id} value={chat.id}>
                      Telegram · {chat.nombre}
                    </option>
                  ))}
                </select>
                <span className="field-hint">
                  <button
                    type="button"
                    className="field-hint-link"
                    onClick={() => setModoChat("nuevo")}
                  >
                    + Conectar otro chat de Telegram
                  </button>
                </span>
              </>
            ) : (
              <>
                <input
                  type="text"
                  placeholder="Chat ID (obtenido con get_chat_id.py)"
                  value={nuevoChatId}
                  onChange={(e) => setNuevoChatId(e.target.value)}
                  style={{ marginBottom: 8 }}
                />
                <input
                  type="text"
                  placeholder="Nombre para identificarlo (ej: Bot Propiedades)"
                  value={nuevoChatNombre}
                  onChange={(e) => setNuevoChatNombre(e.target.value)}
                />
                {chats.length > 0 && (
                  <span className="field-hint">
                    <button
                      type="button"
                      className="field-hint-link"
                      onClick={() => setModoChat("existente")}
                    >
                      Usar un chat ya conectado
                    </button>
                  </span>
                )}
              </>
            )}
          </div>

          <div className="field">
            <label>Frecuencia</label>
            <div className="freq-toggle">
              <button
                type="button"
                className={frecuenciaTipo === "hora_fija" ? "active" : ""}
                onClick={() => setFrecuenciaTipo("hora_fija")}
              >
                Hora fija
              </button>
              <button
                type="button"
                className={frecuenciaTipo === "intervalo" ? "active" : ""}
                onClick={() => setFrecuenciaTipo("intervalo")}
              >
                Cada N horas
              </button>
            </div>
          </div>

          {frecuenciaTipo === "hora_fija" ? (
            <div className="field">
              <label>Hora y zona horaria</label>
              <input
                type="time"
                value={horaEjecucion}
                onChange={(e) => setHoraEjecucion(e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <input
                type="text"
                placeholder="America/Santiago"
                value={tz}
                onChange={(e) => setTz(e.target.value)}
              />
            </div>
          ) : (
            <div className="field">
              <label>Horas entre cada revisión</label>
              <input
                type="number"
                min="1"
                step="1"
                value={intervaloHoras}
                onChange={(e) => setIntervaloHoras(e.target.value)}
              />
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={enviando}
            >
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={enviando}>
              {enviando
                ? "Guardando..."
                : editando
                  ? "Guardar cambios"
                  : "Conectar y empezar a vigilar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
