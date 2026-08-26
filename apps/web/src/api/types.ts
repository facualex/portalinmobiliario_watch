// Reflejan los modelos de packages/lindero_core/src/lindero_core/models.py

export type FrecuenciaTipo = "hora_fija" | "intervalo";
export type EstadoOperativo = "activo" | "error";

export interface ChatTelegram {
  id: number;
  chat_id: string;
  nombre: string;
  creado_en: string;
}

export interface Propiedad {
  id: number;
  nombre: string;
  url_poligono: string;
  comuna: string | null;
  precio_referencia: string | null;
  chat_telegram_id: number;
  frecuencia_tipo: FrecuenciaTipo;
  hora_ejecucion: string | null;
  intervalo_horas: number | null;
  tz: string;
  pausado: boolean;
  estado_operativo: EstadoOperativo;
  ultimo_recuento: string | null;
  ultima_verificacion_en: string | null;
  ultimo_error: string | null;
  proxima_ejecucion_en: string | null;
  creado_en: string;
  actualizado_en: string;
}

export interface PropiedadCrear {
  nombre: string;
  url_poligono: string;
  comuna?: string | null;
  precio_referencia?: string | null;
  chat_telegram_id: number;
  frecuencia_tipo: FrecuenciaTipo;
  hora_ejecucion?: string | null;
  intervalo_horas?: number | null;
  tz: string;
}

export interface PropiedadActualizar {
  nombre?: string;
  url_poligono?: string;
  comuna?: string | null;
  precio_referencia?: string | null;
  chat_telegram_id?: number;
  frecuencia_tipo?: FrecuenciaTipo;
  hora_ejecucion?: string | null;
  intervalo_horas?: number | null;
  tz?: string;
}

export interface ChatTelegramCrear {
  chat_id: string;
  nombre: string;
}
