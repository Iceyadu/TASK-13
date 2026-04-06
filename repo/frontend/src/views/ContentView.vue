<template>
  <div class="content-view">
    <div class="page-header">
      <h1>Content Management</h1>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="previewMode = !previewMode">
          {{ previewMode ? 'Edit Mode' : 'Preview Mode' }}
        </button>
        <button class="btn btn-primary" @click="showCreateForm = !showCreateForm">
          {{ showCreateForm ? 'Cancel' : 'New Config' }}
        </button>
      </div>
    </div>

    <div v-if="showCreateForm" class="card form-card">
      <h3>Create Content Config</h3>
      <form @submit.prevent="createConfig">
        <div class="form-group">
          <label for="name">Name</label>
          <input id="name" v-model="newConfigName" type="text" required placeholder="e.g. homepage-v2" />
        </div>
        <div v-if="createError" class="error-message">{{ createError }}</div>
        <button type="submit" class="btn btn-primary" :disabled="createLoading">
          {{ createLoading ? 'Creating...' : 'Create' }}
        </button>
      </form>
    </div>

    <div v-if="loading" class="loading">Loading content...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="configs.length === 0" class="empty-state">No content configs found.</div>

    <div v-else class="configs-list">
      <div v-for="config in configs" :key="config.id" class="card config-card">
        <div class="config-header" @click="toggleConfig(config.id)">
          <div>
            <h3>{{ config.name }}</h3>
            <span class="badge" :class="'badge-' + config.status">{{ config.status }}</span>
          </div>
          <div class="config-actions">
            <button
              v-if="config.status === 'draft'"
              class="btn btn-small btn-promote"
              @click.stop="promoteStatus(config.id, 'canary')"
            >Promote to Canary</button>
            <button
              v-if="config.status === 'canary'"
              class="btn btn-small btn-promote"
              @click.stop="promoteStatus(config.id, 'published')"
            >Publish</button>
            <button class="btn btn-small btn-secondary" @click.stop="previewConfig(config)">Preview</button>
            <span class="expand-icon">{{ expandedConfig === config.id ? '-' : '+' }}</span>
          </div>
        </div>

        <div v-if="previewMode && expandedConfig === config.id" class="config-preview">
          <div v-for="section in configDetail?.sections || []" :key="section.id" class="preview-section">
            <h4>{{ section.title }} <span class="badge badge-type">{{ section.section_type }}</span></h4>
            <pre class="preview-json">{{ JSON.stringify(section.content_json, null, 2) }}</pre>
          </div>
        </div>

        <div v-if="!previewMode && expandedConfig === config.id" class="sections-panel">
          <h4>Sections</h4>
          <div v-if="sectionsLoading" class="loading">Loading sections...</div>
          <div v-for="section in configDetail?.sections || []" :key="section.id" class="section-item">
            <div class="section-header">
              <strong>{{ section.title }}</strong>
              <span class="badge badge-type">{{ section.section_type }}</span>
              <span class="badge" :class="section.is_active ? 'badge-active' : 'badge-inactive'">
                {{ section.is_active ? 'Active' : 'Inactive' }}
              </span>
              <span class="sort-order">Sort: {{ section.sort_order }}</span>
            </div>
            <pre class="section-json">{{ JSON.stringify(section.content_json, null, 2) }}</pre>
          </div>

          <div class="add-section-form">
            <h5>Add Section</h5>
            <form @submit.prevent="createSection(config.id)">
              <div class="form-group">
                <label>Section Type</label>
                <select v-model="newSection.section_type" required>
                  <option value="carousel">Carousel</option>
                  <option value="recommended_tiles">Recommended Tiles</option>
                  <option value="announcement_banner">Announcement Banner</option>
                </select>
              </div>
              <div class="form-group">
                <label>Title</label>
                <input v-model="newSection.title" type="text" required placeholder="Section title" />
              </div>
              <div class="form-group">
                <label>Content JSON</label>
                <textarea v-model="newSectionJson" rows="4" required placeholder='{"heading": "Welcome", "items": []}'></textarea>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label>Sort Order</label>
                  <input v-model.number="newSection.sort_order" type="number" min="0" />
                </div>
                <div class="form-group">
                  <label><input type="checkbox" v-model="newSection.is_active" /> Active</label>
                </div>
              </div>
              <div v-if="sectionError" class="error-message">{{ sectionError }}</div>
              <button type="submit" class="btn btn-primary btn-small" :disabled="sectionLoading">
                {{ sectionLoading ? 'Adding...' : 'Add Section' }}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>

    <!-- Preview Modal -->
    <div v-if="showPreview" class="preview-overlay" @click.self="showPreview = false">
      <div class="preview-modal">
        <div class="preview-modal-header">
          <h2>Preview: {{ previewTarget?.name }}</h2>
          <button class="btn btn-secondary" @click="showPreview = false">Close</button>
        </div>
        <div class="preview-body">
          <div v-for="section in configDetail?.sections || []" :key="section.id" class="preview-section-block">
            <div v-if="section.section_type === 'announcement_banner'" class="preview-banner">
              <h3>{{ section.title }}</h3>
              <pre>{{ JSON.stringify(section.content_json, null, 2) }}</pre>
            </div>
            <div v-else-if="section.section_type === 'carousel'" class="preview-carousel">
              <h3>{{ section.title }} (Carousel)</h3>
              <pre>{{ JSON.stringify(section.content_json, null, 2) }}</pre>
            </div>
            <div v-else-if="section.section_type === 'recommended_tiles'" class="preview-tiles">
              <h3>{{ section.title }} (Recommended Tiles)</h3>
              <pre>{{ JSON.stringify(section.content_json, null, 2) }}</pre>
            </div>
            <div v-else>
              <h3>{{ section.title }}</h3>
              <pre>{{ JSON.stringify(section.content_json, null, 2) }}</pre>
            </div>
          </div>
          <p v-if="!configDetail?.sections?.length" class="empty-state">No sections to preview.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

