import { useState } from 'react'
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert } from 'react-native'
import AsyncStorage from '@react-native-async-storage/async-storage'

export default function OnboardingScreen({ onAccept, onViewPrivacy }) {
  const [privacyAccepted, setPrivacyAccepted] = useState(false)
  const [biometricConsent, setBiometricConsent] = useState(false)

  const accept = async () => {
    if (!privacyAccepted) {
      Alert.alert(
        'Política de privacidad requerida',
        'Debes leer y aceptar la política de privacidad para continuar.',
        [{ text: 'Entendido' }]
      )
      return
    }
    if (!biometricConsent) {
      Alert.alert(
        'Consentimiento biométrico requerido',
        'Esta app utiliza reconocimiento facial para verificar tu identidad. ' +
        'Debes aceptar el tratamiento de tus datos biométricos para continuar. ' +
        'Esto es requerido por la Ley 18.331 de Uruguay.',
        [{ text: 'Entendido' }]
      )
      return
    }

    await AsyncStorage.setItem('terms_accepted', '1')
    await AsyncStorage.setItem('privacy_accepted', '1')
    await AsyncStorage.setItem('biometric_consent', '1')
    await AsyncStorage.setItem('biometric_consent_date', new Date().toISOString())
    onAccept()
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.icon}>📋</Text>
        <Text style={styles.title}>Términos y Privacidad</Text>
        <Text style={styles.subtitle}>Por favor, lee y acepta antes de continuar</Text>
      </View>

      <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
        <Section title="1. Datos que recopilamos">
          Al marcar tu asistencia, la aplicación captura: tu fotografía facial (selfie), tus coordenadas GPS (latitud y longitud) y la hora exacta del registro. Estos datos se utilizan exclusivamente para controlar y verificar tu jornada laboral.
        </Section>

        <Section title="2. Cómo usamos tus datos">
          La información recopilada se usa únicamente para: verificar tu puntualidad, calcular tu racha de días en hora para el bono de productividad y generar reportes para el área de Recursos Humanos de tu empresa.
        </Section>

        <Section title="3. Lo que NO hacemos">
          ✗ No rastreamos tu ubicación en segundo plano.{'\n'}
          ✗ No accedemos a tu cámara fuera de la marcación.{'\n'}
          ✗ No compartimos tus datos con terceros.{'\n'}
          ✗ No vendemos ni cedemos tu información personal.
        </Section>

        <Section title="4. Permisos requeridos">
          La app solicita acceso a la Cámara y a la Ubicación solo durante el uso activo de la aplicación. Puedes revocar estos permisos en la configuración de tu teléfono en cualquier momento, aunque esto impedirá el funcionamiento de la marcación.
        </Section>

        <Section title="5. Almacenamiento y seguridad">
          Todos los datos son transmitidos de forma segura (HTTPS) y almacenados en los servidores de tu empresa. Tu fotografía y datos de ubicación se conservan durante el período establecido por las políticas de tu organización.
        </Section>

        {/* ─── NEW: Legal compliance sections ─── */}
        <Section title="6. Datos biométricos (Reconocimiento Facial)">
          Esta aplicación puede utilizar reconocimiento facial para verificar tu identidad al marcar asistencia. Tu foto de referencia se almacena de forma segura y se compara mediante un vector matemático (embedding) de 128 dimensiones. Conforme a la Ley 18.331 de Uruguay, este dato se clasifica como dato sensible y requiere tu consentimiento explícito.
        </Section>

        <Section title="7. Tus derechos (ARCO+)">
          Tienes derecho a Acceder, Rectificar, Cancelar y Oponerte al tratamiento de tus datos personales. Puedes ejercer estos derechos desde la sección "Mis Datos" dentro de la app, o contactando al administrador de tu empresa. También puedes presentar una reclamación ante la URCDP (Unidad Reguladora y de Control de Datos Personales).
        </Section>

        <Section title="8. Retención de datos">
          • Fotos de verificación: se eliminan a los 90 días.{'\n'}
          • Foto de referencia facial: se elimina 30 días después de finalizada la relación laboral.{'\n'}
          • Registros de asistencia: se conservan 2 años por obligación legal.
        </Section>

        <Section title="9. Modo sin conexión">
          La aplicación puede registrar tu asistencia sin conexión a internet. Los datos se guardan localmente y se sincronizan automáticamente al reconectar. La verificación facial se realiza en el momento de la sincronización.
        </Section>
      </ScrollView>

      <View style={styles.footer}>
        {/* Privacy policy button */}
        <TouchableOpacity
          style={styles.privacyBtn}
          onPress={onViewPrivacy}
          activeOpacity={0.8}
        >
          <Text style={styles.privacyBtnText}>🔒 Leer política de privacidad completa</Text>
        </TouchableOpacity>

        {/* Acceptance checkboxes */}
        <TouchableOpacity
          style={styles.checkboxRow}
          onPress={() => setPrivacyAccepted(!privacyAccepted)}
          activeOpacity={0.7}
        >
          <View style={[styles.checkbox, privacyAccepted && styles.checkboxChecked]}>
            {privacyAccepted && <Text style={styles.checkmark}>✓</Text>}
          </View>
          <Text style={styles.checkboxLabel}>
            He leído y acepto los <Text style={styles.bold}>términos y condiciones</Text>
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.checkboxRow}
          onPress={() => setBiometricConsent(!biometricConsent)}
          activeOpacity={0.7}
        >
          <View style={[styles.checkbox, biometricConsent && styles.checkboxChecked, biometricConsent && styles.checkboxBiometric]}>
            {biometricConsent && <Text style={styles.checkmark}>✓</Text>}
          </View>
          <Text style={styles.checkboxLabel}>
            Autorizo el tratamiento de mis <Text style={styles.bold}>datos biométricos faciales</Text> conforme a la Ley 18.331
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.button,
            (!privacyAccepted || !biometricConsent) && styles.buttonDisabled
          ]}
          onPress={accept}
          activeOpacity={0.8}
        >
          <Text style={styles.buttonText}>Aceptar y continuar</Text>
        </TouchableOpacity>

        <Text style={styles.note}>
          Al continuar, confirmas haber leído y aceptado esta política de privacidad
          y autorizas el tratamiento de tus datos biométricos.
        </Text>
      </View>
    </View>
  )
}

