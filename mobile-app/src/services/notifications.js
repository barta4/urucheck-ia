import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { reportLocationToServer } from './locationService';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerForPushNotificationsAsync() {
  let token;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    });
  }

  if (Device.isDevice) {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') {
      console.log('No se pudieron obtener los permisos de notificación.');
      return;
    }
    try {
      const projectId =
        Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId;
      
      if (!projectId) {
        console.warn('Project ID no encontrado, usando ID genérico si se ejecuta en Expo Go');
      }
      
      token = (await Notifications.getExpoPushTokenAsync({
        projectId,
      })).data;
      console.log("Token de notificaciones obtenido:", token);
    } catch (e) {
      console.log("Error obteniendo token:", e);
    }
  } else {
    console.log('Se requiere un dispositivo físico para las notificaciones Push');
  }

  return token;
}

/**
 * Registra los listeners de notificaciones para responder a solicitudes de ubicación
 * emitidas desde el panel de administración.
 */
export function setupNotificationListeners(onLocationRequested) {
  // 1. App en primer plano
  const receivedSubscription = Notifications.addNotificationReceivedListener(async (notification) => {
    const data = notification?.request?.content?.data;
    if (data && data.type === 'LOCATION_REQUEST') {
      console.log('[notifications] Solicitud de ubicación recibida en primer plano, reportando...');
      const result = await reportLocationToServer('on_demand');
      if (onLocationRequested) {
        onLocationRequested(result);
      }
    }
  });

  // 2. Usuario interactúa/toca la notificación (en segundo plano o cerrada)
  const responseSubscription = Notifications.addNotificationResponseReceivedListener(async (response) => {
    const data = response?.notification?.request?.content?.data;
    if (data && data.type === 'LOCATION_REQUEST') {
      console.log('[notifications] Solicitud de ubicación pulsada por el usuario, reportando...');
      const result = await reportLocationToServer('on_demand');
      if (onLocationRequested) {
        onLocationRequested(result);
      }
    }
  });

  return () => {
    receivedSubscription.remove();
    responseSubscription.remove();
  };
}

