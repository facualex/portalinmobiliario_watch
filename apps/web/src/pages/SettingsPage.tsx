import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { ChatTelegram } from "../api/types";

export function SettingsPage() {
  const [chats, setChats] = useState<ChatTelegram[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idEditando, setIdEditando] = useState<number | null>(null);
  const [nombreEditado, setNombreEditado] = useState("");
  const [idProcesando, setIdProcesando] = useState<number | null>(null);

  function cargar() {
    api
      .listarChats()
      .then(setChats)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "No se pudo cargar.");
      });
  }

  useEffect(() => {
    cargar();
  }, []);

  function iniciarEdicion(chat: ChatTelegram) {
    setError(null);
    setIdEditando(chat.id);
    setNombreEditado(chat.nombre);
  }

  function cancelarEdicion() {
    setIdEditando(null);
    setNombreEditado("");
  }

  async function guardarEdicion(chat: ChatTelegram) {
    const nuevoNombre = nombreEditado.trim();
    if (!nuevoNombre) {
      setError("El nombre no puede estar vacío.");
      return;
    }
    if (nuevoNombre === chat.nombre) {
      cancelarEdicion();
      return;
    }
    setIdProcesando(chat.id);
    try {
      const actualizado = await api.editarChat(chat.id, { nombre: nuevoNombre });
      setChats((prev) => (prev ?? []).map((c) => (c.id === chat.id ? actualizado : c)));
      cancelarEdicion();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo renombrar el chat.");
    } finally {
      setIdProcesando(null);
    }
  }

  async function manejarEliminar(chat: ChatTelegram) {
    if (!confirm(`¿Eliminar el chat "${chat.nombre}"? Esta acción no se puede deshacer.`)) {
      return;
    }
    setError(null);
    setIdProcesando(chat.id);
    try {
      await api.eliminarChat(chat.id);
      setChats((prev) => (prev ?? []).filter((c) => c.id !== chat.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el chat.");
    } finally {
      setIdProcesando(null);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Configuración</h1>
          <p className="page-sub">Chats de Telegram conectados a esta instancia.</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-list">
        {chats === null && <div className="empty-state">Cargando...</div>}
        {chats?.length === 0 && (
          <div className="empty-state">
            Todavía no conectaste ningún chat. Se conectan desde el modal de
            "Conectar propiedad".
          </div>
        )}
        {chats?.map((chat) => {
          const editando = idEditando === chat.id;
          const procesando = idProcesando === chat.id;
          return (
            <div className="chat-row" key={chat.id}>
              {editando ? (
                <input
                  className="chat-rename-input"
                  type="text"
                  value={nombreEditado}
                  autoFocus
                  disabled={procesando}
                  onChange={(e) => setNombreEditado(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") guardarEdicion(chat);
                    if (e.key === "Escape") cancelarEdicion();
                  }}
                />
              ) : (
                <span>{chat.nombre}</span>
              )}

              <div className="chat-row-right">
                <span className="chat-id mono">chat_id: {chat.chat_id}</span>
                <div className="row-actions">
                  {editando ? (
                    <>
                      <button
                        className="icon-btn"
                        title="Guardar"
                        disabled={procesando}
                        onClick={() => guardarEdicion(chat)}
                      >
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                          <path
                            d="M3 8.5 6.5 12 13 4.5"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                      <button
                        className="icon-btn"
                        title="Cancelar"
                        disabled={procesando}
                        onClick={cancelarEdicion}
                      >
                        ✕
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className="icon-btn"
                        title="Renombrar"
                        disabled={procesando}
                        onClick={() => iniciarEdicion(chat)}
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
                      <button
                        className="icon-btn danger"
                        title="Eliminar"
                        disabled={procesando}
                        onClick={() => manejarEliminar(chat)}
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
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
