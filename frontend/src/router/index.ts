import { createRouter, createWebHistory } from 'vue-router'

import { fetchAdminMe } from '@/api/admin'
import { getStoredAccessToken } from '@/api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/chat',
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
    },
    {
      path: '/admin',
      component: () => import('@/views/admin/AdminLayout.vue'),
      redirect: '/admin/dashboard',
      meta: { requiresAdmin: true },
      children: [
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: () => import('@/views/admin/AdminDashboardView.vue'),
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('@/views/admin/AdminUsersView.vue'),
        },
        {
          path: 'roles',
          name: 'admin-roles',
          component: () => import('@/views/admin/AdminRolesView.vue'),
        },
        {
          path: 'knowledge/documents',
          name: 'admin-knowledge-documents',
          component: () => import('@/views/admin/AdminKnowledgeDocumentsView.vue'),
        },
        {
          path: 'knowledge/jobs',
          name: 'admin-knowledge-jobs',
          component: () => import('@/views/admin/AdminKnowledgeJobsView.vue'),
        },
        {
          path: 'audit',
          name: 'admin-audit',
          component: () => import('@/views/admin/AdminAuditView.vue'),
        },
        {
          path: 'safety',
          name: 'admin-safety',
          component: () => import('@/views/admin/AdminSafetyView.vue'),
        },
        {
          path: 'system',
          name: 'admin-system',
          component: () => import('@/views/admin/AdminSystemView.vue'),
        },
      ],
    },
    {
      path: '/admin/forbidden',
      name: 'admin-forbidden',
      component: () => import('@/views/admin/AdminForbiddenView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/chat',
    },
  ],
})

router.beforeEach(async (to) => {
  if (!to.matched.some((record) => record.meta.requiresAdmin)) {
    return true
  }
  if (!getStoredAccessToken()) {
    return '/chat'
  }
  try {
    const result = await fetchAdminMe()
    return result.permissions.includes('admin:access') ? true : '/admin/forbidden'
  } catch {
    return '/admin/forbidden'
  }
})

export default router
