<template>
  <div class="billing-view">
    <h1>Billing</h1>
    <div v-if="isStaff" class="staff-panel">
      <div class="staff-row">
        <input v-model="billingPeriod" class="input" placeholder="YYYY-MM" />
        <button class="btn-sm" @click="generateBills">Generate Bills</button>
        <button class="btn-sm" @click="applyLateFees">Apply Late Fees</button>
        <button class="btn-sm" @click="loadOverdue">View Overdue</button>
      </div>
      <div class="staff-row">
        <button class="btn-sm" @click="loadReconciliation">Load Reconciliation</button>
        <a class="btn-sm btn-link" :href="reconCsvUrl" target="_blank">Reconciliation CSV</a>
      </div>
      <p v-if="staffMessage" class="staff-message">{{ staffMessage }}</p>
      <div v-if="reconciliation" class="recon-box">
        <strong>Reconciliation:</strong>
        billed ${{ reconciliation.summary.total_billed }} |
        received ${{ reconciliation.summary.total_received }} |
        credits ${{ reconciliation.summary.total_credits }} |
        outstanding ${{ reconciliation.summary.total_outstanding }}
      </div>

      <div class="fee-items-box">
        <h3>Fee Items</h3>
        <div v-if="auth.hasRole('admin')" class="staff-row">
          <input v-model="feeForm.name" class="input" placeholder="Fee name" />
          <input v-model.number="feeForm.amount" type="number" step="0.01" class="input" placeholder="Amount" />
          <label class="checkbox-label">
            <input v-model="feeForm.is_taxable" type="checkbox" />
            Taxable
          </label>
          <button class="btn-sm" @click="saveFeeItem">{{ editingFeeId ? 'Update Fee Item' : 'Create Fee Item' }}</button>
          <button v-if="editingFeeId" class="btn-sm" @click="cancelFeeEdit">Cancel</button>
        </div>
        <p v-if="feeMessage" class="staff-message">{{ feeMessage }}</p>
        <table class="data-table" v-if="feeItems.length > 0">
          <thead>
            <tr>
              <th>Name</th><th>Amount</th><th>Taxable</th><th>Active</th><th v-if="auth.hasRole('admin')">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in feeItems" :key="item.id">
              <td>{{ item.name }}</td>
              <td>${{ item.amount }}</td>
              <td>{{ item.is_taxable ? 'Yes' : 'No' }}</td>
              <td>{{ item.is_active ? 'Yes' : 'No' }}</td>
              <td v-if="auth.hasRole('admin')">
                <button class="btn-sm" @click="editFeeItem(item)">Edit</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="loading" class="loading">Loading bills...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th>Period</th><th>Due Date</th><th>Subtotal</th><th>Tax</th><th>Late Fee</th><th>Total</th><th>Balance</th><th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="bill in bills" :key="bill.id">
            <td>{{ bill.billing_period }}</td>
            <td>{{ bill.due_date }}</td>
            <td>${{ bill.subtotal }}</td>
            <td>${{ bill.tax_total }}</td>
            <td>${{ bill.late_fee }}</td>
            <td>${{ bill.total }}</td>
            <td>${{ bill.balance_due }}</td>
            <td><span :class="'badge badge-' + bill.status">{{ bill.status }}</span></td>
            <td class="action-cell">
              <a :href="'/api/v1/billing/statements/' + bill.id + '/pdf'" target="_blank" class="btn-sm">PDF</a>
              <button @click="generateLocalPdf(bill)" class="btn-sm btn-local">Local PDF</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="bills.length === 0" class="empty">No bills found.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { generateStatementPdf } from '@/services/pdfGenerator'

const auth = useAuthStore()
const bills = ref<any[]>([])
const loading = ref(true)
const error = ref('')
const billingPeriod = ref(new Date().toISOString().slice(0, 7))
const staffMessage = ref('')
const reconciliation = ref<any | null>(null)
const feeItems = ref<any[]>([])
const feeMessage = ref('')
const editingFeeId = ref<string | null>(null)
const editingFeeVersion = ref<number>(0)
const feeForm = ref({ name: '', amount: 0, is_taxable: false, is_active: true })
const isStaff = auth.hasRole('admin', 'property_manager', 'accounting_clerk')
const apiBase = import.meta.env.VITE_API_BASE_URL ? `${import.meta.env.VITE_API_BASE_URL}/api/v1` : '/api/v1'
const reconCsvUrl = computed(() => `${apiBase}/billing/reconciliation/csv?billing_period=${billingPeriod.value}`)

onMounted(async () => {
  await fetchBills()
  if (isStaff) {
    await fetchFeeItems()
  }
})

async function fetchBills() {
  try {
    const resp = await api.get('/billing/bills')
    bills.value = resp.data.items || []
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load bills'
  } finally {
    loading.value = false
  }
}

