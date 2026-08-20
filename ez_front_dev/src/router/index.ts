import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { analysisReady } from '@/state/projectAnalysis'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/about',
    name: 'about',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import(/* webpackChunkName: "about" */ '../views/AboutView.vue')
  },
  {
    path: '/create',
    name: 'create',
    component: () => import('../views/CreateView.vue')
  },
  {
    path: '/test',
    name: 'testMain',
    redirect: '/plan',
    component: () => import('../views/MainView.vue'),
    children:[
      {
        path: '/menu',
        meta: { requiresAnalysis: true },
        component: () => import('../components/TestMenu.vue')
      },
      {
        path: '/plan',
        component: () => import('../components/TestPlan.vue')
      },
      {
        path: '/unit',
        meta: { requiresAnalysis: true },
        component: () => import('../components/UnitTest.vue')
      },
      {
        path: '/integration',
        meta: { requiresAnalysis: true },
        component: () => import('../components/IntegrationTest.vue')
      },
      {
        path: '/api',
        meta: { requiresAnalysis: true },
        component: () => import('../components/ApiTest.vue')
      },
      {
        path: '/ui',
        meta: { requiresAnalysis: true },
        component: () => import('../components/UITest.vue')
      },
      {
        path: '/database',
        meta: { requiresAnalysis: true },
        component: () => import('../components/DatabaseTest.vue')
      },
      {
        path: '/functional',
        meta: { requiresAnalysis: true },
        component: () => import('../components/FounctionalTest.vue')
      },
      {
        path: '/nfunctional',
        meta: { requiresAnalysis: true },
        component: () => import('../components/NonfunctionalTest.vue')
      },
      {
        path: '/acceptance',
        meta: { requiresAnalysis: true },
        component: () => import('../components/AcceptanceTest.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

router.beforeEach((to) => {
  if (to.meta.requiresAnalysis && !analysisReady.value) return '/plan'
  return true
})

export default router
