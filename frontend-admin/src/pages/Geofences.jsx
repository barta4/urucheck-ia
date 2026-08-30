import { useState, useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Circle, Marker, Popup, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Search, MapPin, Trash2, UserPlus, CheckCircle2, Navigation, Layers } from 'lucide-react'
import api from '../api'
import { useToast } from '../context/ToastContext'
import ConfirmModal from '../components/ConfirmModal'

// Fix default Leaflet marker icons in React
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// Sub-component to pan the map
function MapController({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.flyTo(center, zoom || map.getZoom(), { duration: 1.2 })
    }
  }, [center, zoom, map])
  return null
}

function LocationPicker({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng)
    }
  })
  return null
}

export default function Geofences() {
  const { success, error, info } = useToast()
  const [geofences, setGeofences] = useState([])
  const [employees, setEmployees] = useState([])
  const [form, setForm] = useState({ name: '', latitude: '', longitude: '', radius_meters: 100 })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [mapCenter, setMapCenter] = useState([-34.9011, -56.1645]) // Default Montevideo
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const markerRef = useRef(null)

  useEffect(() => {
    fetchGeofences()
    api.get('/employees/').then(r => setEmployees(r.data)).catch(() => {})
  }, [])

  const fetchGeofences = async () => {
    try {
      const res = await api.get('/dashboard/geofences')
      setGeofences(res.data)
      if (res.data.length > 0 && !form.latitude) {
        setMapCenter([parseFloat(res.data[0].latitude), parseFloat(res.data[0].longitude)])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handlePickLocation = (lat, lng) => {
    setForm(prev => ({
      ...prev,
      latitude: lat.toFixed(6),
      longitude: lng.toFixed(6)
    }))
    setMapCenter([lat, lng])
    info(`Ubicación seleccionada: ${lat.toFixed(4)}, ${lng.toFixed(4)}`)
  }

  const handleMarkerDrag = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current
        if (marker != null) {
          const { lat, lng } = marker.getLatLng()
          setForm(prev => ({
            ...prev,
            latitude: lat.toFixed(6),
            longitude: lng.toFixed(6)
          }))
        }
      },
    }),
    [],
  )

  const handleSearchAddress = async (e) => {
    e?.preventDefault()
    if (!searchQuery.trim()) return
    setIsSearching(true)
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`
      )
      const data = await response.json()
      if (data && data.length > 0) {
        const lat = parseFloat(data[0].lat)
        const lon = parseFloat(data[0].lon)
        handlePickLocation(lat, lon)
        if (!form.name) {
          setForm(prev => ({ ...prev, name: data[0].display_name.split(',')[0] }))
        }
        success('Dirección encontrada en el mapa')
      } else {
        error('No se encontraron resultados para esa dirección')
      }
    } catch (err) {
      error('Error al consultar el servicio de búsqueda geográfica')
    } finally {
      setIsSearching(false)
    }
  }

  const createGeofence = async (e) => {
    e.preventDefault()
    if (!form.latitude || !form.longitude) {
      error('Por favor selecciona una ubicación en el mapa')
      return
    }
    setIsSubmitting(true)
    try {
      await api.post('/dashboard/geofences', form)
      success(`Geocerca "${form.name}" creada exitosamente`)
      setForm({ name: '', latitude: '', longitude: '', radius_meters: 100 })
      fetchGeofences()
    } catch (err) {
      error(err.response?.data?.detail || 'Error al crear la geocerca')
    } finally {
      setIsSubmitting(false)
    }
  }

  const assignGeofence = async (gfId, empId) => {
    try {
      await api.post(`/dashboard/geofences/${gfId}/assign/${empId}`)
      success('Geocerca asignada al empleado correctamente')
    } catch (err) {
      error(err.response?.data?.detail || 'Error al asignar la geocerca')
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/dashboard/geofences/${deleteTarget.id}`)
      success(`Geocerca "${deleteTarget.name}" eliminada`)
      setDeleteTarget(null)
      fetchGeofences()
    } catch (e) {
      error('Error al eliminar la geocerca')
    }
  }

  const hasFormCoords = Boolean(form.latitude && form.longitude)

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <MapPin className="w-7 h-7 text-blue-600" />
            Editor Visual de Geocercas
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Configura perímetros de control de asistencia con validación GPS interactiva.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Forms and list */}
        <div className="lg:col-span-5 space-y-6">
          {/* Address Search Helper */}
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 space-y-3">
            <label className="text-sm font-semibold text-gray-800 flex items-center gap-2">
              <Search className="w-4 h-4 text-blue-600" />
              Buscar dirección o lugar
            </label>
            <form onSubmit={handleSearchAddress} className="flex gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ej: Av. 18 de Julio 1234, Montevideo"
                className="flex-1 text-sm border border-gray-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={isSearching}
                className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isSearching ? 'Buscando...' : 'Buscar'}
              </button>
            </form>
          </div>

          {/* New Geofence Form */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5">
            <h3 className="font-semibold text-gray-900 text-base">Crear Nueva Geocerca</h3>
            <form onSubmit={createGeofence} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 mb-1.5">
                  Nombre de la Geocerca
                </label>
                <input
                  required
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="Ej: Sede Central / Obra Norte"
                  className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 mb-1.5">
                    Latitud
                  </label>
                  <input
                    required
                    value={form.latitude}
                    onChange={e => setForm({ ...form, latitude: e.target.value })}
                    placeholder="-34.901100"
                    className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 mb-1.5">
                    Longitud
                  </label>
                  <input
                    required
                    value={form.longitude}
                    onChange={e => setForm({ ...form, longitude: e.target.value })}
                    placeholder="-56.164500"
                    className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono text-xs"
                  />
                </div>
              </div>

              {/* Radius with Slider */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold uppercase tracking-wider text-gray-600">
                    Radio de Cobertura
                  </label>
                  <span className="text-sm font-bold text-blue-600 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-100">
                    {form.radius_meters} metros
                  </span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="1500"
                  step="5"
                  value={form.radius_meters}
                  onChange={e => setForm({ ...form, radius_meters: parseInt(e.target.value, 10) || 50 })}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <div className="flex justify-between text-[11px] text-gray-400">
                  <span>15 m (preciso)</span>
                  <span>500 m</span>
                  <span>1500 m (amplio)</span>
                </div>
              </div>

              <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-100/80 text-xs text-blue-800 flex items-center gap-2">
                <Navigation className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Haz clic en el mapa o arrastra el marcador amarillo para ajustar la posición.</span>
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !hasFormCoords}
                className="w-full bg-blue-600 text-white rounded-xl py-3 text-sm font-semibold hover:bg-blue-700 shadow-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                {isSubmitting ? 'Guardando...' : 'Crear Geocerca'}
              </button>
            </form>
          </div>

          {/* Existing Geofences List */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">
            <h3 className="font-semibold text-gray-900 text-base flex items-center justify-between">
              <span>Geocercas Registradas</span>
              <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                {geofences.length} activas
              </span>
            </h3>

            {geofences.length === 0 ? (
              <p className="text-sm text-gray-500 italic text-center py-4">No hay geocercas registradas aún.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {geofences.map(gf => (
                  <div
                    key={gf.id}
                    className="p-3.5 rounded-xl border border-gray-100 bg-gray-50/70 hover:bg-gray-50 transition-colors flex flex-col gap-2"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-semibold text-sm text-gray-900">{gf.name}</p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          Radio: <span className="font-medium text-gray-700">{gf.radius_meters} m</span> • ({Number(gf.latitude).toFixed(4)}, {Number(gf.longitude).toFixed(4)})
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setMapCenter([parseFloat(gf.latitude), parseFloat(gf.longitude)])
                            info(`Centrando mapa en ${gf.name}`)
                          }}
                          className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="Centrar en mapa"
                        >
                          <Navigation className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(gf)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Eliminar geocerca"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-gray-200/60">
                      <UserPlus className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <select
                        onChange={e => {
                          if (e.target.value) {
                            assignGeofence(gf.id, e.target.value)
                            e.target.value = ''
                          }
                        }}
                        className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 w-full"
                        defaultValue=""
                      >
                        <option value="">Asignar a empleado...</option>
                        {(Array.isArray(employees) ? employees : []).filter(e => e.active).map(e => (
                          <option key={e.id} value={e.id}>{e.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Interactive Map */}
        <div className="lg:col-span-7 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden sticky top-6">
          <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Layers className="w-4 h-4 text-blue-600" />
              Vista Satelital y Cobertura
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" /> Existentes
              </span>
              {hasFormCoords && (
                <span className="flex items-center gap-1.5 font-medium text-amber-700">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> En edición
                </span>
              )}
            </div>
          </div>

          <div className="h-[620px] w-full">
            <MapContainer
              center={mapCenter}
              zoom={14}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapController center={mapCenter} />
              <LocationPicker onPick={handlePickLocation} />

              {/* Render Existing Geofences */}
              {geofences.map(gf => (
                <div key={gf.id}>
                  <Circle
                    center={[parseFloat(gf.latitude), parseFloat(gf.longitude)]}
                    radius={gf.radius_meters}
                    pathOptions={{ color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.2, weight: 2 }}
                  />
                  <Marker position={[parseFloat(gf.latitude), parseFloat(gf.longitude)]}>
                    <Popup>
                      <div className="text-xs p-1">
                        <p className="font-bold text-sm text-gray-900">{gf.name}</p>
                        <p className="text-gray-600 mt-0.5">Radio: {gf.radius_meters}m</p>
                      </div>
                    </Popup>
                  </Marker>
                </div>
              ))}

              {/* Render New / Editing Geofence Marker & Dynamic Circle */}
              {hasFormCoords && (
                <>
                  <Circle
                    center={[parseFloat(form.latitude), parseFloat(form.longitude)]}
                    radius={form.radius_meters}
                    pathOptions={{ color: '#d97706', fillColor: '#f59e0b', fillOpacity: 0.25, weight: 2, dashArray: '4, 4' }}
                  />
                  <Marker
                    draggable={true}
                    eventHandlers={handleMarkerDrag}
                    position={[parseFloat(form.latitude), parseFloat(form.longitude)]}
                    ref={markerRef}
                  >
                    <Popup>
                      <div className="text-xs">
                        <p className="font-bold text-amber-700">{form.name || 'Nueva Geocerca'}</p>
                        <p className="text-gray-500">Arrastra para ajustar posición</p>
                      </div>
                    </Popup>
                  </Marker>
                </>
              )}
            </MapContainer>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Delete */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="¿Eliminar Geocerca?"
        message={`¿Estás seguro de que deseas eliminar la geocerca "${deleteTarget?.name}"? Se desvinculará de todos los empleados asignados.`}
        confirmText="Sí, eliminar"
        cancelText="Cancelar"
        confirmVariant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