interface ContentSection {
  id: string
  section_type: string
  title: string
  content_json: Record<string, unknown>
  sort_order: number
  is_active: boolean
}

interface ContentConfig {
  id: string
  name: string
  status: string
  version?: number
  sections?: ContentSection[]
}

const configs = ref<ContentConfig[]>([])
const configDetail = ref<ContentConfig | null>(null)
const loading = ref(true)
const sectionsLoading = ref(false)
const error = ref('')
const previewMode = ref(false)

const showCreateForm = ref(false)
const newConfigName = ref('')
const createLoading = ref(false)
const createError = ref('')

const expandedConfig = ref<string | null>(null)
const newSection = ref({ section_type: 'carousel', title: '', sort_order: 0, is_active: true })
const newSectionJson = ref('')
const sectionLoading = ref(false)
const sectionError = ref('')

const showPreview = ref(false)
const previewTarget = ref<ContentConfig | null>(null)

onMounted(async () => {
  await fetchConfigs()
})

async function fetchConfigs() {
  try {
    const response = await api.get('/content/configs')
    configs.value = response.data.items || response.data || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load content'
  } finally {
    loading.value = false
  }
}

async function createConfig() {
  createError.value = ''
  createLoading.value = true
  try {
    await api.post('/content/configs', { name: newConfigName.value })
    newConfigName.value = ''
    showCreateForm.value = false
    await fetchConfigs()
  } catch (err: any) {
    createError.value = err.response?.data?.detail || 'Failed to create content config'
  } finally {
    createLoading.value = false
  }
}

async function loadConfigDetail(configId: string) {
  sectionsLoading.value = true
  try {
    const response = await api.get(`/content/configs/${configId}`)
    configDetail.value = response.data
  } catch {
    configDetail.value = null
  } finally {
    sectionsLoading.value = false
  }
}

