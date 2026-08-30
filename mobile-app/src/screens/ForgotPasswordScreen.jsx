import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, Alert, ActivityIndicator
} from 'react-native'
import api from '../api'

export default function ForgotPasswordScreen({ navigation }) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleReset = async () => {
    if (!email) return Alert.alert('Error', 'Ingresa tu email')
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email: email.trim().toLowerCase() })
      setSent(true)
      Alert.alert(
        '✅ Solicitud enviada',
        'Contacta a tu administrador de empresa para que te restablezca la contraseña.'
      )
    } catch (err) {
      const msg = err.response?.data?.detail || 'No se pudo procesar la solicitud'
      Alert.alert('Error', msg)
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <View style={styles.container}>
        <Text style={styles.icon}>🔑</Text>
        <Text style={styles.title}>Solicitud enviada</Text>
        <Text style={styles.subtitle}>
          Contacta a tu administrador de empresa para que te restablezca la contraseña.
        </Text>
        <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}>
          <Text style={styles.buttonText}>Volver al login</Text>
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.icon}>🔑</Text>
      <Text style={styles.title}>¿Olvidaste tu contraseña?</Text>
      <Text style={styles.subtitle}>
        Ingresa tu email y tu administrador podrá restablecer tu contraseña.
      </Text>

      <TextInput
        style={styles.input}
        placeholder="tu@email.com"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        placeholderTextColor="#9ca3af"
      />

      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleReset}
        disabled={loading}
      >
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Solicitar restablecimiento</Text>}
      </TouchableOpacity>

      <TouchableOpacity style={styles.backLink} onPress={() => navigation.goBack()}>
        <Text style={styles.backLinkText}>← Volver al login</Text>
      </TouchableOpacity>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', justifyContent: 'center', padding: 32, alignItems: 'center' },
  icon: { fontSize: 64, marginBottom: 24 },
  title: { fontSize: 22, fontWeight: '800', color: '#111827', textAlign: 'center', marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#6b7280', textAlign: 'center', marginBottom: 32, lineHeight: 22 },
  input: { width: '100%', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 15, color: '#111827', marginBottom: 16 },
  button: { borderRadius: 12, paddingVertical: 15, width: '100%', alignItems: 'center', backgroundColor: '#2563eb' },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  backLink: { marginTop: 24 },
  backLinkText: { color: '#2563eb', fontSize: 14, fontWeight: '600' },
})
