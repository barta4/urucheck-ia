import * as SecureStore from 'expo-secure-store';

export async function getUniqueDeviceId() {
  try {
    let deviceId = await SecureStore.getItemAsync('unique_device_id');
    
    if (!deviceId) {
      // Genera una cadena aleatoria única como ID de dispositivo
      deviceId = Math.random().toString(36).substring(2, 15) + 
                 Math.random().toString(36).substring(2, 15) + 
                 Date.now().toString(36);
                 
      await SecureStore.setItemAsync('unique_device_id', deviceId);
      console.log('Nuevo ID de dispositivo generado y guardado:', deviceId);
    }
    
    return deviceId;
  } catch (error) {
    console.error('Error obteniendo/guardando el ID del dispositivo:', error);
    return null;
  }
}
