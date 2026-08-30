import { Component } from 'react'
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.icon}>⚠️</Text>
          <Text style={styles.title}>Algo salió mal</Text>
          <Text style={styles.message}>
            Ha ocurrido un error inesperado. Intenta reiniciar la aplicación.
          </Text>
          <Text style={styles.details}>
            {this.state.error?.message || 'Error desconocido'}
          </Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => {
              this.setState({ hasError: false, error: null })
            }}
          >
            <Text style={styles.buttonText}>Reintentar</Text>
          </TouchableOpacity>
        </View>
      )
    }

    return this.props.children
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center', padding: 32 },
  icon: { fontSize: 64, marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '800', color: '#dc2626', marginBottom: 8 },
  message: { fontSize: 14, color: '#6b7280', textAlign: 'center', marginBottom: 16, lineHeight: 22 },
  details: { fontSize: 12, color: '#9ca3af', textAlign: 'center', marginBottom: 24, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  button: { backgroundColor: '#2563eb', borderRadius: 12, paddingVertical: 14, paddingHorizontal: 32 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
})

export default ErrorBoundary
