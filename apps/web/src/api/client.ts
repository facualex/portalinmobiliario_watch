import type {
  ChatTelegram,
  ChatTelegramCrear,
  Propiedad,
  PropiedadActualizar,
  PropiedadCrear,
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
      detalle = cuerpo.detail ?? detalle;
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

  ejecutarAhora: (id: number) =>
    solicitud<Propiedad>(`/propiedades/${id}/ejecutar-ahora`, { method: "POST" }),

  eliminarPropiedad: (id: number) =>
    solicitud<void>(`/propiedades/${id}`, { method: "DELETE" }),

  listarChats: () => solicitud<ChatTelegram[]>("/chats-telegram"),

  crearChat: (payload: ChatTelegramCrear) =>
    solicitud<ChatTelegram>("/chats-telegram", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
