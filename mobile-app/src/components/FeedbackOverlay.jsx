import { useEffect, useRef } from 'react'
import { View, Text, StyleSheet, Animated, TouchableOpacity } from 'react-native'
import * as Haptics from 'expo-haptics'

const CONFIGS = {
  green: {
    bg: '#f0fdf4',
    border: '#16a34a',
    icon: '✅',
    titleColor: '#15803d',
  },
  red: {
    bg: '#fef2f2',
    border: '#dc2626',
    icon: '❌',
    titleColor: '#dc2626',
  },
  yellow: {
    bg: '#fefce8',
    border: '#ca8a04',
    icon: '⚠️',
    titleColor: '#a16207',
  },
}

export default function FeedbackOverlay({ feedback, onDismiss }) {
  const opacity = useRef(new Animated.Value(0)).current
  const cfg = CONFIGS[feedback?.alert_type] || CONFIGS.yellow

  useEffect(() => {
    if (!feedback) return

    // Reset opacity so it can animate from 0 each time
    opacity.setValue(0)

    // Haptics
    if (feedback.alert_type === 'green') {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)
    } else if (feedback.alert_type === 'red') {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)
    } else {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning)
    }

    Animated.timing(opacity, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start()
  }, [feedback])

  if (!feedback) return null

  return (
    <Animated.View style={[styles.overlay, { opacity }]}>
      <View style={[styles.card, { backgroundColor: cfg.bg, borderColor: cfg.border }]}>
        <Text style={styles.icon}>{cfg.icon}</Text>
        <Text style={[styles.title, { color: cfg.titleColor }]}>{feedback.title}</Text>
        <Text style={styles.message}>{feedback.message}</Text>

        {feedback.streak !== null && feedback.streak !== undefined && (
          <View style={styles.streakBox}>
            <Text style={styles.streakText}>🔥 Racha: {feedback.streak} días</Text>
            {feedback.streak_message && (
              <Text style={styles.streakSub}>{feedback.streak_message}</Text>
            )}
          </View>
        )}

        <TouchableOpacity style={[styles.button, { backgroundColor: cfg.border }]} onPress={onDismiss}>
          <Text style={styles.buttonText}>Continuar</Text>
        </TouchableOpacity>
      </View>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    inset: 0,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    zIndex: 9999,
    elevation: 9999,
  },
  card: {
    width: '100%',
    maxWidth: 360,
    borderRadius: 24,
    borderWidth: 2,
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 20,
    elevation: 8,
  },
  icon: { fontSize: 56, marginBottom: 16 },
  title: { fontSize: 20, fontWeight: '700', textAlign: 'center', marginBottom: 8 },
  message: { fontSize: 15, color: '#374151', textAlign: 'center', lineHeight: 22, marginBottom: 16 },
  streakBox: {
    backgroundColor: 'rgba(0,0,0,0.05)',
    borderRadius: 12,
    padding: 12,
    width: '100%',
    alignItems: 'center',
    marginBottom: 20,
  },
  streakText: { fontSize: 16, fontWeight: '700', color: '#111827' },
  streakSub: { fontSize: 13, color: '#6b7280', marginTop: 4, textAlign: 'center' },
  button: {
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 40,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
})