function generateLocalPdf(bill: any) {
  const blob = generateStatementPdf({
    propertyName: bill.property_name || 'HarborView Property',
    residentName: auth.user?.username || 'Resident',
    unitNumber: bill.unit_number || '-',
    billingPeriod: bill.billing_period || '-',
    dueDate: bill.due_date || '-',
    lineItems: (bill.line_items || []).map((li: any) => ({
      description: li.description || li.label || '-',
      amount: String(li.amount ?? '0.00'),
      tax: String(li.tax ?? '0.00'),
      total: String(li.total ?? li.amount ?? '0.00'),
    })),
    total: String(bill.total ?? '0.00'),
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `statement-${bill.billing_period || bill.id}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

async function generateBills() {
  staffMessage.value = ''
  try {
    const props = await api.get('/properties/')
    const propId = props.data.items?.[0]?.id
    if (!propId) {
      staffMessage.value = 'No property found for bill generation.'
      return
    }
    const resp = await api.post('/billing/generate', { property_id: propId, billing_period: billingPeriod.value })
    staffMessage.value = `${resp.data.detail}: ${resp.data.bills_created} bill(s)`
    await fetchBills()
  } catch (e: any) {
    staffMessage.value = e.response?.data?.detail || 'Failed to generate bills'
  }
}

async function applyLateFees() {
  staffMessage.value = ''
  try {
    const resp = await api.post('/billing/apply-late-fees')
    staffMessage.value = `${resp.data.detail}: ${resp.data.bills_updated} bill(s)`
    await fetchBills()
  } catch (e: any) {
    staffMessage.value = e.response?.data?.detail || 'Failed to apply late fees'
  }
}

async function loadOverdue() {
  staffMessage.value = ''
  try {
    const resp = await api.get('/billing/bills/overdue')
    bills.value = resp.data.items || []
    staffMessage.value = `Loaded ${bills.value.length} overdue bill(s).`
  } catch (e: any) {
    staffMessage.value = e.response?.data?.detail || 'Failed to load overdue bills'
  }
}

async function loadReconciliation() {
  staffMessage.value = ''
  try {
    const resp = await api.get('/billing/reconciliation', { params: { billing_period: billingPeriod.value } })
    reconciliation.value = resp.data
    staffMessage.value = 'Reconciliation loaded.'
  } catch (e: any) {
    staffMessage.value = e.response?.data?.detail || 'Failed to load reconciliation'
  }
}

async function fetchFeeItems() {
  try {
    const resp = await api.get('/billing/fee-items')
    feeItems.value = resp.data.items || []
  } catch (e: any) {
    feeMessage.value = e.response?.data?.detail || 'Failed to load fee items'
  }
}

function editFeeItem(item: any) {
  editingFeeId.value = item.id
  editingFeeVersion.value = item.version ?? 0
  feeForm.value = {
    name: item.name,
    amount: Number(item.amount ?? 0),
    is_taxable: !!item.is_taxable,
    is_active: !!item.is_active,
  }
}

function cancelFeeEdit() {
  editingFeeId.value = null
  editingFeeVersion.value = 0
  feeForm.value = { name: '', amount: 0, is_taxable: false, is_active: true }
}

async function saveFeeItem() {
  feeMessage.value = ''
  try {
    const props = await api.get('/properties/')
    const propId = props.data.items?.[0]?.id
    if (!propId) {
      feeMessage.value = 'No property found for fee item.'
      return
    }
    if (editingFeeId.value) {
      await api.put(`/billing/fee-items/${editingFeeId.value}`, {
        name: feeForm.value.name,
        amount: feeForm.value.amount,
        is_taxable: feeForm.value.is_taxable,
        is_active: feeForm.value.is_active,
      }, {
        headers: { 'If-Match': String(editingFeeVersion.value) },
      })
      feeMessage.value = 'Fee item updated.'
    } else {
      await api.post('/billing/fee-items', {
        property_id: propId,
        name: feeForm.value.name,
        amount: feeForm.value.amount,
        is_taxable: feeForm.value.is_taxable,
      })
      feeMessage.value = 'Fee item created.'
    }
    cancelFeeEdit()
    await fetchFeeItems()
  } catch (e: any) {
    feeMessage.value = e.response?.data?.detail || 'Failed to save fee item'
  }
}
</script>

<style scoped>
.billing-view { padding: 24px; }
.staff-panel { background: #f7f9fc; border: 1px solid #dce3ee; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
.staff-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; flex-wrap: wrap; }
.input { padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }
.staff-message { color: #1a3c5e; font-size: 13px; margin: 6px 0; }
.recon-box { font-size: 13px; color: #333; background: #fff; border: 1px solid #e3e8f0; border-radius: 4px; padding: 8px; }
.fee-items-box { margin-top: 12px; background: #fff; border: 1px solid #e3e8f0; border-radius: 4px; padding: 8px; }
.fee-items-box h3 { margin: 4px 0 8px; }
.checkbox-label { font-size: 12px; display: inline-flex; align-items: center; gap: 4px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-generated { background: #fff3cd; color: #856404; }
.badge-paid { background: #d4edda; color: #155724; }
.badge-overdue { background: #f8d7da; color: #721c24; }
.badge-partially_paid { background: #cce5ff; color: #004085; }
.btn-sm { padding: 3px 8px; background: #1a3c5e; color: white; border-radius: 3px; text-decoration: none; font-size: 12px; cursor: pointer; border: none; }
.btn-link { display: inline-block; }
.btn-local { background: #28a745; }
.action-cell { display: flex; gap: 4px; }
.empty { color: #888; text-align: center; padding: 24px; }
.loading { text-align: center; padding: 24px; color: #666; }
.error { color: #dc3545; padding: 12px; }
</style>
