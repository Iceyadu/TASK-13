<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

interface MenuItem {
  label: string
  route: string
  roles: string[]
}

const menuItems: MenuItem[] = [
  { label: 'Dashboard', route: '/', roles: ['admin', 'property_manager', 'accounting_clerk', 'maintenance_dispatcher', 'resident'] },
  { label: 'Billing', route: '/billing', roles: ['admin', 'property_manager', 'accounting_clerk', 'resident'] },
  { label: 'Orders', route: '/orders', roles: ['admin', 'property_manager', 'maintenance_dispatcher', 'resident'] },
  { label: 'Listings', route: '/listings', roles: ['admin', 'property_manager', 'accounting_clerk', 'maintenance_dispatcher', 'resident'] },
  { label: 'Addresses', route: '/addresses', roles: ['resident'] },
  { label: 'Payments', route: '/payments', roles: ['resident'] },
  { label: 'Credits', route: '/credits', roles: ['resident', 'accounting_clerk'] },
  { label: 'Users', route: '/admin/users', roles: ['admin'] },
  { label: 'Content', route: '/admin/content', roles: ['admin'] },
  { label: 'Backups', route: '/admin/backup', roles: ['admin'] },
]

const visibleItems = computed(() =>
  menuItems.filter((item) => auth.user && item.roles.includes(auth.user.role))
)
</script>

<template>
  <aside class="sidebar">
    <nav class="sidebar-nav">
      <router-link
        v-for="item in visibleItems"
        :key="item.route"
        :to="item.route"
        class="sidebar-link"
        active-class="sidebar-link-active"
      >
        {{ item.label }}
      </router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  background: #f8f9fa;
  border-right: 1px solid #e9ecef;
  min-height: calc(100vh - 56px);
  padding: 16px 0;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
}

.sidebar-link {
  padding: 10px 24px;
  color: #495057;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
  border-left: 3px solid transparent;
}

.sidebar-link:hover {
  background: #e9ecef;
  color: #1a3c5e;
}

.sidebar-link-active {
  background: #eaf2f8;
  color: #1a3c5e;
  font-weight: 600;
  border-left-color: #1a3c5e;
}
</style>
