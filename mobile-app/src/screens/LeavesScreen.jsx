import { useState, useEffect, useRef } from 'react'
import {
  View, Text, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, ScrollView, SafeAreaView, TextInput, Modal, Image, Platform
} from 'react-native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import * as FileSystem from 'expo-file-system/legacy'
import api from '../api'
import { useCompany } from '../hooks/useCompany'
import * as SecureStore from 'expo-secure-store'

export default function LeavesScreen({ onBack }) {
  const company = useCompany()
  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [reason, setReason] = useState('medical')
  
  const [cameraPermission, requestCameraPermission] = useCameraPermissions()
  const [showCamera, setShowCamera] = useState(false)
  const [photoUri, setPhotoUri] = useState(null)
  const cameraRef = useRef(null)
  const [submitting, setSubmitting] = useState(false)

  const fetchLeaves = async () => {
    try {
      const res = await api.get('/leaves/me')
      setLeaves(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeaves()
  }, [])

  const handleTakePhoto = async () => {
    if (!cameraPermission?.granted) {
      const result = await requestCameraPermission()
      if (!result.granted) {
        Alert.alert('Permiso', 'Se necesita acceso a la cámara.')
        return
      }
    }
    setShowCamera(true)
  }

  const snapPhoto = async () => {
    if (cameraRef.current) {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.5, skipProcessing: true })
      setPhotoUri(photo.uri)
      setShowCamera(false)
    }
  }

  const handleSubmit = async () => {
    if (!startDate || !endDate || !reason) {
      Alert.alert('Error', 'Completa las fechas y el motivo.')
      return
    }
    
    // basic date validation YYYY-MM-DD
    if (!startDate.match(/^\d{4}-\d{2}-\d{2}$/) || !endDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
      Alert.alert('Error', 'Formato de fecha inválido. Usa AAAA-MM-DD')
      return
    }

    setSubmitting(true)
    try {
      const token = await SecureStore.getItemAsync('token')
      const url = `${api.defaults.baseURL}/leaves/`
      
      if (photoUri) {
        const upload = await FileSystem.uploadAsync(url, photoUri, {
          httpMethod: 'POST',
          uploadType: 1,
          fieldName: 'certificate',
          headers: { Authorization: `Bearer ${token}` },
          parameters: { start_date: startDate, end_date: endDate, reason }
        })
        if (upload.status >= 400) throw new Error(JSON.parse(upload.body)?.detail || 'Error')
      } else {
        const formData = new FormData()
        formData.append('start_date', startDate)
        formData.append('end_date', endDate)
        formData.append('reason', reason)
        await api.post('/leaves/', formData)
      }
      
      Alert.alert('Éxito', 'Solicitud enviada correctamente.')
      setShowForm(false)
      setStartDate('')
      setEndDate('')
      setPhotoUri(null)
      fetchLeaves()
    } catch (e) {
      Alert.alert('Error', e.message || 'No se pudo enviar la solicitud')
    } finally {
      setSubmitting(false)
    }
  }

  const STATUS_LABELS = {
    pending: '🟡 Pendiente',
    approved: '🟢 Aprobada',
    rejected: '🔴 Rechazada'
  }
  const REASON_LABELS = {
    medical: 'Enfermedad',
    vacation: 'Vacaciones',
    personal: 'Asunto Personal'
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={[styles.header, { backgroundColor: company.primary_color || '#2563eb' }]}>
        <TouchableOpacity onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backText}>← Volver</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Licencias</Text>
      </View>

      <ScrollView contentContainerStyle={styles.container}>
        {!showForm ? (
          <>
            <TouchableOpacity style={styles.newBtn} onPress={() => setShowForm(true)}>
              <Text style={styles.newBtnText}>+ Nueva Solicitud</Text>
            </TouchableOpacity>

            <Text style={styles.title}>Mis Solicitudes</Text>
            {loading ? <ActivityIndicator size="large" color="#2563eb" /> : (
              leaves.length === 0 ? <Text style={styles.empty}>No tienes solicitudes previas.</Text> :
              leaves.map(l => (
                <View key={l.id} style={styles.card}>
                  <View style={styles.cardHeader}>
                    <Text style={styles.cardDates}>{l.start_date} al {l.end_date}</Text>
                    <Text style={styles.cardStatus}>{STATUS_LABELS[l.status]}</Text>
                  </View>
                  <Text style={styles.cardReason}>{REASON_LABELS[l.reason]}</Text>
                </View>
              ))
            )}
          </>
        ) : (
          <View style={styles.form}>
            <Text style={styles.title}>Nueva Licencia</Text>
            
            <Text style={styles.label}>Motivo</Text>
            <View style={styles.row}>
              {['medical', 'vacation', 'personal'].map(r => (
                <TouchableOpacity key={r} style={[styles.chip, reason === r && styles.chipActive]} onPress={() => setReason(r)}>
                  <Text style={[styles.chipText, reason === r && styles.chipTextActive]}>{REASON_LABELS[r]}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.label}>Fecha Inicio (AAAA-MM-DD)</Text>
            <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} placeholder="2024-01-01" keyboardType="numbers-and-punctuation" />
            
            <Text style={styles.label}>Fecha Fin (AAAA-MM-DD)</Text>
            <TextInput style={styles.input} value={endDate} onChangeText={setEndDate} placeholder="2024-01-05" keyboardType="numbers-and-punctuation" />

            <Text style={styles.label}>Certificado Médico (Opcional)</Text>
            {photoUri ? (
              <View style={styles.photoPreviewBox}>
                <Image source={{uri: photoUri}} style={styles.photoPreview} />
                <TouchableOpacity onPress={() => setPhotoUri(null)}><Text style={{color: 'red', marginTop: 8}}>Quitar Foto</Text></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.cameraBtn} onPress={handleTakePhoto}>
                <Text style={styles.cameraBtnText}>📷 Tomar foto al papel</Text>
              </TouchableOpacity>
            )}

            <View style={{flexDirection: 'row', gap: 10, marginTop: 20}}>
              <TouchableOpacity style={[styles.submitBtn, {backgroundColor: '#9ca3af', flex: 1}]} onPress={() => setShowForm(false)} disabled={submitting}>
                <Text style={styles.submitText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.submitBtn, {flex: 2}]} onPress={handleSubmit} disabled={submitting}>
                {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Enviar Solicitud</Text>}
              </TouchableOpacity>
            </View>
          </View>
        )}
      </ScrollView>

      {showCamera && (
        <Modal animationType="slide" transparent={false}>
          <CameraView ref={cameraRef} style={{flex: 1}} facing="back">
            <View style={styles.camControls}>
              <TouchableOpacity onPress={() => setShowCamera(false)} style={styles.camClose}><Text style={{color:'#fff'}}>Cancelar</Text></TouchableOpacity>
              <TouchableOpacity onPress={snapPhoto} style={styles.camSnap} />
              <View style={{width: 60}} />
            </View>
          </CameraView>
        </Modal>
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f8fafc' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: Platform.OS === 'android' ? 40 : 16 },
  backBtn: { padding: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  headerTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 16 },
  container: { padding: 20 },
  newBtn: { backgroundColor: '#e0e7ff', padding: 16, borderRadius: 12, alignItems: 'center', marginBottom: 24 },
  newBtnText: { color: '#4f46e5', fontWeight: '700', fontSize: 16 },
  title: { fontSize: 18, fontWeight: '700', marginBottom: 16, color: '#111827' },
  empty: { color: '#6b7280', textAlign: 'center', marginTop: 20 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, marginBottom: 12, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 5, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  cardDates: { fontWeight: '600', fontSize: 15 },
  cardStatus: { fontSize: 13, fontWeight: '700' },
  cardReason: { color: '#6b7280', fontSize: 14 },
  form: { backgroundColor: '#fff', padding: 20, borderRadius: 16, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 5, elevation: 2 },
  label: { fontSize: 14, fontWeight: '600', color: '#374151', marginBottom: 8, marginTop: 16 },
  input: { borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 8, padding: 12, fontSize: 16 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 20, paddingVertical: 8, paddingHorizontal: 12 },
  chipActive: { backgroundColor: '#dbeafe', borderColor: '#3b82f6' },
  chipText: { color: '#4b5563' },
  chipTextActive: { color: '#1d4ed8', fontWeight: '600' },
  cameraBtn: { backgroundColor: '#f1f5f9', padding: 16, borderRadius: 8, alignItems: 'center', borderStyle: 'dashed', borderWidth: 1, borderColor: '#cbd5e1' },
  cameraBtnText: { color: '#475569', fontWeight: '600' },
  photoPreviewBox: { alignItems: 'center', backgroundColor: '#f8fafc', padding: 10, borderRadius: 8 },
  photoPreview: { width: 100, height: 100, borderRadius: 8 },
  submitBtn: { backgroundColor: '#2563eb', padding: 16, borderRadius: 12, alignItems: 'center' },
  submitText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  camControls: { flex: 1, backgroundColor: 'transparent', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', padding: 30, paddingBottom: 60 },
  camClose: { padding: 10 },
  camSnap: { width: 70, height: 70, borderRadius: 35, backgroundColor: '#fff', borderWidth: 4, borderColor: '#e5e7eb' }
})
