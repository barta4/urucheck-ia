import { useState, useEffect, useCallback } from 'react'
import { View, ActivityIndicator, StatusBar, BackHandler, Alert } from 'react-native'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { AuthProvider, useAuth } from './src/context/AuthContext'
import { setupNotificationListeners } from './src/services/notifications'
import OnboardingScreen from './src/screens/OnboardingScreen'
import LoginScreen from './src/screens/LoginScreen'
import ForgotPasswordScreen from './src/screens/ForgotPasswordScreen'
import MarkScreen from './src/screens/MarkScreen'
import OfflineQueueScreen from './src/screens/OfflineQueueScreen'
import PrivacyPolicyScreen from './src/screens/PrivacyPolicyScreen'
import MyDataScreen from './src/screens/MyDataScreen'
import LeavesScreen from './src/screens/LeavesScreen'
import ErrorBoundary from './src/components/ErrorBoundary'

const Stack = createNativeStackNavigator()

function AppNavigator() {
  const { user, loading, tokenExpired } = useAuth()
  const [termsAccepted, setTermsAccepted] = useState(null)
  const [navReady, setNavReady] = useState(false)

  // Check onboarding status
  useEffect(() => {
    AsyncStorage.getItem('terms_accepted').then(val => {
      setTermsAccepted(val === '1')
      setNavReady(true)
    })
  }, [])

  // Handle Android back button - only block on first screen
  useEffect(() => {
    const handler = () => {
      // Let React Navigation handle back naturally
      return false
    }
    BackHandler.addEventListener('hardwareBackPress', handler)
    return () => BackHandler.removeEventListener('hardwareBackPress', handler)
  }, [])

  // Listen for admin location requests
  useEffect(() => {
    if (!user) return
    const cleanup = setupNotificationListeners((result) => {
      if (result?.success) {
        Alert.alert(
          '📍 Ubicación Confirmada',
          'Tu ubicación actual ha sido compartida con la administración de la empresa.',
          [{ text: 'Entendido' }]
        )
      }
    })
    return () => {
      if (cleanup) cleanup()
    }
  }, [user])

  if (loading || termsAccepted === null || !navReady) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#1d4ed8' }}>
        <ActivityIndicator color="#fff" size="large" />
      </View>
    )
  }

  // Determine initial route
  const initialRoute = !termsAccepted
    ? 'Onboarding'
    : !user
    ? 'Login'
    : 'Mark'

  return (
    <ErrorBoundary>
      <NavigationContainer>
        <StatusBar barStyle="dark-content" />
        <Stack.Navigator
          initialRouteName={initialRoute}
          screenOptions={{
            headerShown: false,
            animation: 'slide_from_right',
          }}
        >
          {/* Public screens */}
          <Stack.Screen name="Onboarding">
            {props => (
              <OnboardingScreen
                {...props}
                onAccept={async () => {
                  await AsyncStorage.setItem('terms_accepted', '1')
                  await AsyncStorage.setItem('privacy_accepted', '1')
                  await AsyncStorage.setItem('biometric_consent', '1')
                  await AsyncStorage.setItem('biometric_consent_date', new Date().toISOString())
                  props.navigation.replace(user ? 'Mark' : 'Login')
                }}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="PrivacyPolicy" component={PrivacyPolicyScreen} />

          <Stack.Screen name="Login">
            {props => (
              <LoginScreen
                {...props}
                onLoginSuccess={() => props.navigation.replace('Mark')}
                onForgotPassword={() => props.navigation.navigate('ForgotPassword')}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />

          {/* Authenticated screens */}
          <Stack.Screen
            name="Mark"
            options={{ gestureEnabled: false }}
          >
            {props => (
              <MarkScreen
                {...props}
                tokenExpired={tokenExpired}
                onNavigateMyData={() => props.navigation.push('MyData')}
                onNavigateLeaves={() => props.navigation.push('Leaves')}
                onNavigateOfflineQueue={() => props.navigation.push('OfflineQueue')}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="MyData" component={MyDataScreen} />
          <Stack.Screen name="Leaves">
            {props => <LeavesScreen {...props} onBack={() => props.navigation.goBack()} />}
          </Stack.Screen>
          <Stack.Screen name="OfflineQueue" component={OfflineQueueScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppNavigator />
    </AuthProvider>
  )
}
