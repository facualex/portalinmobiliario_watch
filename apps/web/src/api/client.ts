import type {
  ChatTelegram,
  ChatTelegramActualizar,
  ChatTelegramCrear,
  EventoPropiedad,
  Propiedad,
  PropiedadActualizar,
  PropiedadCrear,
  PruebaUrl,
  PruebaUrlCrear,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function solicitud<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });

  if (!respuesta.ok) {
    let detalle = respuesta.statusText;
    try {
      const cuerpo = await respuesta.json();
      if (typeof cuerpo.detail === "string") {
        // HTTPException(status, "mensaje") nuestro, ej. desde los routers.
        detalle = cuerpo.detail;
      } else if (Array.isArray(cuerpo.detail)) {
        // Error de validación automático de FastAPI/Pydantic (422): una lista
        // de objetos {msg, loc, type}, no un string.
        detalle =
          cuerpo.detail
            .map((e: { msg?: string }) => e.msg?.replace(/^Value error, /, ""))
            .filter(Boolean)
            .join(" | ") || detalle;
      }
    } catch {
      // el cuerpo de error no era JSON, nos quedamos con statusText
    }
    throw new ApiError(respuesta.status, detalle);
  }

  if (respuesta.status === 204) {
    return undefined as T;
  }
  return (await respuesta.json()) as T;
}

export const api = {
  listarPropiedades: () => solicitud<Propiedad[]>("/propiedades"),

  crearPropiedad: (payload: PropiedadCrear) =>
    solicitud<Propiedad>("/propiedades", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  editarPropiedad: (id: number, payload: PropiedadActualizar) =>
    solicitud<Propiedad>(`/propiedades/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  pausarPropiedad: (id: number) =>
    solicitud<Propiedad>(`/propiedades/${id}/pausar`, { method: "POST" }),

  reanudarPropiedad: (id: number) =>
    solicitud<Propiedad>(`/propiedades/${id}/reanudar`, { method: "POST" }),

  eliminarPropiedad: (id: number) =>
    solicitud<void>(`/propiedades/${id}`, { method: "DELETE" }),

  listarEventos: (propiedadId: number) =>
    solicitud<EventoPropiedad[]>(`/propiedades/${propiedadId}/eventos`),

  listarChats: () => solicitud<ChatTelegram[]>("/chats-telegram"),

  crearChat: (payload: ChatTelegramCrear) =>
    solicitud<ChatTelegram>("/chats-telegram", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  editarChat: (id: number, payload: ChatTelegramActualizar) =>
    solicitud<ChatTelegram>(`/chats-telegram/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  eliminarChat: (id: number) =>
    solicitud<void>(`/chats-telegram/${id}`, { method: "DELETE" }),

  crearPruebaUrl: (payload: PruebaUrlCrear) =>
    solicitud<PruebaUrl>("/pruebas-url", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  obtenerPruebaUrl: (id: number) => solicitud<PruebaUrl>(`/pruebas-url/${id}`),
};
