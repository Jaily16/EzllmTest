import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { nextTick } from 'vue'
import { routeTitleFor } from '@/config/routePresentation'
import {
  getWorkflowRedirectPath,
  isWorkflowRouteAllowed,
  projectWorkflowStatus,
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
    component: () => import('../views/AboutView.vue')
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
      },
      {
        path: '/agent',
        meta: { requiresAgent: true },
        component: () => import('../components/AgentWorkbench.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to) => {
  if (
    to.meta.requiresAgent &&
    workflowStatusLoaded.value &&
    projectWorkflowStatus.value?.stage === 'setup_required'
  ) {
    return '/create'
  }
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

router.afterEach(async (to) => {
  document.title = `${routeTitleFor(to.path)} | EzllmTest`
  await nextTick()
  const main = document.querySelector<HTMLElement>('main')
  main?.focus({ preventScroll: true })
})

export default router