function Section({ title, children }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionText}>{children}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: { alignItems: 'center', padding: 32, paddingTop: 60, backgroundColor: '#1d4ed8' },
  icon: { fontSize: 48, marginBottom: 12 },
  title: { fontSize: 22, fontWeight: '800', color: '#fff', textAlign: 'center' },
  subtitle: { fontSize: 14, color: '#bfdbfe', marginTop: 6, textAlign: 'center' },
  scroll: { flex: 1, padding: 20 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#111827', marginBottom: 8 },
  sectionText: { fontSize: 14, color: '#4b5563', lineHeight: 22 },
  footer: { padding: 24, borderTopWidth: 1, borderTopColor: '#e5e7eb', backgroundColor: '#fff', paddingBottom: 40 },
  privacyBtn: {
    backgroundColor: '#eff6ff', borderRadius: 12, paddingVertical: 14,
    alignItems: 'center', marginBottom: 16, borderWidth: 1, borderColor: '#bfdbfe',
  },
  privacyBtnText: { color: '#2563eb', fontSize: 14, fontWeight: '700' },
  checkboxRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 12, gap: 12 },
  checkbox: {
    width: 24, height: 24, borderRadius: 6, borderWidth: 2,
    borderColor: '#d1d5db', alignItems: 'center', justifyContent: 'center',
    marginTop: 2, flexShrink: 0,
  },
  checkboxChecked: { backgroundColor: '#2563eb', borderColor: '#2563eb' },
  checkboxBiometric: { backgroundColor: '#16a34a', borderColor: '#16a34a' },
  checkmark: { color: '#fff', fontSize: 14, fontWeight: '800' },
  checkboxLabel: { fontSize: 13, color: '#374151', flex: 1, lineHeight: 20 },
  bold: { fontWeight: '700' },
  button: {
    backgroundColor: '#2563eb', borderRadius: 14, paddingVertical: 16,
    alignItems: 'center', marginBottom: 12, marginTop: 8,
  },
  buttonDisabled: { backgroundColor: '#93c5fd', opacity: 0.7 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  note: { textAlign: 'center', color: '#9ca3af', fontSize: 12, lineHeight: 18 },
})
