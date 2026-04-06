<template>
  <div class="backup-view">
    <div class="page-header">
      <h1>Backup Management</h1>
      <div class="header-actions">
        <button class="btn btn-warning" @click="runRetention" :disabled="retentionLoading">
          {{ retentionLoading ? 'Cleaning...' : 'Retention Cleanup' }}
        </button>
        <button class="btn btn-primary" @click="triggerBackup" :disabled="triggerLoading">
          {{ triggerLoading ? 'Creating backup...' : 'Trigger Backup' }}
        </button>
      </div>
    </div>

    <div v-if="message" :class="['message', messageType === 'error' ? 'error-message' : 'info-message']">
      {{ message }}
    </div>

    <!-- Restore Form -->
    <div v-if="showRestoreForm" class="card restore-card">
      <h3>Restore Backup</h3>
      <form @submit.prevent="restoreBackup">
        <div class="form-group">
          <label>Backup ID</label>
          <input v-model="restoreForm.backup_id" type="text" required readonly />
        </div>
        <div class="form-group">
          <label>Passphrase</label>
          <input v-model="restoreForm.passphrase" type="password" required placeholder="Enter decryption passphrase" />
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="restoreLoading">
            {{ restoreLoading ? 'Restoring...' : 'Restore' }}
          </button>
          <button type="button" class="btn btn-secondary" @click="showRestoreForm = false">Cancel</button>
        </div>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading backups...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="backups.length === 0" class="empty-state">No backups found.</div>

    <div v-else class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Filename</th>
            <th>Size</th>
            <th>Encryption</th>
            <th>Status</th>
            <th>Started</th>
            <th>Completed</th>
            <th>Expires</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="backup in backups" :key="backup.id">
            <td class="id-cell">{{ backup.id }}</td>
            <td>{{ backup.filename }}</td>
            <td>{{ formatSize(backup.file_size) }}</td>
            <td>{{ backup.encryption_method || 'none' }}</td>
            <td>
              <span class="badge" :class="'badge-' + backup.status">
                {{ backup.status }}
              </span>
            </td>
            <td>{{ formatDate(backup.started_at) }}</td>
            <td>{{ formatDate(backup.completed_at) }}</td>
            <td>{{ formatDate(backup.expires_at) }}</td>
            <td>
              <button
                v-if="backup.status === 'completed'"
                class="btn btn-small btn-restore"
                @click="openRestore(backup.id)"
              >Restore</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

interface BackupRecord {
  id: string
  filename: string
  file_size: number
  encryption_method: string
  status: string
  started_at: string
  completed_at: string
  expires_at: string
  created_at: string
}

const backups = ref<BackupRecord[]>([])
const loading = ref(true)
const error = ref('')
const triggerLoading = ref(false)
const restoreLoading = ref(false)
const retentionLoading = ref(false)
const message = ref('')
const messageType = ref<'info' | 'error'>('info')

const showRestoreForm = ref(false)
const restoreForm = ref({ backup_id: '', passphrase: '' })

onMounted(async () => {
  await fetchBackups()
})

async function fetchBackups() {
  try {
    const response = await api.get('/backup/records')
    backups.value = response.data.items || response.data || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load backups'
  } finally {
    loading.value = false
  }
}

async function triggerBackup() {
  triggerLoading.value = true
  message.value = ''
  try {
    const resp = await api.post('/backup/trigger')
    message.value = `Backup triggered successfully. Backup ID: ${resp.data.backup_id || 'pending'}`
    messageType.value = 'info'
    await fetchBackups()
  } catch (err: any) {
    message.value = err.response?.data?.detail || 'Failed to trigger backup'
    messageType.value = 'error'
  } finally {
    triggerLoading.value = false
  }
}

function openRestore(backupId: string) {
  restoreForm.value = { backup_id: backupId, passphrase: '' }
  showRestoreForm.value = true
}

async function restoreBackup() {
  restoreLoading.value = true
  message.value = ''
  try {
    await api.post('/backup/restore', {
      backup_id: restoreForm.value.backup_id,
      passphrase: restoreForm.value.passphrase,
    })
    message.value = 'Restore initiated successfully.'
    messageType.value = 'info'
    showRestoreForm.value = false
    restoreForm.value = { backup_id: '', passphrase: '' }
  } catch (err: any) {
    message.value = err.response?.data?.detail || 'Failed to restore backup'
    messageType.value = 'error'
  } finally {
    restoreLoading.value = false
  }
}

async function runRetention() {
  retentionLoading.value = true
  message.value = ''
  try {
    const resp = await api.post('/backup/retention')
    message.value = `Retention cleanup complete. Deleted ${resp.data.deleted} expired backup(s).`
    messageType.value = 'info'
    await fetchBackups()
  } catch (err: any) {
    message.value = err.response?.data?.detail || 'Failed to run retention cleanup'
    messageType.value = 'error'
  } finally {
    retentionLoading.value = false
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<style scoped>
.backup-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.table-container { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.id-cell { font-family: monospace; font-size: 11px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-running { background: #cce5ff; color: #004085; }
.badge-completed { background: #d4edda; color: #155724; }
.badge-failed { background: #f8d7da; color: #721c24; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-warning { background: #f0ad4e; color: white; }
.btn-small { padding: 4px 10px; font-size: 12px; }
.btn-restore { background: #17a2b8; color: white; }
.btn-primary:disabled, .btn-warning:disabled { opacity: 0.6; cursor: not-allowed; }
.restore-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.restore-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.form-actions { display: flex; gap: 8px; }
.info-message { background: #e8f5e9; color: #2e7d32; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; }
.error-message { color: #dc3545; padding: 12px; background: #f8d7da; border-radius: 4px; margin-bottom: 16px; }
.message { margin-bottom: 16px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }
</style>
