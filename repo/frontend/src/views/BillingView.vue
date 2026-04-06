<template>
  <div class="billing-view">
    <h1>Billing</h1>
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
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { generateStatementPdf } from '@/services/pdfGenerator'

const auth = useAuthStore()
const bills = ref<any[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const resp = await api.get('/billing/bills')
    bills.value = resp.data.items || []
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load bills'
  } finally {
    loading.value = false
  }
})

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
</script>

<style scoped>
.billing-view { padding: 24px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-generated { background: #fff3cd; color: #856404; }
.badge-paid { background: #d4edda; color: #155724; }
.badge-overdue { background: #f8d7da; color: #721c24; }
.badge-partially_paid { background: #cce5ff; color: #004085; }
.btn-sm { padding: 3px 8px; background: #1a3c5e; color: white; border-radius: 3px; text-decoration: none; font-size: 12px; cursor: pointer; border: none; }
.btn-local { background: #28a745; }
.action-cell { display: flex; gap: 4px; }
.empty { color: #888; text-align: center; padding: 24px; }
.loading { text-align: center; padding: 24px; color: #666; }
.error { color: #dc3545; padding: 12px; }
</style>
