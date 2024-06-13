import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

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
    redirect: '/menu',
    component: () => import('../views/MainView.vue'),
    children:[
      {
        path: '/menu',
        component: () => import('../components/TestMenu.vue')
      },
      {
        path: '/plan',
        component: () => import('../components/TestPlan.vue')
      },
      {
        path: '/unit',
        component: () => import('../components/UnitTest.vue')
      },
      {
        path: '/integration',
        component: () => import('../components/IntegrationTest.vue')
      },
      {
        path: '/api',
        component: () => import('../components/ApiTest.vue')
      },
      {
        path: '/ui',
        component: () => import('../components/UITest.vue')
      },
      {
        path: '/database',
        component: () => import('../components/DatabaseTest.vue')
      },
      {
        path: '/functional',
        component: () => import('../components/FounctionalTest.vue')
      },
      {
        path: '/nfunctional',
        component: () => import('../components/NonfunctionalTest.vue')
      },
      {
        path: '/acceptance',
        component: () => import('../components/AcceptanceTest.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router
