import { useState, useEffect } from 'react'
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, KeyboardAvoidingView, Platform, Alert, ActivityIndicator, Image
} from 'react-native'
import AsyncStorage from '@react-native-async-storage/async-storage'
import axios from 'axios'
import api, { DEFAULT_API_URL } from '../api'
import { useAuth } from '../context/AuthContext'
import { useCompany } from '../hooks/useCompany'

const formatApiUrl = (input) => {
  let url = input.trim();
  if (!url) return '';
  url = url.replace(/\/+$/, '');
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    if (url.includes('localhost') || url.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/)) {
      url = 'http://' + url;
    } else {
      url = 'https://' + url;
    }
  }
  if (!url.endsWith('/api')) {
    url = url + '/api';
  }
  return url;
};

export default function LoginScreen({ onLoginSuccess, onForgotPassword }) {
  const { login } = useAuth()
  const globalCompany = useCompany()
  const [company, setCompany] = useState(globalCompany)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [customServer, setCustomServer] = useState('')
  const [showServerConfig, setShowServerConfig] = useState(false)

  useEffect(() => {
    setCompany(globalCompany)
  }, [globalCompany])

  useEffect(() => {
    AsyncStorage.getItem('custom_api_url').then(val => {
      if (val) {
        setCustomServer(val.replace(/\/api$/, '').replace(/^https?:\/\//, ''))
      }
    })
  }, [])

  const handleSaveServer = async () => {
    if (!customServer.trim()) {
      await AsyncStorage.removeItem('custom_api_url')
      api.defaults.baseURL = DEFAULT_API_URL
      Alert.alert('Servidor reestablecido', 'Se ha reestablecido el servidor predeterminado.')
      try {
        const res = await api.get('/company/config')
        setCompany(res.data)
      } catch {}
      setShowServerConfig(false)
      return
    }

    const formatted = formatApiUrl(customServer)
    setLoading(true)
    try {
      const res = await axios.get(`${formatted}/company/config`, { timeout: 8000 })
      let data = res.data
      if (data.logo_url && !data.logo_url.startsWith('http')) {
        const base = formatted.replace(/\/api$/, '')
        data.logo_url = base + data.logo_url
      }
      
      await AsyncStorage.setItem('custom_api_url', formatted)
      api.defaults.baseURL = formatted
      setCompany(data)
      Alert.alert('Conexión exitosa', `Conectado correctamente a: ${data.company_name}`)
      setShowServerConfig(false)
    } catch (err) {
      Alert.alert('Error de conexión', 'No se pudo conectar al servidor. Verifica el dominio o la dirección IP.')
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async () => {
    if (!email || !password) return Alert.alert('Error', 'Completa todos los campos')
    setLoading(true)
    try {
      await login(email.trim().toLowerCase(), password)
      if (onLoginSuccess) onLoginSuccess()
    } catch (err) {
      if (err.response?.status === 429) {
        Alert.alert('Demasiados intentos', 'Por seguridad, espera un minuto antes de intentar nuevamente.')
      } else {
        Alert.alert('Error', err.response?.data?.detail || 'Email o contraseña incorrectos')
      }
    } finally {
      setLoading(false)
    }
  }

  const accentColor = company.accent_color || '#1d4ed8'
  const primaryColor = company.primary_color || '#2563eb'

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={[styles.container, { backgroundColor: accentColor }]}>
      <View style={styles.card}>
        <View style={[styles.logoBox, { backgroundColor: accentColor + '15', borderColor: accentColor + '30' }]}>
          {company.logo_url ? (
            <Image source={{ uri: company.logo_url }} style={styles.logoImg} resizeMode="contain" />
          ) : (
            <Text style={styles.logoEmoji}>🏢</Text>
          )}
        </View>

        <Text style={styles.title}>{company.company_name}</Text>
        <Text style={styles.subtitle}>UruCheck IA</Text>

        <TextInput style={styles.input} placeholder="Email" value={email} onChangeText={setEmail}
          keyboardType="email-address" autoCapitalize="none" placeholderTextColor="#9ca3af" />
        <TextInput style={styles.input} placeholder="Contraseña" value={password} onChangeText={setPassword}
          secureTextEntry placeholderTextColor="#9ca3af" />

        <TouchableOpacity style={[styles.button, { backgroundColor: accentColor }, loading && styles.buttonDisabled]}
          onPress={handleLogin} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Ingresar</Text>}
        </TouchableOpacity>

        {onForgotPassword && (
          <TouchableOpacity onPress={onForgotPassword} style={styles.forgotLink}>
            <Text style={styles.forgotText}>¿Olvidaste tu contraseña?</Text>
          </TouchableOpacity>
        )}

        <View style={styles.divider} />

        <TouchableOpacity onPress={() => setShowServerConfig(!showServerConfig)} style={styles.serverLink}>
          <Text style={[styles.serverLinkText, { color: accentColor }]}>
            ⚙️ {showServerConfig ? 'Ocultar dirección del servidor' : 'Configurar servidor personalizado'}
          </Text>
        </TouchableOpacity>

        {showServerConfig && (
          <View style={styles.serverBox}>
            <TextInput
              style={styles.inputSmall}
              placeholder="ej: tu-dominio.com o 192.168.1.10:8000"
              value={customServer}
              onChangeText={setCustomServer}
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor="#9ca3af"
            />
            <TouchableOpacity
              style={[styles.saveButton, { backgroundColor: accentColor }]}
              onPress={handleSaveServer}
            >
              <Text style={styles.saveButtonText}>Guardar y Probar</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24 },
  card: { backgroundColor: '#fff', borderRadius: 24, padding: 32, alignItems: 'center', shadowColor: '#000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.2, shadowRadius: 16, elevation: 8 },
  logoBox: { width: 84, height: 84, borderRadius: 22, alignItems: 'center', justifyContent: 'center', marginBottom: 16, borderWidth: 2, overflow: 'hidden' },
  logoImg: { width: '100%', height: '100%' },
  logoEmoji: { fontSize: 40 },
  title: { fontSize: 20, fontWeight: '800', color: '#111827', marginBottom: 4, textAlign: 'center' },
  subtitle: { fontSize: 13, color: '#6b7280', marginBottom: 28 },
  input: { width: '100%', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 15, color: '#111827', marginBottom: 12 },
  button: { borderRadius: 12, paddingVertical: 15, width: '100%', alignItems: 'center', marginTop: 8 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  forgotLink: { marginTop: 16, alignItems: 'center' },
  forgotText: { color: '#2563eb', fontSize: 14, fontWeight: '600' },
  divider: { width: '100%', height: 1, backgroundColor: '#f3f4f6', marginVertical: 16 },
  serverLink: { paddingVertical: 4 },
  serverLinkText: { fontSize: 13, fontWeight: '600' },
  serverBox: { width: '100%', marginTop: 12, alignItems: 'center' },
  inputSmall: { width: '100%', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: '#111827', marginBottom: 8 },
  saveButton: { borderRadius: 10, paddingVertical: 10, width: '100%', alignItems: 'center' },
  saveButtonText: { color: '#fff', fontSize: 13, fontWeight: '700' },
})
