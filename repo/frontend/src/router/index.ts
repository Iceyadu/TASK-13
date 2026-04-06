import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
  { path: '/billing', name: 'Billing', component: () => import('@/views/BillingView.vue') },
  { path: '/orders', name: 'Orders', component: () => import('@/views/OrdersView.vue') },
  { path: '/listings', name: 'Listings', component: () => import('@/views/ListingsView.vue') },
  { path: '/addresses', name: 'Addresses', component: () => import('@/views/AddressesView.vue') },
  { path: '/payments', name: 'Payments', component: () => import('@/views/PaymentView.vue') },
  { path: '/credits', name: 'Credits', component: () => import('@/views/CreditsView.vue') },
  { path: '/admin/users', name: 'Users', component: () => import('@/views/UsersView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/content', name: 'Content', component: () => import('@/views/ContentView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/backup', name: 'Backup', component: () => import('@/views/BackupView.vue'), meta: { roles: ['admin'] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  if (to.meta.public) return next()
  const auth = useAuthStore()
  if (!auth.isAuthenticated) {
    auth.loadFromStorage()
    if (!auth.isAuthenticated) return next('/login')
  }
  const requiredRoles = to.meta.roles as string[] | undefined
  if (requiredRoles && !auth.hasRole(...requiredRoles)) return next('/')
  next()
})

export default router