async function toggleConfig(configId: string) {
  if (expandedConfig.value === configId) {
    expandedConfig.value = null
    configDetail.value = null
    return
  }
  expandedConfig.value = configId
  await loadConfigDetail(configId)
}

async function createSection(configId: string) {
  sectionError.value = ''
  sectionLoading.value = true
  try {
    let contentJson: Record<string, unknown> = {}
    if (newSectionJson.value.trim()) {
      contentJson = JSON.parse(newSectionJson.value)
    }
    await api.post(`/content/configs/${configId}/sections`, {
      section_type: newSection.value.section_type,
      title: newSection.value.title,
      content_json: contentJson,
      sort_order: newSection.value.sort_order,
      is_active: newSection.value.is_active,
    })
    newSection.value = { section_type: 'carousel', title: '', sort_order: 0, is_active: true }
    newSectionJson.value = ''
    await loadConfigDetail(configId)
  } catch (err: any) {
    if (err instanceof SyntaxError) {
      sectionError.value = 'Invalid JSON in content field'
    } else {
      sectionError.value = err.response?.data?.detail || 'Failed to create section'
    }
  } finally {
    sectionLoading.value = false
  }
}

async function promoteStatus(configId: string, newStatus: string) {
  try {
    const config = configs.value.find(c => c.id === configId)
    const version = configDetail.value?.id === configId
      ? (configDetail.value?.version ?? config?.version ?? 0)
      : (config?.version ?? 0)
    await api.put(`/content/configs/${configId}/status`, { status: newStatus }, {
      headers: { 'If-Match': String(version) },
    })
    await fetchConfigs()
  } catch (err: any) {
    alert(err.response?.data?.detail || 'Failed to update status')
  }
}

async function previewConfig(config: ContentConfig) {
  previewTarget.value = config
  await loadConfigDetail(config.id)
  expandedConfig.value = config.id
  showPreview.value = true
}
</script>

<style scoped>
.content-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.form-card { background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
.form-card h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: end; }
.config-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.config-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.config-header h3 { margin: 0 8px 0 0; display: inline; }
.config-actions { display: flex; gap: 8px; align-items: center; }
.expand-icon { font-size: 20px; font-weight: bold; color: #999; }
.config-preview { margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee; }
.sections-panel { margin-top: 16px; padding-top: 16px; border-top: 1px solid #eee; }
.sections-panel h4 { margin: 0 0 12px; }
.section-item { padding: 12px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px; }
.section-header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.section-json, .preview-json { background: #f5f5f5; padding: 8px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin-top: 8px; }
.sort-order { font-size: 12px; color: #888; }
.add-section-form { margin-top: 16px; padding-top: 16px; border-top: 1px dashed #ddd; }
.add-section-form h5 { margin: 0 0 12px; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-type { background: #e3f2fd; color: #1565c0; }
.badge-draft { background: #fff3cd; color: #856404; }
.badge-canary { background: #cce5ff; color: #004085; }
.badge-published { background: #d4edda; color: #155724; }
.badge-active { background: #d4edda; color: #155724; }
.badge-inactive { background: #f8d7da; color: #721c24; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a3c5e; color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small { padding: 6px 12px; font-size: 13px; }
.btn-promote { background: #28a745; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.error-message { color: #dc3545; margin-bottom: 12px; font-size: 14px; }
.loading { text-align: center; padding: 24px; color: #666; }
.empty-state { color: #888; text-align: center; padding: 24px; }

.preview-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.preview-modal {
  background: white; border-radius: 8px; padding: 24px; max-width: 800px; width: 95%;
  max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.preview-modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.preview-modal-header h2 { margin: 0; }
.preview-section-block { margin-bottom: 16px; padding: 12px; background: #f9f9f9; border-radius: 4px; }
.preview-banner { border-left: 4px solid #1a3c5e; padding-left: 12px; }
.preview-carousel { border-left: 4px solid #28a745; padding-left: 12px; }
.preview-tiles { border-left: 4px solid #f0ad4e; padding-left: 12px; }
</style>
