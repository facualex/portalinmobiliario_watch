import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { ChatTelegram, Propiedad } from "../api/types";
import { PropertyModal } from "../components/PropertyModal";
import { StatusPill } from "../components/StatusPill";

function formatearRelativo(fechaIso: string | null): string {
  if (!fechaIso) return "Nunca";
  // El backend guarda datetimes naive pero siempre en UTC; sin el sufijo "Z",
  // el motor de JS los interpretaría como hora local.
  const fecha = new Date(`${fechaIso}Z`);
  const diffMin = Math.round((Date.now() - fecha.getTime()) / 60000);

  if (diffMin < 1) return "hace instantes";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `hace ${diffH} h`;
  return `hace ${Math.round(diffH / 24)} d`;
}

function formatearProxima(propiedad: Propiedad): string {
  if (propiedad.pausado) return "—";
  // proxima_ejecucion_en es null solo cuando la propiedad nunca corrió, y esa
  // es justo la condición que el worker interpreta como "pendiente ya" (la
  // recoge en el próximo tick) — mismo caso que "En el próximo chequeo" abajo.
  if (!propiedad.proxima_ejecucion_en) return "En el próximo chequeo";

  const fecha = new Date(`${propiedad.proxima_ejecucion_en}Z`);
  const diffMin = Math.round((fecha.getTime() - Date.now()) / 60000);

  if (diffMin <= 0) return "En el próximo chequeo";
  if (diffMin < 60) return `en ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `en ${diffH} h`;
  return `en ${Math.round(diffH / 24)} d`;
}

const TELEGRAM_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M21.5 3.5 2.6 11c-1 .4-1 1.7.1 2l4.6 1.5 1.8 5.6c.3.9 1.4 1.1 2 .4l2.6-2.7 4.9 3.6c.8.6 2 .2 2.2-.8l3.2-15c.2-1-.7-1.8-1.5-1.5Z" />
  </svg>
);

export function PropertiesPage() {
  const [propiedades, setPropiedades] = useState<Propiedad[] | null>(null);
  const [chats, setChats] = useState<ChatTelegram[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [propiedadEditando, setPropiedadEditando] = useState<Propiedad | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idProcesando, setIdProcesando] = useState<number | null>(null);
  const [mensajeInfo, setMensajeInfo] = useState<string | null>(null);
  const refrescoIntervalRef = useRef<number | null>(null);
  const refrescoTimeoutRef = useRef<number | null>(null);

  function detenerRefrescoTemporal() {
    if (refrescoIntervalRef.current !== null) {
      window.clearInterval(refrescoIntervalRef.current);
      refrescoIntervalRef.current = null;
    }
    if (refrescoTimeoutRef.current !== null) {
      window.clearTimeout(refrescoTimeoutRef.current);
      refrescoTimeoutRef.current = null;
    }
  }

  function iniciarRefrescoTemporal(propiedadId: number) {
    detenerRefrescoTemporal();

    const verificar = async () => {
      try {
        const lista = await api.listarPropiedades();
        setPropiedades(lista);
        const objetivo = lista.find((p) => p.id === propiedadId);
        if (objetivo && objetivo.ultima_verificacion_en) {
          detenerRefrescoTemporal();
        }
      } catch {
        // si falla un ciclo de polling no interrumpimos el resto, se reintenta
        // en el próximo tick del intervalo.
      }
    };

    refrescoIntervalRef.current = window.setInterval(verificar, 5000);
    refrescoTimeoutRef.current = window.setTimeout(detenerRefrescoTemporal, 90000);
  }

  useEffect(() => {
    return () => detenerRefrescoTemporal();
  }, []);

  async function cargar() {
    setError(null);
    try {
      const [listaPropiedades, listaChats] = await Promise.all([
        api.listarPropiedades(),
        api.listarChats(),
      ]);
      setPropiedades(listaPropiedades);
      setChats(listaChats);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `No se pudo cargar: ${err.message}`
          : "No se pudo conectar con la API.",
      );
    }
  }

  useEffect(() => {
    cargar();
  }, []);

  const chatsPorId = useMemo(() => {
    const mapa = new Map<number, ChatTelegram>();
    chats.forEach((chat) => mapa.set(chat.id, chat));
    return mapa;
  }, [chats]);

  const propiedadesFiltradas = useMemo(() => {
    if (!propiedades) return [];
    const termino = busqueda.trim().toLowerCase();
    if (!termino) return propiedades;
    return propiedades.filter(
      (p) =>
        p.nombre.toLowerCase().includes(termino) ||
        (p.comuna ?? "").toLowerCase().includes(termino),
    );
  }, [propiedades, busqueda]);

  function actualizarEnLista(actualizada: Propiedad) {
    setPropiedades((prev) =>
      (prev ?? []).map((p) => (p.id === actualizada.id ? actualizada : p)),
    );
  }

  async function manejarPausar(propiedad: Propiedad) {
    setIdProcesando(propiedad.id);
    try {
      const actualizada = propiedad.pausado
        ? await api.reanudarPropiedad(propiedad.id)
        : await api.pausarPropiedad(propiedad.id);
      actualizarEnLista(actualizada);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar.");
    } finally {
      setIdProcesando(null);
    }
  }

  async function manejarEjecutarAhora(propiedad: Propiedad) {
    setIdProcesando(propiedad.id);
    try {
      const actualizada = await api.ejecutarAhora(propiedad.id);
      actualizarEnLista(actualizada);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo forzar la ejecución.");
    } finally {
      setIdProcesando(null);
    }
  }

  async function manejarEliminar(propiedad: Propiedad) {
    if (!confirm(`¿Eliminar "${propiedad.nombre}"? Esta acción no se puede deshacer.`)) {
      return;
    }
    setIdProcesando(propiedad.id);
    try {
      await api.eliminarPropiedad(propiedad.id);
      setPropiedades((prev) => (prev ?? []).filter((p) => p.id !== propiedad.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar.");
    } finally {
      setIdProcesando(null);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Propiedades</h1>
          <p className="page-sub">
            {propiedades ? `${propiedades.length} propiedad(es) conectadas` : "Cargando..."}
          </p>
        </div>
        <div className="search">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M11 11 L14.5 14.5"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="text"
            placeholder="Buscar propiedad o comuna..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </div>
        <button className="btn-primary" onClick={() => setModalAbierto(true)}>
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 2v12M2 8h12"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          Conectar propiedad
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {mensajeInfo && (
        <div className="info-banner">
          <span>{mensajeInfo}</span>
          <button
            className="info-banner-close"
            onClick={() => setMensajeInfo(null)}
            type="button"
            aria-label="Cerrar aviso"
          >
            ✕
          </button>
        </div>
      )}

      {propiedadesFiltradas.length === 0 ? (
        <div className="empty-state">
          {propiedades === null
            ? "Cargando propiedades..."
            : propiedades.length === 0
              ? "Todavía no conectaste ninguna propiedad."
              : "No hay propiedades que coincidan con la búsqueda."}
        </div>
      ) : (
        <div className="card-grid">
          {propiedadesFiltradas.map((propiedad) => {
            const chat = chatsPorId.get(propiedad.chat_telegram_id);
            const procesando = idProcesando === propiedad.id;
            return (
              <article className="prop-card" key={propiedad.id}>
                <div className="prop-card-header">
                  <div className="prop-name">{propiedad.nombre}</div>
                  <StatusPill propiedad={propiedad} />
                </div>

                {(propiedad.comuna ||
                  propiedad.precio_referencia ||
                  (propiedad.estado_operativo === "error" && propiedad.ultimo_error)) && (
                  <div
                    className={
                      propiedad.estado_operativo === "error"
                        ? "prop-meta is-error"
                        : "prop-meta"
                    }
                  >
                    {propiedad.estado_operativo === "error" && propiedad.ultimo_error
                      ? propiedad.ultimo_error
                      : [propiedad.comuna, propiedad.precio_referencia]
                          .filter(Boolean)
                          .join(" · ")}
                  </div>
                )}

                <div className="prop-card-body">
                  <div className="prop-card-row">
                    <span className="label">Última verificación</span>
                    <span className="value mono">
                      {formatearRelativo(propiedad.ultima_verificacion_en)}
                      {propiedad.ultimo_recuento !== null && (
                        <span className="sub">{propiedad.ultimo_recuento} unidades</span>
                      )}
                    </span>
                  </div>
                  <div className="prop-card-row">
                    <span className="label">Próxima revisión</span>
                    <span className="value mono">{formatearProxima(propiedad)}</span>
                  </div>
                </div>

                <div className="prop-card-footer">
                  <div className="notify-cell">
                    {TELEGRAM_ICON}
                    {chat?.nombre ?? "—"}
                  </div>
                  <div className="row-actions">
                    <button
                      className="icon-btn"
                      title="Ejecutar ahora"
                      disabled={procesando || propiedad.pausado}
                      onClick={() => manejarEjecutarAhora(propiedad)}
                    >
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M13 8a5 5 0 1 1-1.6-3.7M13 3v3.2h-3.2"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                    <button
                      className="icon-btn"
                      title={propiedad.pausado ? "Reanudar" : "Pausar"}
                      disabled={procesando}
                      onClick={() => manejarPausar(propiedad)}
                    >
                      {propiedad.pausado ? (
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                          <path d="M5 3.5v9l8-4.5Z" />
                        </svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                          <rect x="4" y="3" width="3" height="10" rx="1" />
                          <rect x="9" y="3" width="3" height="10" rx="1" />
                        </svg>
                      )}
                    </button>
                    <button
                      className="icon-btn"
                      title="Editar"
                      disabled={procesando}
                      onClick={() => setPropiedadEditando(propiedad)}
                    >
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M11 2.5 13.5 5 5.5 13H3v-2.5Z"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                    <a
                      className="icon-btn"
                      title="Ver aviso"
                      href={propiedad.url_poligono}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M6.5 3h6.5v6.5M13 3 3 13"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </a>
                    <button
                      className="icon-btn danger"
                      title="Eliminar"
                      disabled={procesando}
                      onClick={() => manejarEliminar(propiedad)}
                    >
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M3.5 4.5h9M6.5 4.5V3h3v1.5M6 7.5v4M10 7.5v4M4.3 4.5l.6 8.2a1 1 0 0 0 1 .8h4.2a1 1 0 0 0 1-.8l.6-8.2"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {modalAbierto && (
        <PropertyModal
          chats={chats}
          onClose={() => setModalAbierto(false)}
          onSaved={(creada) => {
            setModalAbierto(false);
            cargar();
            if (creada) {
              setMensajeInfo(
                "En menos de 1 minuto vas a recibir un mensaje de Telegram confirmando que el monitoreo arrancó.",
              );
              iniciarRefrescoTemporal(creada.id);
            }
          }}
        />
      )}

      {propiedadEditando && (
        <PropertyModal
          chats={chats}
          propiedad={propiedadEditando}
          onClose={() => setPropiedadEditando(null)}
          onSaved={() => {
            setPropiedadEditando(null);
            cargar();
          }}
        />
      )}
    </div>
  );
}
