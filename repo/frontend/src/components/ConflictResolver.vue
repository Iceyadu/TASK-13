<template>
  <div v-if="conflict" class="conflict-overlay">
    <div class="conflict-modal">
      <h2>Conflict Detected</h2>
      <p class="conflict-message">
        This record was modified by another user while you were working offline.
        Your version: <strong>{{ conflict.your_version }}</strong>,
        Server version: <strong>{{ conflict.server_version }}</strong>.
      </p>

      <div class="conflict-actions-global">
        <button class="btn btn-outline" @click="keepAllMine">Keep All Mine</button>
        <button class="btn btn-outline" @click="keepAllTheirs">Keep All Theirs</button>
      </div>

      <table class="conflict-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Your Value</th>
            <th>Server Value</th>
            <th>Resolution</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="field in conflict.changed_fields" :key="field" class="conflict-row">
            <td class="field-name">{{ field }}</td>
            <td class="value-mine" :class="{ selected: resolutions[field] === 'mine' }">
              {{ formatValue(conflict.your_data[field]) }}
            </td>
            <td class="value-theirs" :class="{ selected: resolutions[field] === 'theirs' }">
              {{ formatValue(conflict.server_data[field]) }}
            </td>
            <td class="resolution-actions">
              <button
                :class="['btn-sm', resolutions[field] === 'mine' ? 'btn-active' : 'btn-ghost']"
                @click="setResolution(field, 'mine')"
              >Keep Mine</button>
              <button
                :class="['btn-sm', resolutions[field] === 'theirs' ? 'btn-active' : 'btn-ghost']"
                @click="setResolution(field, 'theirs')"
              >Keep Theirs</button>
              <button
                :class="['btn-sm', resolutions[field] === 'merge' ? 'btn-active' : 'btn-ghost']"
                @click="startMerge(field)"
              >Merge</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="mergeField" class="merge-editor">
        <h3>Merge: {{ mergeField }}</h3>
        <label>Combined value:</label>
        <textarea v-model="mergeValue" rows="3" class="merge-textarea"></textarea>
        <button class="btn btn-primary" @click="applyMerge">Apply Merge</button>
        <button class="btn btn-outline" @click="cancelMerge">Cancel</button>
      </div>

      <div class="conflict-footer">
        <button class="btn btn-primary" :disabled="!allResolved" @click="submitResolution">
          Apply Resolution
        </button>
        <button class="btn btn-danger" @click="discardChange">Discard My Change</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ConflictResponse } from '@/types'
import api from '@/services/api'
import { removeFromRetryQueue } from '@/services/offlineCache'

const props = defineProps<{
  conflict: ConflictResponse | null
  queueItemId: number
  requestUrl: string
  requestMethod: string
}>()

const emit = defineEmits<{
  resolved: []
  discarded: []
}>()

type Resolution = 'mine' | 'theirs' | 'merge'
const resolutions = ref<Record<string, Resolution>>({})
const mergeValues = ref<Record<string, string>>({})
const mergeField = ref<string | null>(null)
const mergeValue = ref('')

watch(() => props.conflict, (c) => {
  if (c) {
    resolutions.value = {}
    mergeValues.value = {}
    // Default all to "theirs"
    for (const f of c.changed_fields) {
      resolutions.value[f] = 'theirs'
    }
  }
})

const allResolved = computed(() => {
  if (!props.conflict) return false
  return props.conflict.changed_fields.every(f => resolutions.value[f])
})

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '(empty)'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function setResolution(field: string, res: Resolution) {
  resolutions.value[field] = res
}

function keepAllMine() {
  if (!props.conflict) return
  for (const f of props.conflict.changed_fields) {
    resolutions.value[f] = 'mine'
  }
}

function keepAllTheirs() {
  if (!props.conflict) return
  for (const f of props.conflict.changed_fields) {
    resolutions.value[f] = 'theirs'
  }
}

function startMerge(field: string) {
  mergeField.value = field
  const mine = props.conflict?.your_data[field]
  const theirs = props.conflict?.server_data[field]
  mergeValue.value = `${formatValue(mine)} | ${formatValue(theirs)}`
  resolutions.value[field] = 'merge'
}

function applyMerge() {
  if (mergeField.value) {
    mergeValues.value[mergeField.value] = mergeValue.value
    mergeField.value = null
    mergeValue.value = ''
  }
}

function cancelMerge() {
  if (mergeField.value) {
    resolutions.value[mergeField.value] = 'theirs'
  }
  mergeField.value = null
  mergeValue.value = ''
}

async function submitResolution() {
  if (!props.conflict) return

  // Build resolved payload
  const resolved: Record<string, unknown> = {}
  for (const field of props.conflict.changed_fields) {
    const res = resolutions.value[field]
    if (res === 'mine') {
      resolved[field] = props.conflict.your_data[field]
    } else if (res === 'theirs') {
      resolved[field] = props.conflict.server_data[field]
    } else if (res === 'merge') {
      resolved[field] = mergeValues.value[field] ?? props.conflict.server_data[field]
    }
  }

  try {
    await api.request({
      method: props.requestMethod,
      url: props.requestUrl,
      data: resolved,
      headers: { 'If-Match': String(props.conflict.server_version) },
    })
    // Remove the conflicted item from queue
    await removeFromRetryQueue(props.queueItemId)
    emit('resolved')
  } catch (err) {
    console.error('Failed to submit resolution:', err)
  }
}

async function discardChange() {
  await removeFromRetryQueue(props.queueItemId)
  emit('discarded')
}
</script>

<style scoped>
.conflict-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.conflict-modal {
  background: white; border-radius: 8px; padding: 24px; max-width: 800px; width: 95%;
  max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
h2 { color: #c0392b; margin-bottom: 8px; }
.conflict-message { color: #555; margin-bottom: 16px; }
.conflict-actions-global { display: flex; gap: 8px; margin-bottom: 16px; }
.conflict-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
.conflict-table th, .conflict-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.conflict-table th { background: #f5f5f5; }
.field-name { font-weight: bold; width: 120px; }
.value-mine { background: #fef3e2; }
.value-theirs { background: #e8f5e9; }
.value-mine.selected { background: #fff3cd; border: 2px solid #f0ad4e; }
.value-theirs.selected { background: #d4edda; border: 2px solid #28a745; }
.resolution-actions { display: flex; gap: 4px; flex-wrap: wrap; }
.btn-sm { padding: 2px 8px; font-size: 11px; border: 1px solid #ccc; border-radius: 3px; cursor: pointer; background: white; }
.btn-active { background: #007bff; color: white; border-color: #007bff; }
.btn-ghost { background: white; }
.btn-sm:hover { opacity: 0.8; }
.merge-editor { background: #f9f9f9; padding: 12px; border-radius: 4px; margin-bottom: 16px; }
.merge-textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; }
.conflict-footer { display: flex; gap: 8px; justify-content: flex-end; }
.btn { padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; border: 1px solid #ccc; }
.btn-primary { background: #007bff; color: white; border-color: #007bff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { background: #dc3545; color: white; border-color: #dc3545; }
.btn-outline { background: white; border: 1px solid #007bff; color: #007bff; }
</style>
