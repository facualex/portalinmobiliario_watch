import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { ChatTelegram } from "../api/types";

export function SettingsPage() {
  const [chats, setChats] = useState<ChatTelegram[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listarChats()
      .then(setChats)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "No se pudo cargar.");
      });
  }, []);

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
        {chats?.map((chat) => (
          <div className="chat-row" key={chat.id}>
            <span>{chat.nombre}</span>
            <span className="chat-id mono">chat_id: {chat.chat_id}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
