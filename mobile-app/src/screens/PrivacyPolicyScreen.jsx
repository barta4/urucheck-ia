import { useState, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, SafeAreaView, Linking
} from 'react-native'
import api from '../api'

export default function PrivacyPolicyScreen({ onBack, onAccept }) {
  const [policy, setPolicy] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/privacy/privacy-policy')
      .then(res => setPolicy(res.data))
      .catch(() => setPolicy(fallbackPolicy))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#2563eb" size="large" />
      </SafeAreaView>
    )
  }

  const sections = policy?.sections || fallbackPolicy.sections

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backText}>← Volver</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>🔒 Política de Privacidad</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>🇺🇾 Ley 18.331 — Uruguay</Text>
        </View>

        {sections.map((section, i) => (
          <View key={i} style={styles.section}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            <Text style={styles.sectionText}>{section.content}</Text>
          </View>
        ))}

        {/* URCDP link */}
        <View style={styles.urcdpSection}>
          <Text style={styles.urcdpText}>
            📋 Unidad Reguladora y de Control de Datos Personales (URCDP)
          </Text>
          <TouchableOpacity
            onPress={() => Linking.openURL('https://www.gub.uy/unidad-reguladora-control-datos-personales/')}
            style={styles.urcdpLink}
          >
            <Text style={styles.urcdpLinkText}>Visitar sitio oficial →</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Accept button */}
      {onAccept && (
        <View style={styles.footer}>
          <TouchableOpacity style={styles.acceptButton} onPress={onAccept}>
            <Text style={styles.acceptButtonText}>He leído y acepto la política de privacidad</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  )
}

const fallbackPolicy = {
  sections: [
    {
      title: "1. Responsable del tratamiento",
      content: "El responsable del tratamiento de tus datos personales es tu empleador, registrado ante la URCDP conforme a la Ley 18.331."
    },
    {
      title: "2. Datos que recopilamos",
      content: "Fotografía facial, coordenadas GPS, fecha/hora de registro, tipo de marcación y estado de puntualidad."
    },
    {
      title: "3. Tus derechos (ARCO+)",
      content: "Acceso, Rectificación, Cancelación, Oposición y Revocación del consentimiento. Usa la sección 'Mis Datos' en la app para ejercerlos."
    },
  ]
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#e5e7eb',
    backgroundColor: '#1d4ed8', paddingTop: 50,
  },
  backBtn: { padding: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  headerTitle: { flex: 1, textAlign: 'center', color: '#fff', fontSize: 18, fontWeight: '700' },
  scroll: { padding: 20, paddingBottom: 100 },
  badge: {
    backgroundColor: '#eff6ff', borderRadius: 8, padding: 10,
    marginBottom: 20, alignItems: 'center', borderWidth: 1, borderColor: '#bfdbfe',
  },
  badgeText: { fontSize: 12, fontWeight: '700', color: '#1d4ed8' },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#111827', marginBottom: 8 },
  sectionText: { fontSize: 14, color: '#4b5563', lineHeight: 22 },
  urcdpSection: {
    backgroundColor: '#f0fdf4', borderRadius: 12, padding: 16,
    marginTop: 12, borderWidth: 1, borderColor: '#bbf7d0',
  },
  urcdpText: { fontSize: 14, fontWeight: '600', color: '#15803d', marginBottom: 8 },
  urcdpLink: { paddingVertical: 4 },
  urcdpLinkText: { fontSize: 14, color: '#16a34a', fontWeight: '600', textDecorationLine: 'underline' },
  footer: {
    padding: 20, borderTopWidth: 1, borderTopColor: '#e5e7eb',
    backgroundColor: '#fff', paddingBottom: 40,
  },
  acceptButton: {
    backgroundColor: '#16a34a', borderRadius: 14, paddingVertical: 16,
    alignItems: 'center',
  },
  acceptButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
})
