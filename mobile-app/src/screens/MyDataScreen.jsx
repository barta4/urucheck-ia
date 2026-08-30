import { useState, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  Alert, ActivityIndicator, SafeAreaView, Linking
} from 'react-native'
import * as Sharing from 'expo-sharing'
import * as FileSystem from 'expo-file-system/legacy'
import * as SecureStore from 'expo-secure-store'
import { useAuth } from '../context/AuthContext'
import api from '../api'

export default function MyDataScreen() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    api.get('/data-rights/summary')
      .then(res => setSummary(res.data))
      .catch(() => setSummary(null))
      .finally(() => setLoading(false))
  }, [])

  const handleExportJSON = async () => {
    setExporting(true)
    try {
      const token = await SecureStore.getItemAsync('token')
      const url = `${api.defaults.baseURL}/data-rights/export`
      const fileUri = FileSystem.cacheDirectory + 'mis_datos.json'

      const { status } = await FileSystem.downloadAsync(url, fileUri, {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (status === 200) {
        const canShare = await Sharing.isAvailableAsync()
        if (canShare) {
          await Sharing.shareAsync(fileUri, {
            mimeType: 'application/json',
            UTI: 'public.json'
          })
        } else {
          Alert.alert('Exportado', 'Archivo guardado en caché del dispositivo.')
        }
      }
    } catch (err) {
      Alert.alert('Error', 'No se pudo exportar los datos. Verifica tu conexión.')
    } finally {
      setExporting(false)
    }
  }

  const handleExportCSV = async () => {
    setExporting(true)
    try {
      const token = await SecureStore.getItemAsync('token')
      const url = `${api.defaults.baseURL}/data-rights/export-csv`
      const fileUri = FileSystem.cacheDirectory + 'asistencia.csv'

      const { status } = await FileSystem.downloadAsync(url, fileUri, {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (status === 200) {
        const canShare = await Sharing.isAvailableAsync()
        if (canShare) {
          await Sharing.shareAsync(fileUri, {
            mimeType: 'text/csv',
            UTI: 'public.comma-separated-values-text'
          })
        }
      }
    } catch (err) {
      Alert.alert('Error', 'No se pudo exportar.')
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteFacePhoto = async () => {
    Alert.alert(
      'Eliminar foto de referencia',
      '¿Estás seguro? Si la verificación facial está activa, no podrás marcar asistencia hasta que el admin registre una nueva foto.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true)
            try {
              await api.post('/data-rights/delete-face-photo')
              Alert.alert('✅ Eliminado', 'Tu foto de referencia facial ha sido eliminada.')
              // Refresh summary
              const res = await api.get('/data-rights/summary')
              setSummary(res.data)
            } catch (err) {
              Alert.alert('Error', err.response?.data?.detail || 'No se pudo eliminar.')
            } finally {
              setDeleting(false)
            }
          }
        }
      ]
    )
  }

  const handleRequestFullDeletion = async () => {
    Alert.alert(
      '⚠️ Solicitar eliminación total de datos',
      'Esto solicitará la eliminación de todos tus datos personales almacenados. Los registros de asistencia se conservan por obligación legal (mínimo 2 años) pero tu foto facial será eliminada inmediatamente. ¿Continuar?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Solicitar eliminación',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true)
            try {
              await api.post('/data-rights/request-deletion', {
                delete_face_photo: true,
                delete_attendance_logs: false,
                reason: 'Solicitud voluntaria del empleado (ARCO+)',
              })
              Alert.alert('✅ Solicitud enviada', 'Tu solicitud de eliminación ha sido procesada. La foto facial fue eliminada inmediatamente.')
              const res = await api.get('/data-rights/summary')
              setSummary(res.data)
            } catch (err) {
              Alert.alert('Error', err.response?.data?.detail || 'No se pudo procesar la solicitud.')
            } finally {
              setDeleting(false)
            }
          }
        }
      ]
    )
  }

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#2563eb" size="large" />
      </SafeAreaView>
    )
  }

  const data = summary?.data_held || {}
  const retention = summary?.retention_policy || {}

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>👤 Mis Datos Personales</Text>
        <Text style={styles.headerSub}>Tus derechos ARCO+ — Ley 18.331</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Data summary card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📊 Datos almacenados sobre ti</Text>

          <DataRow label="Foto de referencia facial" value={data.face_reference_photo ? '✅ Sí' : '❌ No'} />
          <DataRow label="Registros de asistencia" value={`${data.attendance_log_count || 0}`} />
          <DataRow label="Racha actual" value={`${data.current_streak || 0} días`} />
          <DataRow label="Geocercas asignadas" value={`${data.geofence_assignments || 0}`} />
          <DataRow label="Registrado desde" value={
            summary?.registered_since
              ? new Date(summary.registered_since).toLocaleDateString('es')
              : '—'
          } />
        </View>

        {/* Retention policy */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🗄️ Política de retención</Text>
          <DataRow label="Fotos de verificación" value={retention.verification_photos || '90 días'} />
          <DataRow label="Foto de referencia" value={retention.face_reference_photo || 'Relación laboral + 30d'} />
          <DataRow label="Registros de asistencia" value={retention.attendance_logs || '2 años'} />
        </View>

        {/* Export actions */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📥 Exportar mis datos</Text>

          <TouchableOpacity
            style={styles.actionBtn}
            onPress={handleExportJSON}
            disabled={exporting}
          >
            <Text style={styles.actionBtnIcon}>📄</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.actionBtnTitle}>Exportar todo (JSON)</Text>
              <Text style={styles.actionBtnSub}>Datos completos: perfil, asistencia, racha, bonos</Text>
            </View>
            {exporting && <ActivityIndicator color="#2563eb" />}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnSecondary]}
            onPress={handleExportCSV}
            disabled={exporting}
          >
            <Text style={styles.actionBtnIcon}>📊</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.actionBtnTitle}>Exportar asistencia (CSV)</Text>
              <Text style={styles.actionBtnSub}>Solo registros de entrada/salida</Text>
            </View>
            {exporting && <ActivityIndicator color="#2563eb" />}
          </TouchableOpacity>
        </View>

        {/* Delete face photo */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🗑️ Gestionar datos biométricos</Text>

          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnDanger]}
            onPress={handleDeleteFacePhoto}
            disabled={deleting || !data.face_reference_photo}
          >
            <Text style={styles.actionBtnIcon}>🗑️</Text>
            <View style={{ flex: 1 }}>
              <Text style={[styles.actionBtnTitle, { color: '#dc2626' }]}>
                Eliminar foto de referencia
              </Text>
              <Text style={[styles.actionBtnSub, { color: '#9ca3af' }]}>
                {data.face_reference_photo
                  ? 'Se eliminará tu foto facial. Contacta al admin para registrar una nueva.'
                  : 'No tienes foto de referencia registrada'}
              </Text>
            </View>
            {deleting && <ActivityIndicator color="#dc2626" />}
          </TouchableOpacity>
        </View>

        {/* Full data deletion */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🗑️ Eliminación total de datos (ARCO+)</Text>
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnDanger]}
            onPress={handleRequestFullDeletion}
            disabled={deleting}
          >
            <Text style={styles.actionBtnIcon}>⚠️</Text>
            <View style={{ flex: 1 }}>
              <Text style={[styles.actionBtnTitle, { color: '#dc2626' }]}>
                Solicitar eliminación de todos mis datos
              </Text>
              <Text style={[styles.actionBtnSub, { color: '#9ca3af' }]}>
                Incluye foto facial. Registros de asistencia se conservan por ley.
              </Text>
            </View>
            {deleting && <ActivityIndicator color="#dc2626" />}
          </TouchableOpacity>
        </View>

        {/* Legal notice */}
        <View style={styles.legalCard}>
          <Text style={styles.legalTitle}>⚖️ Aviso Legal</Text>
          <Text style={styles.legalText}>
            Conforme a la Ley 18.331 de Uruguay, tienes derecho a acceder, rectificar,
            cancelar y oponerte al tratamiento de tus datos personales. Los registros de
            asistencia se conservan por obligación legal (mínimo 2 años).
          </Text>
          <TouchableOpacity
            onPress={() => Linking.openURL('https://www.gub.uy/unidad-reguladora-control-datos-personales/')}
            style={styles.linkBtn}
          >
            <Text style={styles.linkBtnText}>URCDP — Más información →</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  )
}

