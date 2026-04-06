<template>
  <div class="listings-view">
    <h1>Community Listings</h1>
    <div class="header-actions">
      <button v-if="auth.hasRole('admin','property_manager')" @click="showCreate = !showCreate" class="btn btn-primary">
        {{ showCreate ? 'Cancel' : 'New Listing' }}
      </button>
      <template v-if="auth.hasRole('admin','property_manager') && selectedIds.length > 0">
        <button @click="bulkSetStatus('published')" class="btn btn-promote">Bulk Publish ({{ selectedIds.length }})</button>
        <button @click="bulkSetStatus('unpublished')" class="btn btn-secondary">Bulk Unpublish ({{ selectedIds.length }})</button>
      </template>
    </div>
    <div v-if="showCreate" class="create-form">
      <input v-model="form.title" placeholder="Title" class="input" />
      <textarea v-model="form.description" placeholder="Description" class="input" rows="2"></textarea>
      <select v-model="form.category" class="input">
        <option value="garage_sale">Garage Sale</option>
        <option value="parking_sublet">Parking Sublet</option>
        <option value="amenity_addon">Amenity Add-on</option>
      </select>
      <input v-model.number="form.price" type="number" placeholder="Price" class="input" />
      <button @click="saveListing" class="btn btn-primary" :disabled="!form.title">
        {{ editingId ? 'Update Listing' : 'Create Draft' }}
      </button>
      <button v-if="editingId" @click="cancelEdit" class="btn btn-secondary" style="margin-left:8px">Cancel Edit</button>
    </div>
    <p v-if="mediaError" class="error-message">{{ mediaError }}</p>
    <div class="listing-grid">
      <div v-for="item in listings" :key="item.id" class="listing-card">
        <div class="listing-select" v-if="auth.hasRole('admin','property_manager')">
          <input type="checkbox" :value="item.id" v-model="selectedIds" />
        </div>
        <h3>{{ item.title }}</h3>
        <p class="listing-category">{{ item.category.replace('_', ' ') }}</p>
        <p v-if="item.description">{{ item.description }}</p>
        <p v-if="item.price" class="listing-price">${{ item.price }}</p>
        <span :class="'badge badge-' + item.status">{{ item.status }}</span>
        <div v-if="item.media && item.media.length > 0" class="listing-media">
          <div v-for="m in item.media" :key="m.media_id" class="media-thumb">
            <img
              v-if="m.content_type && m.content_type.startsWith('image/')"
              :src="apiBaseUrl + '/media/' + m.media_id + '/download'"
              :alt="m.filename || 'media'"
              class="media-img"
            />
            <a
              v-else
              :href="apiBaseUrl + '/media/' + m.media_id + '/download'"
              target="_blank"
              class="media-link"
            >{{ m.filename || 'Download' }}</a>
          </div>
        </div>
        <div v-if="auth.hasRole('admin','property_manager')" class="listing-actions">
          <button @click="editListing(item)" class="btn-sm btn-edit">Edit</button>
          <button v-if="item.status === 'draft'" @click="setStatus(item.id, 'published', item.version)" class="btn-sm">Publish</button>
          <button v-if="item.status === 'published'" @click="setStatus(item.id, 'unpublished', item.version)" class="btn-sm">Unpublish</button>
          <label class="btn-sm btn-upload-label">
            Upload Media
            <input type="file" accept="image/jpeg,image/png,video/mp4" @change="uploadMedia(item.id, $event)" hidden />
          </label>
        </div>
      </div>
    </div>
    <p v-if="!loading && listings.length === 0" class="empty">No listings found.</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : '/api/v1'
const listings = ref<any[]>([])
const loading = ref(true)
const showCreate = ref(false)
const editingId = ref<string | null>(null)
const editingVersion = ref<number>(0)
const selectedIds = ref<string[]>([])
const mediaError = ref('')
const form = ref({ title: '', description: '', category: 'garage_sale', price: 0 })

onMounted(fetchListings)

