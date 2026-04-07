<template>
  <div class="orders-view">
    <h1>Service Orders</h1>
    <button v-if="auth.hasRole('resident')" @click="showCreate = !showCreate" class="btn btn-primary">
      {{ showCreate ? 'Cancel' : 'New Order' }}
    </button>
    <div v-if="showCreate" class="create-form">
      <h3>Submit Service Order</h3>
      <input v-model="newOrder.title" placeholder="Title (e.g., Fix leaking faucet)" class="input" />
      <textarea v-model="newOrder.description" placeholder="Description" class="input" rows="3"></textarea>
      <select v-model="newOrder.category" class="input">
        <option value="">Select category</option>
        <option value="plumbing">Plumbing</option>
        <option value="electrical">Electrical</option>
        <option value="appliance">Appliance</option>
        <option value="general">General</option>
      </select>
      <select v-model="newOrder.priority" class="input">
        <option value="normal">Normal</option>
        <option value="high">High</option>
        <option value="urgent">Urgent</option>
        <option value="low">Low</option>
      </select>
      <button @click="submitOrder" class="btn btn-primary" :disabled="!newOrder.title">Submit Order</button>
      <p v-if="createError" class="error">{{ createError }}</p>
    </div>
    <div v-if="loading" class="loading">Loading orders...</div>
    <div v-else>
      <div v-for="order in orders" :key="order.id" class="order-card">
        <div class="order-header">
          <h3>{{ order.title }}</h3>
          <span :class="'badge badge-' + order.status">{{ order.status.replace('_', ' ') }}</span>
        </div>
        <p class="order-meta">{{ order.category || 'General' }} | Priority: {{ order.priority }} | {{ order.created_at.slice(0, 10) }}</p>
        <p v-if="order.description" class="order-desc">{{ order.description }}</p>
        <p v-if="order.assigned_to" class="order-assignee">Assigned to: {{ order.assigned_to }}</p>

        <div v-if="canOperateOrder(order)" class="staff-actions">
          <button
            v-if="!order.assigned_to"
            @click="assignToMe(order)"
            class="btn-sm btn-assign"
          >
            Assign To Me
          </button>
          <button
            v-for="next in nextTransitions(order.status)"
            :key="next"
            class="btn-sm"
            @click="transitionOrder(order, next)"
          >
            {{ next.replace('_', ' ') }}
          </button>
        </div>
        <p v-if="actionErrorByOrder[order.id]" class="error">{{ actionErrorByOrder[order.id] }}</p>
        <div class="milestones">
          <div v-for="m in order.milestones" :key="m.created_at" class="milestone">
            <span class="milestone-dot"></span>
            <span class="milestone-status">{{ (m.to_status || '').replace('_', ' ') }}</span>
            <span class="milestone-time">{{ m.created_at.slice(0, 19).replace('T', ' ') }}</span>
            <span v-if="m.notes" class="milestone-notes">{{ m.notes }}</span>
          </div>
        </div>
      </div>
      <p v-if="orders.length === 0" class="empty">No service orders found.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { v4 as uuidv4 } from 'uuid'

const auth = useAuthStore()
const orders = ref<any[]>([])
const loading = ref(true)
const showCreate = ref(false)
const createError = ref('')
const actionErrorByOrder = ref<Record<string, string>>({})
const newOrder = ref({ title: '', description: '', category: '', priority: 'normal' })

const ORDER_TRANSITIONS: Record<string, string[]> = {
  created: ['payment_recorded'],
  payment_recorded: ['accepted'],
  accepted: ['dispatched'],
  dispatched: ['arrived'],
  arrived: ['in_service'],
  in_service: ['completed'],
  completed: ['after_sales_credit'],
  after_sales_credit: [],
}

const TRANSITION_ROLES: Record<string, string[]> = {
  payment_recorded: ['resident', 'accounting_clerk', 'admin'],
  accepted: ['property_manager', 'accounting_clerk', 'admin'],
  dispatched: ['property_manager', 'maintenance_dispatcher', 'admin'],
  arrived: ['maintenance_dispatcher', 'admin'],
  in_service: ['maintenance_dispatcher', 'admin'],
  completed: ['maintenance_dispatcher', 'admin'],
  after_sales_credit: ['property_manager', 'accounting_clerk', 'admin'],
}

