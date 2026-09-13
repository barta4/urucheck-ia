import { useState, useEffect, useMemo } from 'react'
import {
  UserPlus,
  Upload,
  Download,
  Edit2,
  Calendar,
  Camera,
  Trash2,
  UserCheck,
  UserX,
  FileSpreadsheet,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  X,
  Smartphone,
  Clock,
  Plus
} from 'lucide-react'
import api from '../api'
import { useToast } from '../context/ToastContext'
import ConfirmModal from '../components/ConfirmModal'
import { downloadBlob, downloadCsvFromData } from '../utils/fileDownloader'

const DAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const FULL_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

const timeToMinutes = (t) => {
  if (!t) return 0
  const parts = t.split(':')
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10)
}

const normalizeDaysList = (days) => {
  if (!days) return []
  if (Array.isArray(days)) return days.map(d => parseInt(d, 10)).filter(d => !isNaN(d))
  if (typeof days === 'string') {
    return days.replace(/[{}[\]]/g, '').split(',').map(d => parseInt(d.trim(), 10)).filter(d => !isNaN(d))
  }
  return []
}

const getScheduleIntervals = (days, startTime, endTime) => {
  const normDays = normalizeDaysList(days)
  if (!normDays.length || !startTime || !endTime) return []
  const startMin = timeToMinutes(startTime)
  const endMin = timeToMinutes(endTime)
  const intervals = []

  if (startMin < endMin) {
    for (const d of normDays) {
      intervals.push({ day: d, start: startMin, end: endMin })
    }
  } else if (startMin > endMin) {
    for (const d of normDays) {
      intervals.push({ day: d, start: startMin, end: 1440 })
      const nextDay = (d % 7) + 1
      intervals.push({ day: nextDay, start: 0, end: endMin })
    }
  }
  return intervals
}

const findScheduleConflict = (schedulesList, newDays, newStart, newEnd, excludeId = null) => {
  if (!schedulesList || !schedulesList.length) return null
  const newIntervals = getScheduleIntervals(newDays, newStart, newEnd)
  for (const s of schedulesList) {
    if (excludeId && String(s.id) === String(excludeId)) continue
    const oldIntervals = getScheduleIntervals(s.day_of_week, s.start_time, s.end_time)
    for (const nInt of newIntervals) {
      for (const oInt of oldIntervals) {
        if (nInt.day === oInt.day && nInt.start < oInt.end && oInt.start < nInt.end) {
          const dayName = FULL_DAYS[nInt.day - 1] || `Día ${nInt.day}`
          const slotLabel = s.slot_name || 'Turno Regular'
          const startStr = s.start_time?.slice(0, 5)
          const endStr = s.end_time?.slice(0, 5)
          return {
            conflict: true,
            day: nInt.day,
            dayName,
            schedule: s,
            message: `Conflicto de horario: El día ${dayName} se superpone con '${slotLabel}' (${startStr} – ${endStr}). No se permiten turnos en el mismo horario.`
          }
        }
      }
    }
  }
  return null
}

