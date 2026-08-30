/**
 * Offline queue for attendance marks.
 * Stores pending marks in AsyncStorage when offline,
 * and syncs them when connectivity is restored.
 */
import AsyncStorage from '@react-native-async-storage/async-storage'
import * as FileSystem from 'expo-file-system/legacy'
import * as SecureStore from 'expo-secure-store'
import api from './api'

const QUEUE_KEY = '@attendance_offline_queue'
const MAX_QUEUE_AGE_HOURS = 48

/**
 * Get all pending queue items
 */
export async function getQueue() {
  try {
    const raw = await AsyncStorage.getItem(QUEUE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/**
 * Add a mark to the offline queue
 * @param {Object} markData - { latitude, longitude, gps_accuracy, device_timestamp, photoUri }
 */
export async function addToQueue(markData) {
  const queue = await getQueue()
  const item = {
    ...markData,
    queued_at: new Date().toISOString(),
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    status: 'pending',
  }
  queue.push(item)
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue))
  return item
}

/**
 * Remove a successfully synced item from the queue
 */
export async function removeFromQueue(itemId) {
  const queue = await getQueue()
  const filtered = queue.filter(item => item.id !== itemId)
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(filtered))
}

/**
 * Mark an item as failed
 */
export async function markItemFailed(itemId) {
  const queue = await getQueue()
  const item = queue.find(i => i.id === itemId)
  if (item) {
    item.status = 'failed'
    item.error = 'Sync failed after retry'
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue))
  }
}

/**
 * Clean up old queue items (older than MAX_QUEUE_AGE_HOURS)
 */
export async function cleanOldQueue() {
  const queue = await getQueue()
  const cutoff = new Date(Date.now() - MAX_QUEUE_AGE_HOURS * 60 * 60 * 1000)
  const filtered = queue.filter(item => new Date(item.queued_at) > cutoff)
  if (filtered.length !== queue.length) {
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(filtered))
  }
}

/**
 * Get queue count (for UI badge)
 */
export async function getQueueCount() {
  const queue = await getQueue()
  return queue.filter(item => item.status === 'pending').length
}

/**
 * Sync all pending queue items to the server.
 * Call this when connectivity is restored.
 * @returns {Object} { synced: number, failed: number }
 */
export async function syncQueue(onProgress) {
  await cleanOldQueue()
  const queue = await getQueue()
  let synced = 0
  let failed = 0

  for (let i = 0; i < queue.length; i++) {
    const item = queue[i]
    if (item.status !== 'pending') continue

    if (onProgress) onProgress(i + 1, queue.filter(x => x.status === 'pending').length)

    try {
      const token = await SecureStore.getItemAsync('token')
      if (!token) {
        failed++
        continue
      }

      const url = `${api.defaults.baseURL}/attendance/mark`

      if (item.photoUri) {
        // Upload with photo via FileSystem.uploadAsync
        const result = await FileSystem.uploadAsync(url, item.photoUri, {
          httpMethod: 'POST',
          uploadType: 1,
          fieldName: 'photo',
          headers: { Authorization: `Bearer ${token}` },
          parameters: {
            latitude: item.latitude?.toString() || '',
            longitude: item.longitude?.toString() || '',
            gps_accuracy: item.gps_accuracy?.toString() || '0',
            device_timestamp: item.device_timestamp || new Date(item.queued_at).toISOString(),
          },
        })

        if (result.status >= 200 && result.status < 300) {
          await removeFromQueue(item.id)
          if (item.photoUri) await deleteQueuedPhoto(item.photoUri)
          synced++
        } else {
          await markItemFailed(item.id)
          failed++
        }
      } else {
        // No photo fallback — send without
        const formData = new FormData()
        if (item.latitude) formData.append('latitude', item.latitude.toString())
        if (item.longitude) formData.append('longitude', item.longitude.toString())
        formData.append('gps_accuracy', (item.gps_accuracy || 0).toString())
        formData.append('device_timestamp', item.device_timestamp || new Date(item.queued_at).toISOString())

        try {
          const res = await api.post('/attendance/mark', formData)
          if (res.status >= 200 && res.status < 300) {
            await removeFromQueue(item.id)
            synced++
          } else {
            await markItemFailed(item.id)
            failed++
          }
        } catch {
          await markItemFailed(item.id)
          failed++
        }
      }
    } catch (err) {
      console.log(`[OfflineQueue] Failed to sync item ${item.id}:`, err.message)
      failed++
    }
  }

  return { synced, failed }
}

/**
 * Delete local photo from queue (after sync)
 */
export async function deleteQueuedPhoto(uri) {
  try {
    const info = await FileSystem.getInfoAsync(uri)
    if (info.exists) {
      await FileSystem.deleteAsync(uri)
    }
  } catch {
    // ignore
  }
}