function DataRow({ label, value }) {
  return (
    <View style={styles.dataRow}>
      <Text style={styles.dataLabel}>{label}</Text>
      <Text style={styles.dataValue}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: {
    backgroundColor: '#1d4ed8', paddingHorizontal: 20,
    paddingVertical: 20, paddingTop: 50,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#fff' },
  headerSub: { fontSize: 14, color: '#bfdbfe', marginTop: 4 },
  scroll: { padding: 16, paddingBottom: 40 },
  card: {
    backgroundColor: '#fff', borderRadius: 16, padding: 16,
    marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#111827', marginBottom: 12 },
  dataRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#f1f5f9',
  },
  dataLabel: { fontSize: 14, color: '#6b7280' },
  dataValue: { fontSize: 14, fontWeight: '600', color: '#111827' },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: 14, backgroundColor: '#f8fafc', borderRadius: 12,
    borderWidth: 1, borderColor: '#e2e8f0', marginBottom: 8,
  },
  actionBtnSecondary: { backgroundColor: '#eff6ff', borderColor: '#bfdbfe' },
  actionBtnDanger: { backgroundColor: '#fef2f2', borderColor: '#fecaca' },
  actionBtnIcon: { fontSize: 24 },
  actionBtnTitle: { fontSize: 14, fontWeight: '600', color: '#111827' },
  actionBtnSub: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  legalCard: {
    backgroundColor: '#fffbeb', borderRadius: 12, padding: 16,
    borderWidth: 1, borderColor: '#fde68a', marginTop: 4,
  },
  legalTitle: { fontSize: 15, fontWeight: '700', color: '#92400e', marginBottom: 8 },
  legalText: { fontSize: 13, color: '#78716c', lineHeight: 20 },
  linkBtn: { marginTop: 8, paddingVertical: 4 },
  linkBtnText: { fontSize: 13, color: '#2563eb', fontWeight: '600', textDecorationLine: 'underline' },
})
