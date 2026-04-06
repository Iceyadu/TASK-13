<template>
  <div class="dashboard">
    <h1>Welcome, {{ auth.user?.username }}</h1>
    <p class="role-badge">{{ roleLabel }}</p>
    <!-- Homepage Content (from active config) -->
    <div v-if="contentSections.length > 0" class="homepage-content">
      <div v-for="section in contentSections" :key="section.id" class="content-section">
        <!-- Announcement Banner -->
        <div v-if="section.section_type === 'announcement_banner'"
             :class="['announcement-banner', 'banner-' + (section.content_json.severity || 'info')]">
          <p>{{ section.content_json.text }}</p>
        </div>
        <!-- Carousel -->
        <div v-if="section.section_type === 'carousel'" class="carousel-section">
          <div v-for="(panel, idx) in (section.content_json.panels || [])" :key="idx" class="carousel-panel">
            <h3>{{ panel.title }}</h3>
            <p>{{ panel.subtitle }}</p>
          </div>
        </div>
        <!-- Recommended Tiles -->
        <div v-if="section.section_type === 'recommended_tiles'" class="tiles-section">
          <div v-for="(tile, idx) in (section.content_json.tiles || [])" :key="idx" class="rec-tile">
            <h4>{{ tile.title }}</h4>
            <p>{{ tile.description }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="card-grid">
      <router-link v-if="auth.hasRole('resident')" to="/billing" class="dash-card">
        <h3>My Bills</h3><p>View statements and make payments</p>
      </router-link>
      <router-link v-if="auth.hasRole('resident')" to="/orders" class="dash-card">
        <h3>Service Orders</h3><p>Submit and track maintenance requests</p>
      </router-link>
      <router-link v-if="auth.hasRole('resident')" to="/addresses" class="dash-card">
        <h3>Addresses</h3><p>Manage your shipping and mailing addresses</p>
      </router-link>
      <router-link v-if="auth.hasRole('resident')" to="/payments" class="dash-card">
        <h3>Payments</h3><p>Submit payment evidence and view history</p>
      </router-link>
      <router-link v-if="auth.hasRole('resident', 'accounting_clerk')" to="/credits" class="dash-card">
        <h3>Credits</h3><p>Request refunds and view credit memos</p>
      </router-link>
      <router-link to="/listings" class="dash-card">
        <h3>Listings</h3><p>Browse community marketplace</p>
      </router-link>
      <router-link v-if="auth.hasRole('admin','property_manager','accounting_clerk')" to="/billing" class="dash-card">
        <h3>Billing</h3><p>Manage billing and reconciliation</p>
      </router-link>
      <router-link v-if="auth.hasRole('admin','property_manager','maintenance_dispatcher')" to="/orders" class="dash-card">
        <h3>Orders</h3><p>Manage service orders</p>
      </router-link>
      <router-link v-if="auth.hasRole('admin')" to="/admin/users" class="dash-card">
        <h3>Users</h3><p>Manage user accounts</p>
      </router-link>
      <router-link v-if="auth.hasRole('admin')" to="/admin/content" class="dash-card">
        <h3>Content</h3><p>Configure homepage content</p>
      </router-link>
      <router-link v-if="auth.hasRole('admin')" to="/admin/backup" class="dash-card">
        <h3>Backup</h3><p>Backup and restore</p>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
const auth = useAuthStore()

const contentSections = ref<any[]>([])

onMounted(async () => {
  try {
    const resp = await api.get('/content/configs/active')
    contentSections.value = resp.data.sections || []
  } catch {
    // No active content config — that's fine
  }
})
const roleLabel = computed(() => {
  const roles: Record<string, string> = {
    admin: 'Administrator', property_manager: 'Property Manager',
    accounting_clerk: 'Accounting Clerk', maintenance_dispatcher: 'Maintenance / Dispatcher',
    resident: 'Resident',
  }
  return roles[auth.user?.role || ''] || auth.user?.role || ''
})
</script>

<style scoped>
.dashboard { padding: 24px; }
.role-badge { display: inline-block; background: #e8f5e9; color: #2e7d32; padding: 4px 12px; border-radius: 12px; font-size: 13px; margin-bottom: 24px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.dash-card { display: block; background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; text-decoration: none; color: #333; transition: box-shadow 0.2s; }
.dash-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
.dash-card h3 { color: #1a3c5e; margin: 0 0 8px; }
.dash-card p { color: #666; font-size: 13px; margin: 0; }

.homepage-content { margin-bottom: 24px; }
.content-section { margin-bottom: 16px; }
.announcement-banner { padding: 12px 16px; border-radius: 6px; font-weight: 500; }
.banner-info { background: #cce5ff; color: #004085; }
.banner-warning { background: #fff3cd; color: #856404; }
.banner-error { background: #f8d7da; color: #721c24; }
.banner-success { background: #d4edda; color: #155724; }
.announcement-banner p { margin: 0; }
.carousel-section { display: flex; gap: 16px; overflow-x: auto; padding: 8px 0; }
.carousel-panel { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; min-width: 220px; flex-shrink: 0; }
.carousel-panel h3 { color: #1a3c5e; margin: 0 0 8px; }
.carousel-panel p { color: #666; margin: 0; font-size: 13px; }
.tiles-section { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.rec-tile { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }
.rec-tile h4 { color: #1a3c5e; margin: 0 0 6px; }
.rec-tile p { color: #666; font-size: 13px; margin: 0; }
</style>
