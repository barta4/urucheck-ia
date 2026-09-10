import * as Location from 'expo-location';
import api from '../api.js';

/**
 * Obtiene las coordenadas GPS actuales del dispositivo.
 */
export async function getCurrentLocation() {
  try {
    let { status } = await Location.getForegroundPermissionsAsync();
    if (status !== 'granted') {
      const requestRes = await Location.requestForegroundPermissionsAsync();
      status = requestRes.status;
    }

    if (status !== 'granted') {
      console.warn('[locationService] Permiso de ubicación no concedido');
      return null;
    }

    const loc = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
      timeInterval: 4000,
    });

    return loc?.coords || null;
  } catch (err) {
    console.error('[locationService] Error al obtener coordenadas:', err.message);
    return null;
  }
}

/**
 * Reporta la ubicación actual al backend.
 * @param {'on_demand' | 'shift_tracking'} source
 */
export async function reportLocationToServer(source = 'on_demand') {
  try {
    const coords = await getCurrentLocation();
    if (!coords) {
      console.warn('[locationService] Coordenadas nulas, cancelando reporte.');
      return { success: false, error: 'No se pudo obtener GPS' };
    }

    const payload = {
      latitude: coords.latitude,
      longitude: coords.longitude,
      accuracy: coords.accuracy || null,
      source,
    };

    const res = await api.post('/locations/report', payload);
    console.log(`[locationService] Ubicación reportada (${source}):`, coords.latitude, coords.longitude);
    return { success: true, data: res.data, coords };
  } catch (err) {
    console.error('[locationService] Error reportando ubicación al servidor:', err.message);
    return { success: false, error: err.message };
  }
}
