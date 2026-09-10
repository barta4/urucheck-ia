/**
 * Common attendance type and status label definitions for Frontend Admin.
 */

export const TYPE_LABELS = {
  check_in: 'Entrada',
  break_start: 'Inicio descanso',
  break_end: 'Fin descanso',
  check_out: 'Salida',
}

export const STATUS_LABELS = {
  on_time: { label: 'En hora', class: 'bg-green-100 text-green-700' },
  late: { label: 'Tarde', class: 'bg-red-100 text-red-700' },
  warning: { label: 'Advertencia', class: 'bg-yellow-100 text-yellow-700' },
}
