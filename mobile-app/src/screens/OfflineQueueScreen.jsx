import { useState, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, SafeAreaView, Alert, RefreshControl
} from 'react-native'
import { getQueue, syncQueue, removeFromQueue, deleteQueuedPhoto } from '../offlineQueue'

export default function OfflineQueueScreen({ navigation }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [lastSync, setLastSync] = useState(null)

  useEffect(() => { load() }, [])

  const load = async () => {
    const queue = await getQueue()
    setItems(queue)
    setLoading(false)
  }

  const handleSyncAll = async () => {
    setSyncing(true)
    try {
      const result = await syncQueue()
      Alert.alert(
        'Sincronización completada',
        `${result.synced} enviado(s), ${result.failed} fallido(s)`,
        [{ text: 'OK', onPress: load }]
      )
      setLastSync(new Date())
    } catch (err) {
      Alert.alert('Error', 'No se pudo sincronizar')
    } finally {
      setSyncing(false)
    }
  }

  const handleRetry = async (item) => {
    if (item.status === 'failed') {
      // Remove failed item, user can try marking again
      await removeFromQueue(item.id)
      if (item.photoUri) await deleteQueuedPhoto(item.photoUri)
      Alert.alert('Eliminado', 'Registro fallido eliminado. Vuelve a marcar asistencia.')
      load()
    }
  }

  const handleDelete = async (item) => {
    Alert.alert('Eliminar registro', '¿Eliminar este registro pendiente? Se perderá el dato.', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Eliminar',
        style: 'destructive',
        onPress: async () => {
          await removeFromQueue(item.id)
          if (item.photoUri) await deleteQueuedPhoto(item.photoUri)
          load()
        }
      }
    ])
  }

  const pendingCount = items.filter(i => i.status === 'pending').length
  const failedCount = items.filter(i => i.status === 'failed').length

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Volver</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>📶 Registros Pendientes ({pendingCount})</Text>
      </View>

      {/* Summary */}
      <View style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Pendientes</Text>
          <Text style={[styles.summaryValue, { color: '#d97706' }]}>{pendingCount}</Text>
        </View>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Fallidos</Text>
          <Text style={[styles.summaryValue, { color: '#dc2626' }]}>{failedCount}</Text>
        </View>
        {lastSync && (
          <Text style={styles.lastSyncText}>Último sync: {lastSync.toLocaleTimeString('es')}</Text>
        )}
      </View>

      {/* Sync All button */}
      {pendingCount > 0 && (
        <TouchableOpacity
          style={[styles.syncButton, syncing && styles.syncButtonDisabled]}
          onPress={handleSyncAll}
          disabled={syncing}
          activeOpacity={0.8}
        >
          {syncing ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.syncButtonText}>🔄 Sincronizar ahora ({pendingCount})</Text>
          )}
        </TouchableOpacity>
      )}

      {/* Queue items */}
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#2563eb" />}
      >
        {loading ? (
          <ActivityIndicator style={{ marginTop: 40 }} color="#2563eb" />
        ) : items.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>✅</Text>
            <Text style={styles.emptyTitle}>Sin registros pendientes</Text>
            <Text style={styles.emptySub}>Todos tus registros están sincronizados</Text>
          </View>
        ) : (
          items.map((item, i) => (
            <View key={item.id} style={[
              styles.itemCard,
              item.status === 'failed' && styles.itemCardFailed
            ]}>
              <View style={styles.itemHeader}>
                <Text style={styles.itemIndex}>#{i + 1}</Text>
                <Text style={[
                  styles.itemStatus,
                  item.status === 'pending' ? styles.statusPending : styles.statusFailed
                ]}>
                  {item.status === 'pending' ? '⏳ Pendiente' : '❌ Fallido'}
                </Text>
              </View>

              <Text style={styles.itemTime}>
                {new Date(item.queued_at).toLocaleString('es')}
              </Text>

              {item.latitude && item.longitude && (
                <Text style={styles.itemLocation}>
                  📍 {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                </Text>
              )}

              {item.photoUri && (
                <Text style={styles.itemPhoto}>📸 Foto incluida</Text>
              )}

              <View style={styles.itemActions}>
                {item.status === 'failed' && (
                  <TouchableOpacity
                    style={styles.actionBtnRetry}
                    onPress={() => handleRetry(item)}
                  >
                    <Text style={styles.actionBtnText}>🗑️ Quitar</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={styles.actionBtnDelete}
                  onPress={() => handleDelete(item)}
                >
                  <Text style={styles.actionBtnText}>Eliminar</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#e5e7eb',
    backgroundColor: '#1d4ed8', paddingTop: 50,
  },
  backBtn: { padding: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  headerTitle: { flex: 1, textAlign: 'center', color: '#fff', fontSize: 18, fontWeight: '700' },
  summaryCard: {
    backgroundColor: '#fff', margin: 16, borderRadius: 12, padding: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  summaryLabel: { fontSize: 14, color: '#6b7280' },
  summaryValue: { fontSize: 18, fontWeight: '800' },
  lastSyncText: { fontSize: 12, color: '#9ca3af', textAlign: 'center', marginTop: 4, paddingTop: 8, borderTopWidth: 1, borderTopColor: '#f1f5f9' },
  syncButton: {
    marginHorizontal: 16, marginBottom: 8, borderRadius: 12, paddingVertical: 14,
    alignItems: 'center', backgroundColor: '#2563eb',
  },
  syncButtonDisabled: { opacity: 0.6 },
  syncButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  list: { padding: 16, paddingBottom: 40 },
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: '#111827' },
  emptySub: { fontSize: 14, color: '#6b7280', marginTop: 4 },
  itemCard: {
    backgroundColor: '#fff', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#e5e7eb',
  },
  itemCardFailed: { borderColor: '#fecaca', backgroundColor: '#fef2f2' },
  itemHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  itemIndex: { fontSize: 12, color: '#9ca3af' },
  itemStatus: { fontSize: 12, fontWeight: '700' },
  statusPending: { color: '#d97706' },
  statusFailed: { color: '#dc2626' },
  itemTime: { fontSize: 14, fontWeight: '600', color: '#111827', marginBottom: 2 },
  itemLocation: { fontSize: 12, color: '#6b7280' },
  itemPhoto: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  itemActions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  actionBtnRetry: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#fef3c7' },
  actionBtnDelete: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#fee2e2' },
  actionBtnText: { fontSize: 12, fontWeight: '600', color: '#991b1b' },
})
