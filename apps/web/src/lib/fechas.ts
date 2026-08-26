export function formatearRelativo(fechaIso: string | null): string {
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
