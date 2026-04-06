<template>
  <div class="payment-view">
    <div class="page-header">
      <h1>Payments</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancel' : 'Submit Payment Evidence' }}
      </button>
    </div>

    <div v-if="showForm" class="card form-card">
      <h3>Submit Payment Evidence</h3>
      <form @submit.prevent="submitPayment">
        <div class="form-group">
          <label>Bill ID</label>
          <input v-model="form.bill_id" type="text" required placeholder="Bill ID to pay against" />
        </div>
        <div class="form-group">
          <label>Amount</label>
          <input v-model="form.amount" type="number" step="0.01" min="0.01" required placeholder="0.00" />
        </div>
        <div class="form-group">
          <label>Payment Method</label>
          <select v-model="form.payment_method" required>
            <option value="check">Check</option>
            <option value="money_order">Money Order</option>
          </select>
        </div>
        <div class="form-group">
          <label>Evidence File (JPG or PNG only, max 10MB)</label>
          <input type="file" @change="onFileChange" accept="image/jpeg,image/png" />
          <p v-if="fileError" class="error-message">{{ fileError }}</p>
        </div>
        <div v-if="formError" class="error-message">{{ formError }}</div>
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Submitting...' : 'Submit Payment' }}
        </button>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading payments...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="payments.length === 0" class="empty-state">No payments found.</div>

    <div v-else class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Bill</th>
            <th>Amount</th>
            <th>Method</th>
            <th>Status</th>
            <th>Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="payment in payments" :key="payment.id">
            <td class="id-cell">{{ payment.id }}</td>
            <td class="id-cell">{{ payment.bill_id }}</td>
            <td>${{ payment.amount }}</td>
            <td>{{ payment.payment_method }}</td>
            <td>
              <span class="badge" :class="'badge-' + payment.status">{{ payment.status }}</span>
            </td>
            <td>{{ formatDate(payment.created_at) }}</td>
            <td>
              <button class="btn btn-small btn-receipt" @click="downloadReceipt(payment)">Download Receipt</button>
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
import { generateReceiptPdf } from '@/services/pdfGenerator'

interface Payment {
  id: string
  bill_id: string
  amount: string
  payment_method: string
  status: string
  created_at: string
}

const payments = ref<Payment[]>([])
const loading = ref(true)
const error = ref('')
const showForm = ref(false)
const submitting = ref(false)
const formError = ref('')
const evidenceFile = ref<File | null>(null)

const fileError = ref('')
const form = ref({ bill_id: '', amount: '', payment_method: 'check' })

onMounted(async () => {
  await fetchPayments()
})

async function fetchPayments() {
  try {
    const resp = await api.get('/payments/')
    payments.value = resp.data.items || resp.data || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load payments'
  } finally {
    loading.value = false
  }
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0] || null
  fileError.value = ''
  if (file) {
    const allowedTypes = ['image/jpeg', 'image/png']
    if (!allowedTypes.includes(file.type)) {
      fileError.value = 'Only JPG and PNG files are allowed.'
      evidenceFile.value = null
      target.value = ''
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      fileError.value = 'File must be 10MB or smaller.'
      evidenceFile.value = null
      target.value = ''
      return
    }
  }
  evidenceFile.value = file
}

async function submitPayment() {
  formError.value = ''
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('bill_id', form.value.bill_id)
    formData.append('amount', form.value.amount)
    formData.append('payment_method', form.value.payment_method)
    if (evidenceFile.value) {
      formData.append('evidence_file', evidenceFile.value)
    }
    await api.post('/payments/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.value = { bill_id: '', amount: '', payment_method: 'check' }
    evidenceFile.value = null
    showForm.value = false
    await fetchPayments()
  } catch (err: any) {
    formError.value = err.response?.data?.detail || 'Failed to submit payment'
  } finally {
    submitting.value = false
  }
}

function downloadReceipt(payment: Payment) {
  const blob = generateReceiptPdf({
    receiptNumber: payment.id,
    residentName: '',
    propertyName: '',
    paymentDate: formatDate(payment.created_at),
    paymentMethod: payment.payment_method,
    amount: payment.amount,
    billReference: payment.bill_id,
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `receipt-${payment.id.slice(0, 8)}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.payment-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.form-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.form-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.table-container { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.id-cell { font-family: monospace; font-size: 11px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-approved { background: #d4edda; color: #155724; }
.badge-rejected { background: #f8d7da; color: #721c24; }
.badge-submitted { background: #cce5ff; color: #004085; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-small { padding: 4px 10px; font-size: 12px; }
.btn-receipt { background: #17a2b8; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }
</style>