async function fetchListings() {
  loading.value = true
  try {
    const resp = await api.get('/listings/')
    listings.value = resp.data.items || []
  } catch { /* empty */ } finally { loading.value = false }
}

function editListing(item: any) {
  editingId.value = item.id
  editingVersion.value = item.version ?? 0
  form.value = { title: item.title, description: item.description || '', category: item.category, price: item.price || 0 }
  showCreate.value = true
}

function cancelEdit() {
  editingId.value = null
  form.value = { title: '', description: '', category: 'garage_sale', price: 0 }
  showCreate.value = false
}

async function saveListing() {
  if (editingId.value) {
    await api.put(`/listings/${editingId.value}`, form.value, {
      headers: { 'If-Match': String(editingVersion.value) },
    })
    editingId.value = null
  } else {
    const props = await api.get('/properties/')
    const propId = props.data.items?.[0]?.id
    if (!propId) return
    await api.post('/listings/', { property_id: propId, ...form.value })
  }
  form.value = { title: '', description: '', category: 'garage_sale', price: 0 }
  showCreate.value = false
  await fetchListings()
}

async function setStatus(id: string, status: string, version?: number) {
  await api.put(`/listings/${id}/status`, { status }, {
    headers: { 'If-Match': String(version ?? 0) },
  })
  await fetchListings()
}

async function bulkSetStatus(status: string) {
  for (const id of selectedIds.value) {
    try {
      await api.put(`/listings/${id}/status`, { status })
    } catch { /* skip failures */ }
  }
  selectedIds.value = []
  await fetchListings()
}

async function uploadMedia(listingId: string, event: Event) {
  mediaError.value = ''
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const allowedTypes = ['image/jpeg', 'image/png', 'video/mp4']
  if (!allowedTypes.includes(file.type)) {
    mediaError.value = 'Only JPG, PNG, and MP4 files are allowed.'
    target.value = ''
    return
  }
  const maxSize = file.type === 'video/mp4' ? 200 * 1024 * 1024 : 10 * 1024 * 1024
  if (file.size > maxSize) {
    mediaError.value = file.type === 'video/mp4'
      ? 'Video must be 200MB or smaller.'
      : 'Image must be 10MB or smaller.'
    target.value = ''
    return
  }

  const formData = new FormData()
  formData.append('file', file)
  try {
    await api.post(`/listings/${listingId}/media`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    await fetchListings()
  } catch (err: any) {
    mediaError.value = err.response?.data?.detail || 'Failed to upload media'
  }
  target.value = ''
}
</script>

<style scoped>
.listings-view { padding: 24px; }
.create-form { background: #f9f9f9; padding: 16px; border-radius: 8px; margin: 16px 0; }
.create-form .input { display: block; width: 100%; padding: 8px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.listing-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 16px; }
.listing-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }
.listing-card h3 { color: #1a3c5e; margin: 0 0 4px; }
.listing-category { color: #888; font-size: 12px; text-transform: capitalize; }
.listing-price { font-weight: 700; color: #2e7d32; font-size: 18px; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-draft { background: #e0e0e0; color: #424242; }
.badge-published { background: #d4edda; color: #155724; }
.badge-unpublished { background: #fff3cd; color: #856404; }
.header-actions { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.listing-actions { margin-top: 8px; display: flex; gap: 4px; flex-wrap: wrap; }
.listing-select { margin-bottom: 8px; }
.btn-sm { padding: 4px 10px; background: #1a3c5e; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
.btn-edit { background: #6c757d; }
.btn-upload-label { padding: 4px 10px; background: #17a2b8; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; display: inline-block; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-promote { background: #28a745; color: white; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.listing-media { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.media-thumb { border: 1px solid #e0e0e0; border-radius: 4px; overflow: hidden; }
.media-img { width: 80px; height: 80px; object-fit: cover; display: block; }
.media-link { display: inline-block; padding: 4px 8px; font-size: 12px; color: #1a3c5e; text-decoration: underline; }
.empty { color: #888; text-align: center; padding: 24px; }
</style>
