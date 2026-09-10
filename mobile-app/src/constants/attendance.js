/**
 * Attendance action configuration and labels for the Mobile App.
 */

export const ACTION_CONFIG = {
  check_in: {
    label: 'Registrar Entrada',
    icon: '🟢',
    color: '#16a34a',
    bg: '#f0fdf4',
  },
  break_start: {
    label: 'Iniciar Descanso',
    icon: '☕',
    color: '#d97706',
    bg: '#fffbeb',
  },
  break_end: {
    label: 'Volver al Trabajo',
    icon: '💼',
    color: '#2563eb',
    bg: '#eff6ff',
  },
  check_out: {
    label: 'Registrar Salida',
    icon: '🔴',
    color: '#dc2626',
    bg: '#fef2f2',
  },
  already_completed: {
    label: 'Jornada Completa',
    icon: '✅',
    color: '#6b7280',
    bg: '#f9fafb',
  },
}

export const TYPE_LABELS = {
  check_in: 'Entrada',
  break_start: 'Inicio descanso',
  break_end: 'Fin descanso',
  check_out: 'Salida',
}

export const STATUS_LABELS = {
  on_time: { label: 'En hora' },
  late: { label: 'Tarde' },
  warning: { label: 'Advertencia' },
}
