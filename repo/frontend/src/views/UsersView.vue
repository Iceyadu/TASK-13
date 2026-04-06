<template>
  <div class="users-view">
    <div class="page-header">
      <h1>User Management</h1>
      <button class="btn btn-primary" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? 'Cancel' : 'New User' }}
      </button>
    </div>

    <div v-if="showCreateForm" class="card form-card">
      <h3>Create User</h3>
      <form @submit.prevent="createUser">
        <div class="form-group">
          <label for="username">Username</label>
          <input id="username" v-model="newUser.username" type="text" required placeholder="Enter username" />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input id="password" v-model="newUser.password" type="password" required placeholder="Enter password" />
        </div>
        <div class="form-group">
          <label for="role">Role</label>
          <select id="role" v-model="newUser.role" required>
            <option value="resident">Resident</option>
            <option value="property_manager">Property Manager</option>
            <option value="accounting_clerk">Accounting Clerk</option>
            <option value="maintenance_dispatcher">Maintenance Dispatcher</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div v-if="createError" class="error-message">{{ createError }}</div>
        <button type="submit" class="btn btn-primary" :disabled="createLoading">
          {{ createLoading ? 'Creating...' : 'Create User' }}
        </button>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading users...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="users.length === 0" class="empty-state">No users found.</div>

    <div v-else class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Username</th>
            <th>Role</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.username }}</td>
            <td><span class="badge badge-role">{{ user.role }}</span></td>
            <td>
              <span class="badge" :class="user.is_active ? 'badge-active' : 'badge-inactive'">
                {{ user.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const users = ref<any[]>([])
const loading = ref(true)
const error = ref('')

const showCreateForm = ref(false)
const newUser = ref({ username: '', password: '', role: 'resident' })
const createLoading = ref(false)
const createError = ref('')

onMounted(async () => {
  await fetchUsers()
})

async function fetchUsers() {
  try {
    const response = await api.get('/users/')
    users.value = response.data.items || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load users'
  } finally {
    loading.value = false
  }
}

async function createUser() {
  createError.value = ''
  createLoading.value = true
  try {
    await api.post('/users/', newUser.value)
    newUser.value = { username: '', password: '', role: 'resident' }
    showCreateForm.value = false
    await fetchUsers()
  } catch (err: any) {
    createError.value = err.response?.data?.detail || 'Failed to create user'
  } finally {
    createLoading.value = false
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.users-view { padding: 24px; }
.form-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.form-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }
.data-table th { background: #f5f5f5; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-role { background: #e3f2fd; color: #1565c0; }
.badge-active { background: #d4edda; color: #155724; }
.badge-inactive { background: #f8d7da; color: #721c24; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }
</style>
