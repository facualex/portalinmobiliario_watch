import type { Propiedad } from "../api/types";

interface Props {
  propiedad: Pick<Propiedad, "pausado" | "estado_operativo">;
}

export function StatusPill({ propiedad }: Props) {
  if (propiedad.pausado) {
    return <span className="status-pill is-paused">Pausado</span>;
  }

  if (propiedad.estado_operativo === "error") {
    return <span className="status-pill is-error">Error</span>;
  }

  return <span className="status-pill is-active">Activo</span>;
}
