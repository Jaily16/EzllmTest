import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import {
  getWorkflowRedirectPath,
  isWorkflowRouteAllowed,
  setWorkflowRedirectMessage,
  workflowStatusLoaded,
} from '@/state/projectAnalysis'

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
        meta: { requiresWorkflow: true },
        component: () => import('../components/TestMenu.vue')
      },
      {
        path: '/plan',
        meta: { requiresWorkflow: true },
        component: () => import('../components/TestPlan.vue')
      },
      {
        path: '/unit',
        meta: { requiresWorkflow: true },
        component: () => import('../components/UnitTest.vue')
      },
      {
        path: '/integration',
        meta: { requiresWorkflow: true },
        component: () => import('../components/IntegrationTest.vue')
      },
      {
        path: '/api',
        meta: { requiresWorkflow: true },
        component: () => import('../components/ApiTest.vue')
      },
      {
        path: '/ui',
        meta: { requiresWorkflow: true },
        component: () => import('../components/UITest.vue')
      },
      {
        path: '/database',
        meta: { requiresWorkflow: true },
        component: () => import('../components/DatabaseTest.vue')
      },
      {
        path: '/functional',
        meta: { requiresWorkflow: true },
        component: () => import('../components/FounctionalTest.vue')
      },
      {
        path: '/nfunctional',
        meta: { requiresWorkflow: true },
        component: () => import('../components/NonfunctionalTest.vue')
      },
      {
        path: '/acceptance',
        meta: { requiresWorkflow: true },
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
  if (
    to.meta.requiresWorkflow &&
    workflowStatusLoaded.value &&
    !isWorkflowRouteAllowed(to.path)
  ) {
    setWorkflowRedirectMessage(to.path)
    const redirect = getWorkflowRedirectPath()
    if (redirect !== to.path) return redirect
  }
  return true
})

export default router
