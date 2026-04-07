<template>
  <div class="addresses-view">
    <div class="page-header">
      <h1>My Addresses</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancel' : 'Add Address' }}
      </button>
    </div>

    <div v-if="showForm" class="card form-card">
      <h3>{{ editingId ? 'Edit Address' : 'New Address' }}</h3>
      <form @submit.prevent="saveAddress">
        <div class="form-group">
          <label>Type</label>
          <select v-model="form.address_type" required>
            <option value="shipping">Shipping</option>
            <option value="mailing">Mailing</option>
          </select>
        </div>
        <div class="form-group">
          <label>Street Line 1</label>
          <input v-model="form.line1" type="text" required placeholder="123 Main St" />
        </div>
        <div class="form-group">
          <label>Street Line 2</label>
          <input v-model="form.line2" type="text" placeholder="Apt 4B" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>City</label>
            <input v-model="form.city" type="text" required />
          </div>
          <div class="form-group">
            <label>State</label>
            <input v-model="form.state" type="text" required maxlength="2" placeholder="CA" />
          </div>
          <div class="form-group">
            <label>ZIP</label>
            <input v-model="form.zip_code" type="text" required maxlength="10" placeholder="90210" />
          </div>
        </div>
        <div v-if="formError" class="error-message">{{ formError }}</div>
        <button type="submit" class="btn btn-primary" :disabled="saving">
          {{ saving ? 'Saving...' : (editingId ? 'Update' : 'Create') }}
        </button>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading addresses...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="addresses.length === 0" class="empty-state">No addresses on file.</div>

    <div v-else class="address-list">
      <div v-for="addr in addresses" :key="addr.id" class="card address-card">
        <div class="address-header">
          <span class="badge" :class="'badge-' + addr.address_type">{{ addr.address_type }}</span>
          <div class="address-actions">
            <button class="btn btn-small btn-secondary" @click="editAddress(addr)">Edit</button>
            <button class="btn btn-small btn-danger" @click="deleteAddress(addr.id)">Delete</button>
          </div>
        </div>
        <p class="address-text">
          {{ addr.line1 }}<br />
          <span v-if="addr.line2">{{ addr.line2 }}<br /></span>
          {{ addr.city }}, {{ addr.state }} {{ addr.zip_code }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

interface Address {
  id: string
  version: number
  address_type: string
  line1: string
  line2: string
  city: string
  state: string
  zip_code: string
}

const addresses = ref<Address[]>([])
const loading = ref(true)
const error = ref('')
const showForm = ref(false)
const saving = ref(false)
const formError = ref('')
const editingId = ref<string | null>(null)
const editingVersion = ref<number>(0)

const emptyForm = { address_type: 'shipping', line1: '', line2: '', city: '', state: '', zip_code: '' }
const form = ref({ ...emptyForm })

onMounted(async () => {
  await fetchAddresses()
})

async function fetchAddresses() {
  try {
    const resp = await api.get('/residents/me/addresses')
    addresses.value = resp.data.items || resp.data || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load addresses'
  } finally {
    loading.value = false
  }
}

function editAddress(addr: Address) {
  editingId.value = addr.id
  editingVersion.value = addr.version ?? 0
  form.value = { address_type: addr.address_type, line1: addr.line1, line2: addr.line2 || '', city: addr.city, state: addr.state, zip_code: addr.zip_code }
  showForm.value = true
}

async function saveAddress() {
  formError.value = ''
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/residents/me/addresses/${editingId.value}`, form.value, {
        headers: { 'If-Match': String(editingVersion.value) },
      })
    } else {
      await api.post('/residents/me/addresses', form.value)
    }
    form.value = { ...emptyForm }
    editingId.value = null
    editingVersion.value = 0
    showForm.value = false
    await fetchAddresses()
  } catch (err: any) {
    formError.value = err.response?.data?.detail || 'Failed to save address'
  } finally {
    saving.value = false
  }
}

async function deleteAddress(id: string) {
  if (!confirm('Delete this address?')) return
  try {
    await api.delete(`/residents/me/addresses/${id}`)
    await fetchAddresses()
  } catch (err: any) {
    alert(err.response?.data?.detail || 'Failed to delete address')
  }
}
</script>

<style scoped>
.addresses-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.form-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.form-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.form-row { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 12px; }
.address-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.address-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }
.address-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.address-actions { display: flex; gap: 4px; }
.address-text { margin: 0; color: #333; line-height: 1.6; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-shipping { background: #cce5ff; color: #004085; }
.badge-mailing { background: #e3f2fd; color: #1565c0; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-danger { background: #dc3545; color: white; }
.btn-small { padding: 4px 10px; font-size: 12px; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }
</style>
