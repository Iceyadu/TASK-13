<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSyncManager } from '@/services/syncManager'

const router = useRouter()
const auth = useAuthStore()
const { isOnline } = useSyncManager()

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <div class="navbar-left">
        <router-link to="/" class="navbar-brand">HarborView</router-link>

        <div class="nav-links">
          <router-link to="/" class="nav-link">Dashboard</router-link>
          <router-link to="/billing" class="nav-link">Billing</router-link>
          <router-link to="/orders" class="nav-link">Orders</router-link>
          <router-link to="/listings" class="nav-link">Listings</router-link>

          <template v-if="auth.hasRole('admin')">
            <router-link to="/admin/users" class="nav-link">Users</router-link>
            <router-link to="/admin/content" class="nav-link">Content</router-link>
            <router-link to="/admin/backup" class="nav-link">Backups</router-link>
          </template>
        </div>
      </div>

      <div class="navbar-right">
        <div class="status-indicator" :class="isOnline ? 'online' : 'offline'">
          <span class="status-dot"></span>
          {{ isOnline ? 'Online' : 'Offline' }}
        </div>

        <span class="username">{{ auth.user?.username }}</span>

        <button class="btn btn-secondary btn-logout" @click="handleLogout">Logout</button>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  background: #1a3c5e;
  color: #fff;
  padding: 0 24px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.navbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.navbar-brand {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  text-decoration: none;
}

.nav-links {
  display: flex;
  gap: 4px;
}

.nav-link {
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.nav-link.router-link-active,
.nav-link.router-link-exact-active {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.online .status-dot {
  background: #4caf50;
}

.offline .status-dot {
  background: #f44336;
}

.username {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.btn-logout {
  padding: 4px 12px;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
}

.btn-logout:hover {
  background: rgba(255, 255, 255, 0.25);
}
</style>