function Modal({ title, onClose, children, maxWidth = 'max-w-lg' }) {
  return (
    <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className={`bg-white rounded-2xl shadow-2xl w-full ${maxWidth} max-h-[90vh] overflow-hidden flex flex-col border border-gray-100`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <h3 className="font-semibold text-gray-900 text-base">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 rounded-lg p-1 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

export default function Employees() {
  const { success, error, info, warning } = useToast()
  const [employees, setEmployees] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [showEdit, setShowEdit] = useState(null)
  const [showSchedule, setShowSchedule] = useState(null)
  const [showFaceEnroll, setShowFaceEnroll] = useState(null)
  const [schedules, setSchedules] = useState([])
  const [geofences, setGeofences] = useState([])
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'employee', document_id: '', address: '', phone: '' })
  const [editForm, setEditForm] = useState({ name: '', email: '', password: '', role: 'employee', document_id: '', address: '', phone: '' })
  const [schedForm, setSchedForm] = useState({
    slot_name: '',
    day_of_week: [],
    start_time: '09:00',
    end_time: '18:00',
    tolerance_minutes: 5,
    geofence_id: '',
    break_mode: 'flexible',
    break_duration_minutes: 45,
    break_start_time: '13:00',
    break_end_time: '14:00'
  })
  const [loading, setLoading] = useState(false)
  const [facePhoto, setFacePhoto] = useState(null)
  const [facePreview, setFacePreview] = useState(null)
  const [faceStatuses, setFaceStatuses] = useState({})

  // Confirm Modal state
  const [confirmState, setConfirmState] = useState({
    isOpen: false,
    title: '',
    message: '',
    confirmVariant: 'danger',
    onConfirm: null,
  })

  // Bulk import state
  const [bulkRows, setBulkRows] = useState([])
  const [bulkErrors, setBulkErrors] = useState([])
  const [isImporting, setIsImporting] = useState(false)

  const fetchEmployees = async () => {
    try {
      const res = await api.get('/employees/')
      setEmployees(res.data)
      res.data.forEach(emp => fetchFaceStatus(emp.id))
    } catch (e) {
      error('Error al cargar la lista de empleados')
    }
  }

  const fetchSchedules = async (empId) => {
    try {
      const res = await api.get(`/employees/${empId}/schedules`)
      setSchedules(res.data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { fetchEmployees() }, [])

  // ─── Face enrollment ──────────────────────────────────────────────
  const fetchFaceStatus = async (empId) => {
    try {
      const res = await api.get(`/employees/${empId}/face-status`)
      setFaceStatuses(prev => ({ ...prev, [empId]: res.data.has_face_reference }))
    } catch {
      // ignore
    }
  }

  const createEmployee = async (e) => {
    e.preventDefault()
    if (!form.password || form.password.length < 8) {
      error('La contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (!/\d/.test(form.password)) {
      error('La contraseña debe incluir al menos un número.')
      return
    }
    if (!/[A-Z]/.test(form.password)) {
      error('La contraseña debe incluir al menos una letra mayúscula.')
      return
    }

    setLoading(true)
    try {
      await api.post('/employees/', form)
      success(`Empleado ${form.name} creado exitosamente`)
      setShowCreate(false)
      setForm({ name: '', email: '', password: '', role: 'employee', document_id: '', address: '', phone: '' })
      fetchEmployees()
    } catch (err) {
      error(err.response?.data?.detail || 'Error al crear empleado')
    } finally { setLoading(false) }
  }

  const openEdit = (emp) => {
    setEditForm({
      name: emp.name,
      email: emp.email,
      password: '',
      role: emp.role,
      document_id: emp.document_id || '',
      address: emp.address || '',
      phone: emp.phone || ''
    })
    setShowEdit(emp)
  }

  const saveEdit = async (e) => {
    e.preventDefault()
    if (editForm.password) {
      if (editForm.password.length < 8) {
        error('La contraseña debe tener al menos 8 caracteres.')
        return
      }
      if (!/\d/.test(editForm.password)) {
        error('La contraseña debe incluir al menos un número.')
        return
      }
      if (!/[A-Z]/.test(editForm.password)) {
        error('La contraseña debe incluir al menos una letra mayúscula.')
        return
      }
    }

    setLoading(true)
    try {
      const payload = {
        name: editForm.name,
        email: editForm.email,
        role: editForm.role,
        document_id: editForm.document_id,
        address: editForm.address,
        phone: editForm.phone,
      }
      if (editForm.password) payload.password = editForm.password
      await api.patch(`/employees/${showEdit.id}`, payload)
      success('Datos del empleado actualizados')
      setShowEdit(null)
      fetchEmployees()
    } catch (err) {
      error(err.response?.data?.detail || 'Error al guardar los cambios')
    } finally { setLoading(false) }
  }

  const toggleActive = (emp) => {
    setConfirmState({
      isOpen: true,
      title: emp.active ? '¿Desactivar empleado?' : '¿Activar empleado?',
      message: emp.active
        ? `Al desactivar a ${emp.name}, no podrá registrar asistencias ni iniciar sesión en la aplicación móvil.`
        : `Se reactivará el acceso de ${emp.name} al sistema de asistencia.`,
      confirmVariant: emp.active ? 'danger' : 'primary',
      onConfirm: async () => {
        try {
          await api.patch(`/employees/${emp.id}`, { active: !emp.active })
          success(emp.active ? 'Empleado desactivado' : 'Empleado activado')
          setConfirmState(prev => ({ ...prev, isOpen: false }))
          fetchEmployees()
        } catch (e) {
          error('Error al actualizar estado del empleado')
        }
      }
    })
  }

  const handleResetDevice = (emp) => {
    setConfirmState({
      isOpen: true,
      title: '¿Desvincular Dispositivo?',
      message: `Se desvinculará el teléfono actual de ${emp.name}. Podrá iniciar sesión desde un nuevo dispositivo móvil en su próxima marca.`,
      confirmVariant: 'warning',
      onConfirm: async () => {
        try {
          await api.post(`/employees/${emp.id}/reset-device`)
          success(`Dispositivo de ${emp.name} desvinculado con éxito`)
          setConfirmState(prev => ({ ...prev, isOpen: false }))
        } catch (e) {
          error('Error al desvincular dispositivo')
        }
      }
    })
  }

  const openSchedule = async (emp) => {
    setSchedForm({
      slot_name: '',
      day_of_week: [],
      start_time: '09:00',
      end_time: '18:00',
      tolerance_minutes: 5,
      geofence_id: '',
      break_mode: 'flexible',
      break_duration_minutes: 45,
      break_start_time: '',
      break_end_time: ''
    })
    setShowSchedule(emp)
    fetchSchedules(emp.id)
    try {
      const res = await api.get('/dashboard/geofences')
      setGeofences(res.data)
    } catch (e) {
      console.error('Error al cargar geocercas', e)
    }
  }

  const addSchedule = async (e) => {
    e.preventDefault()
    if (!schedForm.day_of_week || schedForm.day_of_week.length === 0) {
      warning('Debes seleccionar al menos un día de la semana (ej. Lun, Mar, Mié)')
      return
    }
    if (!schedForm.start_time) {
      warning('Debes especificar la hora de entrada del turno')
      return
    }
    if (!schedForm.end_time) {
      warning('Debes especificar la hora de salida del turno')
      return
    }
    if (schedForm.start_time === schedForm.end_time) {
      warning('La hora de entrada y salida no pueden ser iguales')
      return
    }
    if (schedForm.break_mode === 'fixed') {
      if (!schedForm.break_start_time || !schedForm.break_end_time) {
        warning('Para descanso en horario fijo, debes ingresar tanto la hora de inicio como la de fin del descanso')
        return
      }
      if (schedForm.break_start_time === schedForm.break_end_time) {
        warning('La hora de inicio y de fin del descanso fijo no pueden ser iguales')
        return
      }
    }
    if (schedForm.break_mode === 'flexible') {
      const dur = parseInt(schedForm.break_duration_minutes, 10)
      if (isNaN(dur) || dur <= 0 || dur > 360) {
        warning('La duración del descanso flexible debe ser un número entre 1 y 360 minutos')
        return
      }
    }
    const tol = parseInt(schedForm.tolerance_minutes, 10)
    if (isNaN(tol) || tol < 0 || tol > 120) {
      warning('La tolerancia debe ser un valor numérico entre 0 y 120 minutos')
      return
    }

    const conflict = findScheduleConflict(schedules, schedForm.day_of_week, schedForm.start_time, schedForm.end_time)
    if (conflict) {
      warning(conflict.message)
      return
    }
    try {
      await api.post(`/employees/${showSchedule.id}/schedules`, {
        employee_id: showSchedule.id,
        slot_name: schedForm.slot_name ? schedForm.slot_name.trim() : null,
        day_of_week: schedForm.day_of_week,
        start_time: schedForm.start_time,
        end_time: schedForm.end_time,
        tolerance_minutes: tol,
        geofence_id: schedForm.geofence_id || null,
        break_mode: schedForm.break_mode || 'flexible',
        break_duration_minutes: schedForm.break_mode === 'flexible' ? (parseInt(schedForm.break_duration_minutes, 10) || 45) : null,
        break_start_time: schedForm.break_mode === 'fixed' ? schedForm.break_start_time : null,
        break_end_time: schedForm.break_mode === 'fixed' ? schedForm.break_end_time : null
      })
      success('Horario asignado correctamente')
      setSchedForm(f => ({
        ...f,
        slot_name: '',
        day_of_week: [],
        geofence_id: '',
        break_start_time: '',
        break_end_time: ''
      }))
      fetchSchedules(showSchedule.id)
    } catch (err) {
      const detail = err.response?.data?.detail
      error(detail || err.message || 'Error al guardar el horario')
    }
  }

  const deleteSchedule = async (schedId) => {
    try {
      await api.delete(`/employees/${showSchedule.id}/schedules/${schedId}`)
      success('Horario eliminado correctamente')
      fetchSchedules(showSchedule.id)
    } catch (e) {
      error(e.response?.data?.detail || 'Error al eliminar horario')
    }
  }

  const toggleDay = (day) => {
    setSchedForm(f => ({
      ...f,
      day_of_week: f.day_of_week.includes(day)
        ? f.day_of_week.filter(d => d !== day)
        : [...f.day_of_week, day]
    }))
  }

  // ─── Face enrollment ──────────────────────────────────────────────
  const handleFacePhoto = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setFacePhoto(file)
    setFacePreview(URL.createObjectURL(file))
  }

  const enrollFace = async (e) => {
    e.preventDefault()
    if (!facePhoto || !showFaceEnroll) return
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('photo', facePhoto)
      await api.post(`/employees/${showFaceEnroll.id}/face-enroll`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setFaceStatuses(prev => ({ ...prev, [showFaceEnroll.id]: true }))
      setShowFaceEnroll(null)
      setFacePhoto(null)
      setFacePreview(null)
      success('Rostro registrado y verificado correctamente')
    } catch (err) {
      error(err.response?.data?.detail || 'Error al registrar rostro')
    } finally {
      setLoading(false)
    }
  }

  const removeFaceEnrollment = (emp) => {
    setConfirmState({
      isOpen: true,
      title: '¿Eliminar referencia facial?',
      message: `¿Estás seguro de que deseas eliminar la foto de referencia facial de ${emp.name}? El empleado no podrá marcar si la verificación biométrica es obligatoria.`,
      confirmVariant: 'danger',
      onConfirm: async () => {
        try {
          await api.delete(`/employees/${emp.id}/face-enroll`)
          setFaceStatuses(prev => ({ ...prev, [emp.id]: false }))
          success('Referencia facial eliminada')
          setConfirmState(prev => ({ ...prev, isOpen: false }))
          setShowFaceEnroll(null)
        } catch (err) {
          error(err.response?.data?.detail || 'Error al eliminar')
        }
      }
    })
  }

  const openFaceEnroll = (emp) => {
    setShowFaceEnroll(emp)
    setFacePhoto(null)
    setFacePreview(null)
    fetchFaceStatus(emp.id)
  }

  // ─── Bulk Import & Export ─────────────────────────────────────────
  const downloadTemplate = () => {
    const header = "Nombre,Email,Password,Rol,Cedula,Telefono,Direccion\n"
    const example = "Juan Perez,juan@empresa.com,123456,employee,1.234.567-8,099123456,Av. 18 de Julio 1234\nMaria Gomez,maria@empresa.com,123456,admin,4.567.890-1,098765432,Bvar. Artigas 567"
    downloadBlob(header + example, 'plantilla_empleados.csv', 'text/csv;charset=utf-8;')
    info('Plantilla descargada')
  }

  const exportEmployees = () => {
    if (employees.length === 0) {
      warning('No hay empleados para exportar')
      return
    }
    const headers = ['Nombre', 'Email', 'Rol', 'Estado', 'Cedula', 'Telefono', 'Direccion']
    const rows = employees.map(e => [
      e.name,
      e.email,
      e.role,
      e.active ? 'Activo' : 'Inactivo',
      e.document_id || '',
      e.phone || '',
      e.address || ''
    ])
    downloadCsvFromData(`empleados_${new Date().toISOString().slice(0, 10)}.csv`, headers, rows)
    success('Listado de empleados exportado en CSV')
  }

  const handleFileUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target.result
      const lines = text.split(/\r\n|\n/).filter(line => line.trim() !== '')
      if (lines.length <= 1) {
        error('El archivo CSV está vacío o solo contiene encabezados')
        return
      }

      // Ignore header, parse rows
      const parsed = []
      const errs = []
      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map(p => p.trim().replace(/^["']|["']$/g, ''))
        const [name, email, password, role, document_id, phone, address] = parts
        
        let rowError = null
        if (!name) rowError = 'Falta el nombre'
        else if (!email || !email.includes('@')) rowError = 'Email inválido'

        if (rowError) {
          errs.push(`Línea ${i + 1}: ${rowError}`)
        } else {
          parsed.push({
            name,
            email,
            password: password || '123456',
            role: role === 'admin' ? 'admin' : 'employee',
            document_id: document_id || null,
            phone: phone || null,
            address: address || null,
            valid: true
          })
        }
      }

      setBulkRows(parsed)
      setBulkErrors(errs)
      setShowBulkImport(true)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const executeBulkImport = async () => {
    if (bulkRows.length === 0) return
    setIsImporting(true)
    try {
      const payload = {
        employees: bulkRows.map(r => ({
          name: r.name,
          email: r.email,
          password: r.password,
          role: r.role,
          document_id: r.document_id,
          phone: r.phone,
          address: r.address
        }))
      }
      const res = await api.post('/employees/bulk', payload)
      success(res.data.message)
      if (res.data.errors && res.data.errors.length > 0) {
        warning(`Hubo advertencias: ${res.data.errors.join(' ')}`)
      }
      setShowBulkImport(false)
      setBulkRows([])
      setBulkErrors([])
      fetchEmployees()
    } catch (err) {
      error(err.response?.data?.detail || 'Error durante la importación masiva')
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header with Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <UserPlus className="w-7 h-7 text-blue-600" />
            Gestión de Empleados
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Administra altas, perfiles, turnos de asistencia y reconocimiento facial.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={exportEmployees}
            className="px-3.5 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 shadow-sm flex items-center gap-2 transition"
          >
            <Download className="w-4 h-4 text-gray-500" />
            Exportar
          </button>

          <label className="px-3.5 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 shadow-sm flex items-center gap-2 transition cursor-pointer">
            <Upload className="w-4 h-4 text-gray-500" />
            Importar CSV
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>

          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-sm flex items-center gap-2 transition"
          >
            <UserPlus className="w-4 h-4" />
            Nuevo Empleado
          </button>
        </div>
      </div>

      {/* Employees Table Card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50/80 text-gray-600 text-xs uppercase tracking-wider font-semibold border-b border-gray-100">
              <tr>
                <th className="px-6 py-4">Nombre / C.I.</th>
                <th className="px-6 py-4">Contacto</th>
                <th className="px-6 py-4">Rol</th>
                <th className="px-6 py-4">Estado</th>
                <th className="px-6 py-4">Biometría</th>
                <th className="px-6 py-4 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {employees.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No hay empleados registrados. Agrega uno nuevo o importa una plantilla CSV.
                  </td>
                </tr>
              ) : (
                employees.map(emp => (
                  <tr key={emp.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-gray-900">{emp.name}</div>
                      <div className="text-xs text-gray-500 font-mono mt-0.5">
                        {emp.document_id ? `C.I. ${emp.document_id}` : 'Sin C.I.'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-gray-900">{emp.email}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{emp.phone || 'Sin teléfono'}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        emp.role === 'admin'
                          ? 'bg-purple-50 text-purple-700 border border-purple-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {emp.role === 'admin' ? 'Administrador' : 'Empleado'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        emp.active
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-gray-100 text-gray-600 border border-gray-200'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${emp.active ? 'bg-emerald-500' : 'bg-gray-400'}`} />
                        {emp.active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => openFaceEnroll(emp)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium transition ${
                          faceStatuses[emp.id]
                            ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                            : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200'
                        }`}
                      >
                        <Camera className="w-3.5 h-3.5" />
                        {faceStatuses[emp.id] ? 'Verificado' : 'Registrar'}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openEdit(emp)}
                          className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition"
                          title="Editar empleado"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => openSchedule(emp)}
                          className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition"
                          title="Gestionar horarios"
                        >
                          <Calendar className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleResetDevice(emp)}
                          className="p-2 text-gray-500 hover:text-amber-600 hover:bg-amber-50 rounded-xl transition"
                          title="Desvincular teléfono"
                        >
                          <Smartphone className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => toggleActive(emp)}
                          className={`p-2 rounded-xl transition ${
                            emp.active
                              ? 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                              : 'text-gray-400 hover:text-emerald-600 hover:bg-emerald-50'
                          }`}
                          title={emp.active ? 'Desactivar' : 'Activar'}
                        >
                          {emp.active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bulk Import Preview Modal */}
      {showBulkImport && (
        <Modal
          title="Importación Masiva de Empleados"
          maxWidth="max-w-2xl"
          onClose={() => setShowBulkImport(false)}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-blue-50 p-4 rounded-xl border border-blue-100">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-6 h-6 text-blue-600" />
                <div>
                  <p className="text-sm font-semibold text-blue-900">
                    {bulkRows.length} empleados listos para importar
                  </p>
                  <p className="text-xs text-blue-700">
                    Revisa las filas antes de confirmar la carga masiva.
                  </p>
                </div>
              </div>
              <button
                onClick={downloadTemplate}
                className="text-xs font-semibold text-blue-700 underline hover:text-blue-900"
              >
                Descargar plantilla
              </button>
            </div>

            {bulkErrors.length > 0 && (
              <div className="bg-red-50 p-3.5 rounded-xl border border-red-200 text-xs text-red-700 space-y-1">
                <p className="font-semibold flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 text-red-600" />
                  Filas con errores ignoradas:
                </p>
                {bulkErrors.map((err, i) => (
                  <p key={i}>• {err}</p>
                ))}
              </div>
            )}

            <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-xl divide-y text-xs">
              {bulkRows.map((r, i) => (
                <div key={i} className="p-3 flex items-center justify-between bg-white hover:bg-gray-50">
                  <div>
                    <span className="font-semibold text-gray-900">{r.name}</span>
                    <span className="text-gray-500 ml-2">({r.email})</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-mono">
                    {r.role}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t">
              <button
                type="button"
                onClick={() => setShowBulkImport(false)}
                className="px-4 py-2 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={isImporting || bulkRows.length === 0}
                onClick={executeBulkImport}
                className="px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-xl hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                {isImporting ? 'Importando...' : `Confirmar Importación (${bulkRows.length})`}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Create Employee Modal */}
      {showCreate && (
        <Modal title="Nuevo Empleado" onClose={() => setShowCreate(false)}>
          <form onSubmit={createEmployee} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Nombre Completo</label>
              <input
                required
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="Ej. Juan Pérez"
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">C.I. / Documento</label>
                <input
                  value={form.document_id}
                  onChange={e => setForm({ ...form, document_id: e.target.value })}
                  placeholder="Ej. 1.234.567-8"
                  className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Teléfono</label>
                <input
                  value={form.phone}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                  placeholder="Ej. 099123456"
                  className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Dirección</label>
              <input
                value={form.address}
                onChange={e => setForm({ ...form, address: e.target.value })}
                placeholder="Ej. Av. 18 de Julio 1234"
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Email</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                placeholder="correo@empresa.com"
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Contraseña Inicial</label>
              <input
                type="password"
                required
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <p className="text-[11px] text-gray-400 mt-1">Mínimo 8 caracteres, al menos un número y una mayúscula.</p>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Rol</label>
              <select
                value={form.role}
                onChange={e => setForm({ ...form, role: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="employee">Empleado</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white rounded-xl py-3 font-semibold hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
            >
              {loading ? 'Creando empleado...' : 'Crear Empleado'}
            </button>
          </form>
        </Modal>
      )}

      {/* Edit Employee Modal */}
      {showEdit && (
        <Modal title={`Editar Empleado — ${showEdit.name}`} onClose={() => setShowEdit(null)}>
          <form onSubmit={saveEdit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Nombre Completo</label>
              <input
                required
                value={editForm.name}
                onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">C.I. / Documento</label>
                <input
                  value={editForm.document_id}
                  onChange={e => setEditForm({ ...editForm, document_id: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Teléfono</label>
                <input
                  value={editForm.phone}
                  onChange={e => setEditForm({ ...editForm, phone: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Dirección</label>
              <input
                value={editForm.address}
                onChange={e => setEditForm({ ...editForm, address: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Email</label>
              <input
                type="email"
                required
                value={editForm.email}
                onChange={e => setEditForm({ ...editForm, email: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                Nueva Contraseña <span className="text-gray-400 font-normal">(dejar en blanco para no cambiar)</span>
              </label>
              <input
                type="password"
                value={editForm.password}
                onChange={e => setEditForm({ ...editForm, password: e.target.value })}
                placeholder="••••••••"
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <p className="text-[11px] text-gray-400 mt-1">Mínimo 8 caracteres, al menos un número y una mayúscula.</p>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Rol</label>
              <select
                value={editForm.role}
                onChange={e => setEditForm({ ...editForm, role: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="employee">Empleado</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white rounded-xl py-3 font-semibold hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
            >
              {loading ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </form>
        </Modal>
      )}

      {/* Schedule Modal */}
      {showSchedule && (
        <Modal title={`Gestión de Turnos y Descansos — ${showSchedule.name}`} onClose={() => setShowSchedule(null)}>
          <div className="space-y-5">
            {schedules.length === 0 ? (
              <div className="text-center py-4 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                <Clock className="w-8 h-8 text-gray-400 mx-auto mb-1.5" />
                <p className="text-gray-500 text-xs font-medium">No tiene turnos asignados actualmente.</p>
              </div>
            ) : (
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {schedules.map(s => {
                  const gf = s.geofence_id ? geofences.find(g => g.id === s.geofence_id) : null
                  const conflict = findScheduleConflict(schedules, s.day_of_week, s.start_time, s.end_time, s.id)
                  return (
                    <div
                      key={s.id}
                      className={`flex items-center justify-between rounded-2xl p-3.5 shadow-sm transition border ${
                        conflict
                          ? 'bg-amber-50/40 border-amber-300 hover:border-amber-400'
                          : 'bg-white border-gray-200/80 hover:border-blue-200'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900 text-xs tracking-tight">
                            {s.slot_name || 'Turno Regular'}
                          </span>
                          <span className="text-[11px] font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                            {s.start_time?.slice(0, 5)} – {s.end_time?.slice(0, 5)}
                          </span>
                          {gf && (
                            <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md flex items-center gap-1">
                              📍 {gf.name}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-wrap text-[11px] text-gray-500">
                          <span>📅 {s.day_of_week.map(d => DAYS[d - 1]).join(', ')}</span>
                          <span>•</span>
                          <span>±{s.tolerance_minutes}m tol.</span>
                          <span>•</span>
                          {s.break_mode === 'none' ? (
                            <span className="text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded font-medium">Sin descanso</span>
                          ) : s.break_mode === 'fixed' ? (
                            <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded font-medium">
                              ☕ Fijo: {s.break_start_time?.slice(0, 5)} - {s.break_end_time?.slice(0, 5)}
                            </span>
                          ) : (
                            <span className="text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded font-medium">
                              ☕ Flexible: {s.break_duration_minutes || 45} min
                            </span>
                          )}
                        </div>
                        {conflict && (
                          <div className="flex items-center gap-1.5 text-[11px] font-medium text-amber-800 bg-amber-100/70 border border-amber-200 px-2 py-0.5 rounded-lg mt-1 w-fit">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                            <span>Conflicto: se superpone los <strong>{conflict.dayName}</strong> con <em>{conflict.schedule.slot_name || 'otro turno'}</em> ({conflict.schedule.start_time?.slice(0, 5)} – {conflict.schedule.end_time?.slice(0, 5)})</span>
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => deleteSchedule(s.id)}
                        className="text-gray-400 hover:text-red-600 p-2 rounded-xl hover:bg-red-50 transition"
                        title="Eliminar turno"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="border-t border-gray-100 pt-4">
              <p className="font-bold text-xs uppercase tracking-wider text-gray-700 mb-3 flex items-center gap-1.5">
                <Plus className="w-4 h-4 text-blue-600" />
                Asignar Nuevo Turno / Ubicación
              </p>
              <form onSubmit={addSchedule} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Nombre / Etiqueta del Turno (Opcional)</label>
                  <input
                    type="text"
                    placeholder="Ej. Turno Mañana - Sucursal Centro"
                    value={schedForm.slot_name}
                    onChange={e => setSchedForm({ ...schedForm, slot_name: e.target.value })}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Días Laborales</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {DAYS.map((d, i) => (
                      <button
                        type="button"
                        key={i}
                        onClick={() => toggleDay(i + 1)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                          schedForm.day_of_week.includes(i + 1)
                            ? 'bg-blue-600 text-white shadow-sm'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Hora Entrada</label>
                    <input
                      type="time"
                      value={schedForm.start_time}
                      onChange={e => setSchedForm({ ...schedForm, start_time: e.target.value })}
                      className="w-full border border-gray-200 rounded-xl px-2.5 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Hora Salida</label>
                    <input
                      type="time"
                      value={schedForm.end_time}
                      onChange={e => setSchedForm({ ...schedForm, end_time: e.target.value })}
                      className="w-full border border-gray-200 rounded-xl px-2.5 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Tolerancia (min)</label>
                    <input
                      type="number"
                      value={schedForm.tolerance_minutes}
                      min={0}
                      max={60}
                      onChange={e => setSchedForm({ ...schedForm, tolerance_minutes: parseInt(e.target.value, 10) || 0 })}
                      className="w-full border border-gray-200 rounded-xl px-2.5 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Ubicación Requerida para este Horario</label>
                  <select
                    value={schedForm.geofence_id}
                    onChange={e => setSchedForm({ ...schedForm, geofence_id: e.target.value })}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">Todas las ubicaciones permitidas</option>
                    {geofences.map(gf => (
                      <option key={gf.id} value={gf.id}>📍 {gf.name}</option>
                    ))}
                  </select>
                </div>

                {/* Break Configuration */}
                <div className="bg-gray-50/80 border border-gray-200/70 rounded-2xl p-3 space-y-2.5">
                  <label className="block text-xs font-semibold text-gray-700">☕ Configuración de Descanso / Almuerzo</label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { id: 'none', label: 'Sin descanso' },
                      { id: 'flexible', label: 'Flexible' },
                      { id: 'fixed', label: 'Horario Fijo' }
                    ].map(tab => (
                      <button
                        type="button"
                        key={tab.id}
                        onClick={() => setSchedForm({ ...schedForm, break_mode: tab.id })}
                        className={`py-1.5 rounded-xl text-xs font-semibold transition ${
                          schedForm.break_mode === tab.id
                            ? 'bg-white text-blue-600 shadow-sm border border-gray-200'
                            : 'text-gray-500 hover:text-gray-800'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {schedForm.break_mode === 'flexible' && (
                    <div className="pt-1">
                      <label className="block text-[11px] text-gray-500 mb-1">Duración Máxima Permitida</label>
                      <select
                        value={schedForm.break_duration_minutes}
                        onChange={e => setSchedForm({ ...schedForm, break_duration_minutes: parseInt(e.target.value, 10) })}
                        className="w-full border border-gray-200 rounded-xl px-3 py-1.5 text-xs bg-white"
                      >
                        <option value={15}>15 minutos</option>
                        <option value={30}>30 minutos</option>
                        <option value={45}>45 minutos (estándar)</option>
                        <option value={60}>60 minutos (1 hora)</option>
                        <option value={90}>90 minutos (1.5 horas)</option>
                        <option value={120}>120 minutos (2 horas)</option>
                      </select>
                    </div>
                  )}

                  {schedForm.break_mode === 'fixed' && (
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <div>
                        <label className="block text-[11px] text-gray-500 mb-1">Inicio Descanso</label>
                        <input
                          type="time"
                          value={schedForm.break_start_time}
                          onChange={e => setSchedForm({ ...schedForm, break_start_time: e.target.value })}
                          className="w-full border border-gray-200 rounded-xl px-2.5 py-1.5 text-xs bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] text-gray-500 mb-1">Fin Descanso</label>
                        <input
                          type="time"
                          value={schedForm.break_end_time}
                          onChange={e => setSchedForm({ ...schedForm, break_end_time: e.target.value })}
                          className="w-full border border-gray-200 rounded-xl px-2.5 py-1.5 text-xs bg-white"
                        />
                      </div>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  className="w-full bg-blue-600 text-white rounded-xl py-2.5 text-xs font-semibold hover:bg-blue-700 transition shadow-sm"
                >
                  Guardar Horario y Descanso
                </button>
              </form>
            </div>
          </div>
        </Modal>
      )}

      {/* Face Enroll Modal */}
      {showFaceEnroll && (
        <Modal title={`Reconocimiento Facial — ${showFaceEnroll.name}`} onClose={() => setShowFaceEnroll(null)}>
          <form onSubmit={enrollFace} className="space-y-4">
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-4">
                {faceStatuses[showFaceEnroll.id]
                  ? 'Este empleado ya tiene un rostro registrado. Puedes actualizarlo subiendo una nueva foto frontal.'
                  : 'Sube una foto frontal con buena iluminación para habilitar el marcado biométrico.'}
              </p>

              {/* Preview Avatar */}
              <div className="w-36 h-36 mx-auto rounded-2xl border-2 border-dashed border-gray-200 flex items-center justify-center bg-gray-50 overflow-hidden mb-4 shadow-inner">
                {facePreview ? (
                  <img src={facePreview} alt="Preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="text-center p-4">
                    <Camera className="w-8 h-8 text-gray-400 mx-auto" />
                    <p className="text-xs text-gray-400 mt-2">Sin foto</p>
                  </div>
                )}
              </div>

              <label className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-xl text-sm font-semibold hover:bg-gray-50 cursor-pointer transition shadow-sm">
                <Camera className="w-4 h-4 text-gray-600" />
                Seleccionar Foto Frontal
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleFacePhoto}
                  className="hidden"
                />
              </label>

              {facePhoto && (
                <p className="text-xs text-emerald-600 mt-2 font-medium flex items-center justify-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {facePhoto.name}
                </p>
              )}
            </div>

            {faceStatuses[showFaceEnroll.id] && (
              <button
                type="button"
                onClick={() => removeFaceEnrollment(showFaceEnroll)}
                className="w-full bg-red-50 text-red-600 hover:bg-red-100 rounded-xl py-2.5 font-semibold text-xs transition border border-red-200"
              >
                Eliminar Referencia Facial Actual
              </button>
            )}

            <button
              type="submit"
              disabled={loading || !facePhoto}
              className="w-full bg-blue-600 text-white rounded-xl py-3 font-semibold hover:bg-blue-700 disabled:opacity-50 transition shadow-sm text-sm"
            >
              {loading ? 'Procesando biometría...' : (faceStatuses[showFaceEnroll.id] ? 'Actualizar Rostro' : 'Guardar Rostro')}
            </button>
          </form>
        </Modal>
      )}

      {/* Global Confirm Modal */}
      <ConfirmModal
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        confirmVariant={confirmState.confirmVariant}
        confirmText="Confirmar"
        cancelText="Cancelar"
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState(prev => ({ ...prev, isOpen: false }))}
      />
    </div>
  )
}
