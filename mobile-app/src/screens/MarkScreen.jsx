import { useState, useEffect, useRef, useCallback } from 'react'
import {
  View, Text, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, ScrollView, SafeAreaView, Image, Platform, RefreshControl
} from 'react-native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import * as Location from 'expo-location'
import * as FileSystem from 'expo-file-system/legacy'
import * as SecureStore from 'expo-secure-store'
import NetInfo from '@react-native-community/netinfo'
import { useAuth } from '../context/AuthContext'
import { useCompany } from '../hooks/useCompany'
import FeedbackOverlay from '../components/FeedbackOverlay'
import api from '../api'
import { addToQueue, getQueueCount, syncQueue, deleteQueuedPhoto } from '../offlineQueue'

const ACTION_CONFIG = {
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

export default function MarkScreen({ onNavigateMyData, onNavigateLeaves, onNavigateOfflineQueue, tokenExpired }) {
  const { user, logout } = useAuth()
  const company = useCompany()
  const [cameraPermission, requestCameraPermission] = useCameraPermissions()
  const [todayData, setTodayData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [verifyingFace, setVerifyingFace] = useState(false)
  const [isOnline, setIsOnline] = useState(true)
  const [queueCount, setQueueCount] = useState(0)
  const [lastSync, setLastSync] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const cameraRef = useRef(null)

  const fetchTodayData = async () => {
    setLoading(true)
    try {
      const res = await api.get('/attendance/today')
      setTodayData(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTodayData()
    requestCameraPermission()
    Location.requestForegroundPermissionsAsync()

    // Listen for network changes
    const unsubscribe = NetInfo.addEventListener(state => {
      const connected = state.isConnected && state.isInternetReachable !== false
      setIsOnline(connected)

      // Auto-sync when back online
      if (connected) {
        handleAutoSync()
      }
    })

    // Check queue count
    const updateQueueCount = async () => {
      const count = await getQueueCount()
      setQueueCount(count)
    }
    updateQueueCount()
    const interval = setInterval(updateQueueCount, 10000)

    return () => {
      unsubscribe()
      clearInterval(interval)
    }
  }, [])

  const handleAutoSync = async () => {
    const count = await getQueueCount()
    if (count === 0) return
    try {
      const result = await syncQueue((current, total) => {
        console.log(`[AutoSync] Sincronizando ${current}/${total}`)
      })
      if (result.synced > 0) {
        setFeedback({
          alert_type: 'green',
          title: '✅ Sincronización completada',
          message: `${result.synced} registro(s) pendiente(s) enviado(s) al servidor.`,
          streak: todayData?.streak || 0,
        })
        fetchTodayData()
      }
      const newCount = await getQueueCount()
      setQueueCount(newCount)
      setLastSync(new Date())
    } catch (err) {
      console.log('[AutoSync] Error:', err.message)
    }
  }

  const handleManualSync = async () => {
    setSyncing(true)
    try {
      const result = await syncQueue()
      if (result.synced > 0) {
        fetchTodayData()
      }
      Alert.alert(
        result.failed === 0 ? '✅ Sincronizado' : '⚠️ Parcial',
        `${result.synced} enviado(s), ${result.failed} fallido(s)`
      )
      const newCount = await getQueueCount()
      setQueueCount(newCount)
      setLastSync(new Date())
    } catch (err) {
      Alert.alert('Error', 'No se pudo sincronizar')
    } finally {
      setSyncing(false)
    }
  }

  const handleMark = async () => {
    if (sending) return

    // Check GPS
    const { status: locStatus } = await Location.getForegroundPermissionsAsync()
    if (locStatus !== 'granted') {
      Alert.alert('Permiso de ubicación', 'Necesitamos acceso a tu ubicación para registrar la asistencia.')
      return
    }

    // Check Camera
    if (!cameraPermission?.granted) {
      const result = await requestCameraPermission()
      if (!result.granted) {
        Alert.alert('Permiso de cámara', 'Necesitamos acceso a la cámara para tomar una foto de validación.')
        return
      }
    }

    setSending(true)
    setVerifyingFace(true)
    try {
      // Early departure check before marking exit
      if (todayData?.next_action === 'check_out' && todayData?.schedule?.end_time) {
        const now = new Date()
        const [endH, endM] = todayData.schedule.end_time.split(':').map(Number)
        const scheduledExit = new Date()
        scheduledExit.setHours(endH, endM, 0, 0)

        if (now < scheduledExit - 5 * 60 * 1000) {
          const diffMs = scheduledExit - now
          const diffMins = Math.floor(diffMs / 60000)
          const h = Math.floor(diffMins / 60)
          const m = diffMins % 60
          const timeRemaining = h > 0 ? `${h}h ${m}m` : `${m} min`

          const confirmExit = await new Promise(resolve => {
            Alert.alert(
              '⚠️ Salida Anticipada',
              `Tu horario finaliza a las ${todayData.schedule.end_time.slice(0, 5)} (faltan ${timeRemaining}).\n\n¿Deseas registrar la salida de todas formas?`,
              [
                { text: 'Cancelar', style: 'cancel', onPress: () => resolve(false) },
                { text: 'Confirmar Salida', style: 'destructive', onPress: () => resolve(true) },
              ]
            )
          })

          if (!confirmExit) {
            setSending(false)
            setVerifyingFace(false)
            return
          }
        }
      }

      // Get GPS
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
        timeInterval: 5000,
      }).catch(() => null)

      // Warn if GPS accuracy is too poor (backend rejects > 150m)
      const accuracy = location?.coords?.accuracy
      if (accuracy && accuracy > 120) {
        const proceed = await new Promise(resolve => {
          Alert.alert(
            '📡 Señal GPS débil',
            `La precisión actual es ${Math.round(accuracy)}m. Puede que tu marcación sea rechazada.\n\n¿Deseas intentarlo igual o esperar mejor señal?`,
            [
              { text: 'Esperar', style: 'cancel', onPress: () => resolve(false) },
              { text: 'Intentar igual', onPress: () => resolve(true) },
            ]
          )
        })
        if (!proceed) {
          setSending(false)
          setVerifyingFace(false)
          return
        }
      }

      // Take selfie
      let photoUri = null
      if (cameraRef.current) {
        const photo = await cameraRef.current.takePictureAsync({
          quality: 0.5,
          skipProcessing: true,
        })
        photoUri = photo.uri
      }

      // ─── ONLINE MODE ───
      if (isOnline) {
        const token = await SecureStore.getItemAsync('token')
        let resData = null

        if (photoUri) {
          const upload = await FileSystem.uploadAsync(
            `${api.defaults.baseURL}/attendance/mark`,
            photoUri,
            {
              httpMethod: 'POST',
              uploadType: 1,
              fieldName: 'photo',
              headers: { Authorization: `Bearer ${token}` },
              parameters: {
                latitude: location ? location.coords.latitude.toString() : '',
                longitude: location ? location.coords.longitude.toString() : '',
                gps_accuracy: location ? (location.coords.accuracy?.toString() || '0') : '0',
                device_timestamp: new Date().toISOString()
              }
            }
          )

          if (upload.status >= 400) {
            throw new Error(JSON.parse(upload.body)?.detail || 'Error en el servidor')
          }
          resData = JSON.parse(upload.body)
        } else {
          const formData = new FormData()
          if (location) {
            formData.append('latitude', location.coords.latitude.toString())
            formData.append('longitude', location.coords.longitude.toString())
            formData.append('gps_accuracy', location.coords.accuracy?.toString() || '0')
          }
          formData.append('device_timestamp', new Date().toISOString())
          const res = await api.post('/attendance/mark', formData)
          resData = res.data
        }

        setFeedback(resData)
        fetchTodayData()
      }
      // ─── OFFLINE MODE ───
      else {
        const queueItem = await addToQueue({
          latitude: location?.coords.latitude,
          longitude: location?.coords.longitude,
          gps_accuracy: location?.coords.accuracy,
          device_timestamp: new Date().toISOString(),
          photoUri,
        })

        const count = await getQueueCount()
        setQueueCount(count)

        setFeedback({
          alert_type: 'yellow',
          title: '📶 Guardado sin conexión',
          message: `Tu asistencia fue guardada localmente. Se sincronizará automáticamente al recuperar conexión. (${count} pendiente(s))`,
          streak: todayData?.streak || 0,
        })
      }
    } catch (err) {
      console.log('MARK_ERROR', {
        message: err.message,
        code: err.code,
        response: err.response?.data,
        status: err.response?.status,
        headers: err.response?.headers
      })

      // Only save to offline queue for real network errors, NOT server validation errors (4xx)
      const isNetworkError = !isOnline || !err.response || err.message?.includes('Network') || err.message?.includes('network')
      const isServerValidation = err.response?.status >= 400 && err.response?.status < 500

      if (isNetworkError && !isServerValidation) {
        const queueItem = await addToQueue({
          latitude: location?.coords?.latitude,
          longitude: location?.coords?.longitude,
          gps_accuracy: location?.coords?.accuracy,
          device_timestamp: new Date().toISOString(),
          photoUri,
        })
        const count = await getQueueCount()
        setQueueCount(count)
        setFeedback({
          alert_type: 'yellow',
          title: '📶 Guardado sin conexión',
          message: `Error de red. Registro guardado localmente. (${count} pendiente(s))`,
          streak: todayData?.streak || 0,
        })
      } else {
        Alert.alert('Error', err.response?.data?.detail || err.message || 'No se pudo conectar al servidor. Verifica tu conexión.')
      }
    } finally {
      setSending(false)
      setVerifyingFace(false)
    }
  }

  const nextAction = todayData?.next_action || 'check_in'
  const actionCfg = ACTION_CONFIG[nextAction] || ACTION_CONFIG.check_in
  const isCompleted = nextAction === 'already_completed'

  const TYPE_LABELS = {
    check_in: 'Entrada',
    break_start: 'Inicio descanso',
    break_end: 'Fin descanso',
    check_out: 'Salida',
  }

  return (
    <SafeAreaView style={styles.safe}>
      {/* Offline banner */}
      {!isOnline && (
        <View style={styles.offlineBanner}>
          <Text style={styles.offlineText}>📶 Sin conexión — Los registros se guardan localmente</Text>
          {queueCount > 0 && (
            <Text style={styles.offlineQueueText}>{queueCount} pendiente(s)</Text>
          )}
        </View>
      )}

      {/* Company top bar */}
      <View style={[styles.companyBar, { backgroundColor: company.accent_color || '#1d4ed8' }]}>
        {company.logo_url ? (
          <Image source={{ uri: company.logo_url }} style={styles.companyLogo} resizeMode="contain" />
        ) : (
          <Text style={styles.companyLogoEmoji}>🏢</Text>
        )}
        <Text style={styles.companyName}>{company.company_name}</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={fetchTodayData} tintColor="#2563eb" />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.greeting}>Hola, {user?.name?.split(' ')[0]} 👋</Text>
            <Text style={styles.date}>
              {new Date().toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'long' })}
            </Text>
            {lastSync && (
              <Text style={styles.lastSyncText}>Último sync: {lastSync.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })}</Text>
            )}
          </View>
          <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {/* Token expired warning */}
            {tokenExpired && (
              <TouchableOpacity onPress={logout} style={[styles.logoutBtn, { backgroundColor: '#fef2f2' }]}>
                <Text style={[styles.logoutText, { color: '#dc2626' }]}>⚠️ Token</Text>
              </TouchableOpacity>
            )}
            {/* Offline queue button */}
            {queueCount > 0 && (
              <TouchableOpacity onPress={onNavigateOfflineQueue} style={[styles.logoutBtn, { backgroundColor: '#fef3c7' }]}>
                <Text style={[styles.logoutText, { color: '#92400e' }]}>📶 {queueCount}</Text>
              </TouchableOpacity>
            )}
            {/* Manual sync button */}
            {!isOnline && queueCount > 0 && (
              <TouchableOpacity onPress={handleManualSync} style={[styles.logoutBtn, { backgroundColor: '#eff6ff' }]}>
                {syncing
                  ? <ActivityIndicator size="small" color="#2563eb" />
                  : <Text style={[styles.logoutText, { color: '#2563eb' }]}>🔄 Sync</Text>
                }
              </TouchableOpacity>
            )}
            {onNavigateLeaves && (
              <TouchableOpacity onPress={onNavigateLeaves} style={[styles.logoutBtn, { backgroundColor: '#eff6ff' }]}>
                <Text style={[styles.logoutText, { color: '#2563eb' }]}>📄 Licencias</Text>
              </TouchableOpacity>
            )}
            {onNavigateMyData && (
              <TouchableOpacity onPress={onNavigateMyData} style={[styles.logoutBtn, { backgroundColor: '#eff6ff' }]}>
                <Text style={[styles.logoutText, { color: '#2563eb' }]}>👤 Perfil</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={logout} style={styles.logoutBtn}>
              <Text style={styles.logoutText}>Salir</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Streak card */}
        {todayData && (
          <View style={styles.streakCard}>
            <Text style={styles.streakIcon}>🔥</Text>
            <View>
              <Text style={styles.streakNum}>{todayData.streak} días seguidos</Text>
              <Text style={styles.streakSub}>Faltan {todayData.days_to_bonus} días para el bono</Text>
            </View>
          </View>
        )}

        {/* Active shift card */}
        {todayData?.schedule && (
          <View style={styles.shiftCard}>
            <View style={styles.shiftHeader}>
              <Text style={styles.shiftTitle}>📍 {todayData.schedule.geofence_name || 'Ubicación Asignada'}</Text>
              <View style={styles.shiftBadge}>
                <Text style={styles.shiftBadgeText}>{todayData.schedule.slot_name || 'Turno Regular'}</Text>
              </View>
            </View>
            <View style={styles.shiftDetails}>
              <Text style={styles.shiftHours}>
                🕒 Horario: {todayData.schedule.start_time?.slice(0, 5)} – {todayData.schedule.end_time?.slice(0, 5)}
              </Text>
              <Text style={styles.shiftBreak}>
                {todayData.schedule.break_mode === 'none'
                  ? '☕ Sin descanso'
                  : `☕ Descanso máx: ${todayData.schedule.break_duration_minutes || 45} min`}
              </Text>
            </View>
          </View>
        )}

        {/* Camera preview */}
        {!isCompleted && cameraPermission?.granted && (
          <View style={styles.cameraContainer}>
            <CameraView
              ref={cameraRef}
              style={styles.camera}
              facing="front"
            />
            <View style={styles.cameraOverlay}>
              <View style={[
                styles.faceBorder,
                verifyingFace && styles.faceBorderVerifying
              ]} />
            </View>
            <Text style={styles.cameraHint}>
              {verifyingFace ? '🔍 Verificando identidad...' : 'Centra tu rostro antes de marcar'}
            </Text>
          </View>
        )}

        {/* Main action button */}
        <TouchableOpacity
          style={[
            styles.markButton,
            { backgroundColor: isCompleted ? '#9ca3af' : (company.primary_color || actionCfg.color) },
            (sending || isCompleted) && styles.markButtonDisabled
          ]}
          onPress={handleMark}
          disabled={sending || isCompleted}
          activeOpacity={0.8}
        >
          {sending ? (
            <ActivityIndicator color="#fff" size="large" />
          ) : (
            <>
              <Text style={styles.markButtonIcon}>{actionCfg.icon}</Text>
              <Text style={styles.markButtonText}>{actionCfg.label}</Text>
            </>
          )}
        </TouchableOpacity>

        {sending && (
          <Text style={styles.sendingText}>Verificando... por favor espera</Text>
        )}

        {/* Today's logs */}
        {todayData?.logs?.length > 0 && (
          <View style={styles.logsCard}>
            <Text style={styles.logsTitle}>Registros de hoy</Text>
            {todayData.logs.map((log, i) => (
              <View key={log.id} style={styles.logItem}>
                <Text style={styles.logDot}>•</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.logType}>{TYPE_LABELS[log.type] || log.type}</Text>
                  <Text style={styles.logTime}>
                    {new Date(log.timestamp).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })}
                  </Text>
                </View>
                {log.status && (
                  <Text style={[
                    styles.logStatus,
                    log.status === 'on_time' ? styles.statusGreen : (log.status === 'late' ? styles.statusRed : styles.statusYellow)
                  ]}>
                    {STATUS_LABELS[log.status]?.label || log.status}
                  </Text>
                )}
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Feedback modal */}
      {feedback && (
        <FeedbackOverlay
          feedback={feedback}
          onDismiss={() => setFeedback(null)}
        />
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f8fafc', position: 'relative' },
  offlineBanner: {
    backgroundColor: '#fef3c7', paddingVertical: 8, paddingHorizontal: 12,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    borderBottomWidth: 1, borderBottomColor: '#fde68a',
  },
  offlineText: { fontSize: 12, color: '#92400e', fontWeight: '600', flex: 1 },
  offlineQueueText: { fontSize: 12, color: '#92400e', fontWeight: '800' },
  companyBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  companyLogo: { width: 28, height: 28, borderRadius: 6 },
  companyLogoEmoji: { fontSize: 22 },
  companyName: { color: '#fff', fontWeight: '700', fontSize: 15, flex: 1 },
  container: { padding: 20, paddingBottom: 40 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  greeting: { fontSize: 22, fontWeight: '700', color: '#111827' },
  date: { fontSize: 14, color: '#6b7280', marginTop: 2, textTransform: 'capitalize' },
  lastSyncText: { fontSize: 11, color: '#9ca3af', marginTop: 2 },
  logoutBtn: { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#f1f5f9', borderRadius: 8 },
  logoutText: { fontSize: 13, color: '#64748b' },
  streakCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  streakIcon: { fontSize: 32 },
  streakNum: { fontSize: 16, fontWeight: '700', color: '#111827' },
  streakSub: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  shiftCard: {
    backgroundColor: '#eff6ff',
    borderRadius: 16,
    padding: 14,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: '#dbeafe',
  },
  shiftHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  shiftTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1e40af',
    flex: 1,
  },
  shiftBadge: {
    backgroundColor: '#dbeafe',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  shiftBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#1d4ed8',
  },
  shiftDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  shiftHours: {
    fontSize: 12,
    fontWeight: '600',
    color: '#3b82f6',
  },
  shiftBreak: {
    fontSize: 11,
    color: '#60a5fa',
    fontWeight: '500',
  },
  cameraContainer: { marginBottom: 24, borderRadius: 20, overflow: 'hidden', position: 'relative' },
  camera: { width: '100%', height: 260 },
  cameraOverlay: { position: 'absolute', inset: 0, top: 0, left: 0, right: 0, bottom: 0, justifyContent: 'center', alignItems: 'center' },
  faceBorder: { width: 160, height: 200, borderWidth: 3, borderColor: 'rgba(255,255,255,0.8)', borderRadius: 80 },
  faceBorderVerifying: { borderColor: '#3b82f6', borderWidth: 4, borderRadius: 100 },
  cameraHint: { textAlign: 'center', color: '#6b7280', fontSize: 13, marginTop: 8, paddingHorizontal: 4 },
  markButton: {
    borderRadius: 20,
    paddingVertical: 24,
    alignItems: 'center',
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 6,
  },
  markButtonDisabled: { opacity: 0.7 },
  markButtonIcon: { fontSize: 40, marginBottom: 8 },
  markButtonText: { fontSize: 20, fontWeight: '800', color: '#fff' },
  sendingText: { textAlign: 'center', color: '#6b7280', fontSize: 14, marginBottom: 16 },
  logsCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginTop: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  logsTitle: { fontSize: 15, fontWeight: '700', color: '#111827', marginBottom: 12 },
  logItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#f1f5f9' },
  logDot: { fontSize: 16, color: '#d1d5db', marginRight: 10 },
  logType: { fontSize: 14, fontWeight: '600', color: '#374151' },
  logTime: { fontSize: 12, color: '#9ca3af', marginTop: 2 },
  logStatus: { fontSize: 12, fontWeight: '600', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusGreen: { backgroundColor: '#f0fdf4', color: '#16a34a' },
  statusRed: { backgroundColor: '#fef2f2', color: '#dc2626' },
  statusYellow: { backgroundColor: '#fefce8', color: '#ca8a04' },
})
