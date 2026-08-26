import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { EventoPropiedad, EventoTipo } from "../api/types";
import { formatearRelativo } from "../lib/fechas";

interface Props {
  propiedadId: number;
  propiedadNombre: string;
  onClose: () => void;
}

const ICONOS: Record<EventoTipo, string> = {
  activacion: "✅",
  cambio: "🔔",
  error: "🚨",
};

export function PropertyHistoryModal({ propiedadId, propiedadNombre, onClose }: Props) {
  const [eventos, setEventos] = useState<EventoPropiedad[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listarEventos(propiedadId)
      .then(setEventos)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "No se pudo cargar el historial.");
      });
  }, [propiedadId]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Historial · {propiedadNombre}</h2>
          <button className="modal-close" onClick={onClose} type="button">
            ✕
          </button>
        </div>
        <p className="modal-sub">Los últimos cambios, activaciones y errores registrados.</p>

        {error && <div className="error-banner">{error}</div>}

        {eventos === null && !error && <div className="empty-state">Cargando...</div>}
        {eventos?.length === 0 && (
          <div className="empty-state">
            Todavía no hay eventos: se registran en cuanto el worker corra por
            primera vez para esta propiedad.
          </div>
        )}

        {eventos && eventos.length > 0 && (
          <div className="history-list">
            {eventos.map((evento) => (
              <div className={`history-item is-${evento.tipo}`} key={evento.id}>
                <span className="history-icon">{ICONOS[evento.tipo]}</span>
                <div className="history-body">
                  <span className="history-mensaje">{evento.mensaje}</span>
                  <span className="history-fecha mono">
                    {formatearRelativo(evento.ocurrido_en)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button className="btn-secondary" type="button" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
