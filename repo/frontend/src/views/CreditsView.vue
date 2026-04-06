<template>
  <div class="credits-view">
    <div class="page-header">
      <h1>Credit Memos</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancel' : 'Request Refund' }}
      </button>
    </div>

    <div v-if="showForm" class="card form-card">
      <h3>Request Refund / Credit</h3>
      <form @submit.prevent="submitCredit">
        <div class="form-group">
          <label>Bill ID</label>
          <input v-model="form.bill_id" type="text" required placeholder="Original bill ID" />
        </div>
        <div class="form-group">
          <label>Amount</label>
          <input v-model="form.amount" type="number" step="0.01" min="0.01" required placeholder="0.00" />
        </div>
        <div class="form-group">
          <label>Reason</label>
          <textarea v-model="form.reason" rows="3" required placeholder="Explain the reason for the credit request..."></textarea>
        </div>
        <div v-if="formError" class="error-message">{{ formError }}</div>
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Submitting...' : 'Submit Request' }}
        </button>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading credits...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="credits.length === 0" class="empty-state">No credit memos found.</div>

    <div v-else class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Bill</th>
            <th>Amount</th>
            <th>Reason</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="credit in credits" :key="credit.id">
            <td class="id-cell">{{ credit.id }}</td>
            <td class="id-cell">{{ credit.bill_id }}</td>
            <td>${{ credit.amount }}</td>
            <td>{{ credit.reason }}</td>
            <td>
              <span class="badge" :class="'badge-' + credit.status">{{ credit.status }}</span>
            </td>
            <td>{{ formatDate(credit.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

interface CreditMemo {
  id: string
  bill_id: string
  amount: string
  reason: string
  status: string
  created_at: string
}

const credits = ref<CreditMemo[]>([])
const loading = ref(true)
const error = ref('')
const showForm = ref(false)
const submitting = ref(false)
const formError = ref('')

const form = ref({ bill_id: '', amount: '', reason: '' })

onMounted(async () => {
  await fetchCredits()
})

async function fetchCredits() {
  try {
    const resp = await api.get('/credits/')
    credits.value = resp.data.items || resp.data || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load credits'
  } finally {
    loading.value = false
  }
}

async function submitCredit() {
  formError.value = ''
  submitting.value = true
  try {
    await api.post('/credits/', {
      bill_id: form.value.bill_id,
      amount: parseFloat(form.value.amount),
      reason: form.value.reason,
    })
    form.value = { bill_id: '', amount: '', reason: '' }
    showForm.value = false
    await fetchCredits()
  } catch (err: any) {
    formError.value = err.response?.data?.detail || 'Failed to submit credit request'
  } finally {
    submitting.value = false
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.credits-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.form-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.form-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.table-container { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.id-cell { font-family: monospace; font-size: 11px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-approved { background: #d4edda; color: #155724; }
.badge-rejected { background: #f8d7da; color: #721c24; }
.badge-applied { background: #cce5ff; color: #004085; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }
</style>
