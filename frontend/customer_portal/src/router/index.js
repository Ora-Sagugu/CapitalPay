import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layout/DefaultLayout.vue'),
    redirect: '/orders',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'onboarding',
        name: 'onboarding',
        component: () => import('@/views/OnboardingWizard.vue'),
        meta: { title: '资料完善' }
      },
      {
        path: 'remittance',
        name: 'remittance',
        component: () => import('@/views/RemittanceApply.vue'),
        meta: { title: '汇款申请' }
      },
      {
        path: 'orders',
        name: 'orders',
        component: () => import('@/views/Orders.vue'),
        meta: { title: '支付记录' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/orders'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'orders' }
  }
  return true
})

export default router