onMounted(async () => {
  await fetchOrders()
})

async function fetchOrders() {
  try {
    const resp = await api.get('/orders/')
    orders.value = resp.data.items || []
  } catch { /* empty */ } finally { loading.value = false }
}

function canOperateOrder(order: any) {
  if (!auth.user) return false
  if (auth.user.role === 'resident') return false
  return nextTransitions(order.status).length > 0 || !order.assigned_to
}

function nextTransitions(status: string): string[] {
  const all = ORDER_TRANSITIONS[status] || []
  const role = auth.user?.role || ''
  return all.filter((s) => (TRANSITION_ROLES[s] || []).includes(role))
}

async function submitOrder() {
  createError.value = ''
  try {
    const props = await api.get('/properties/')
    const propId = props.data.items?.[0]?.id
    if (!propId) { createError.value = 'No property found'; return }
    await api.post('/orders/', {
      property_id: propId,
      title: newOrder.value.title,
      description: newOrder.value.description || null,
      category: newOrder.value.category || null,
      priority: newOrder.value.priority,
      idempotency_key: uuidv4(),
    })
    showCreate.value = false
    await fetchOrders()
  } catch (e: any) { createError.value = e.response?.data?.detail || 'Failed to create order' }
}

async function assignToMe(order: any) {
  actionErrorByOrder.value[order.id] = ''
  try {
    await api.put(`/orders/${order.id}`, { assigned_to: auth.user?.id }, {
      headers: { 'If-Match': String(order.version ?? 0) },
    })
    await fetchOrders()
  } catch (e: any) {
    actionErrorByOrder.value[order.id] = e.response?.data?.detail || 'Failed to assign order'
  }
}

async function transitionOrder(order: any, toStatus: string) {
  actionErrorByOrder.value[order.id] = ''
  try {
    await api.post(`/orders/${order.id}/transition`, {
      to_status: toStatus,
      notes: `Transitioned to ${toStatus.replace('_', ' ')}`,
      idempotency_key: uuidv4(),
    }, {
      headers: { 'If-Match': String(order.version ?? 0) },
    })
    await fetchOrders()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    actionErrorByOrder.value[order.id] = typeof detail === 'string'
      ? detail
      : detail?.message || 'Failed to transition order'
  }
}
</script>

<style scoped>
.orders-view { padding: 24px; }
.create-form { background: #f9f9f9; padding: 16px; border-radius: 8px; margin: 16px 0; }
.create-form .input { display: block; width: 100%; padding: 8px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.order-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 12px 0; }
.order-header { display: flex; justify-content: space-between; align-items: center; }
.order-header h3 { margin: 0; color: #1a3c5e; }
.order-meta { color: #888; font-size: 13px; margin: 4px 0; }
.order-desc { color: #555; font-size: 14px; }
.order-assignee { color: #555; font-size: 12px; margin: 6px 0; }
.staff-actions { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.badge { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; text-transform: capitalize; }
.badge-created { background: #e3f2fd; color: #1565c0; }
.badge-payment_recorded { background: #fff3e0; color: #e65100; }
.badge-accepted { background: #e8f5e9; color: #2e7d32; }
.badge-dispatched { background: #f3e5f5; color: #7b1fa2; }
.badge-arrived { background: #e0f7fa; color: #00838f; }
.badge-in_service { background: #fff9c4; color: #f57f17; }
.badge-completed { background: #c8e6c9; color: #1b5e20; }
.badge-after_sales_credit { background: #ffccbc; color: #bf360c; }
.milestones { margin-top: 12px; border-left: 2px solid #1a3c5e; padding-left: 16px; }
.milestone { margin: 8px 0; display: flex; align-items: center; gap: 8px; font-size: 13px; }
.milestone-dot { width: 8px; height: 8px; background: #1a3c5e; border-radius: 50%; }
.milestone-status { font-weight: 600; text-transform: capitalize; }
.milestone-time { color: #888; }
.milestone-notes { color: #666; font-style: italic; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-assign { background: #6c757d; }
.empty { color: #888; text-align: center; padding: 24px; }
.loading { text-align: center; padding: 24px; color: #666; }
.error { color: #dc3545; font-size: 14px; }
</style>
