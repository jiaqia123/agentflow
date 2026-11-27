import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/request'

/** 视图全部懒加载：首屏只下载登录页需要的代码 */
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { public: true, title: '注册' }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '概览', icon: 'dashboard' }
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('@/views/KnowledgeListView.vue'),
        meta: { title: '知识库', icon: 'database' }
      },
      {
        path: 'knowledge/:id',
        name: 'knowledge-detail',
        component: () => import('@/views/KnowledgeDetailView.vue'),
        props: true,
        // 详情页属于「知识库」这一项，侧栏保持高亮
        meta: { title: '知识库详情', activeMenu: 'knowledge' }
      },
      {
        path: 'documents',
        name: 'documents',
        component: () => import('@/views/DocumentListView.vue'),
        meta: { title: '文档库', icon: 'file' }
      },
      {
        path: 'documents/:id',
        name: 'document-detail',
        component: () => import('@/views/DocumentDetailView.vue'),
        // 详情页属于「文档库」这一项，侧栏保持高亮
        meta: { title: '文档详情', activeMenu: 'documents' }
      },
      {
        path: 'retrieve',
        name: 'retrieve',
        component: () => import('@/views/RetrieveView.vue'),
        meta: { title: '在线检索', icon: 'search' }
      }
    ]
  },
  // 兜底：未知路径一律回首页（未登录时会被守卫再踢到登录页）
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const logged = Boolean(getToken())

  if (!to.meta.public && !logged) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }
  // 已登录还去登录/注册页，直接放行回首页
  if (to.meta.public && logged) {
    return { name: 'dashboard' }
  }
  return true
})

router.afterEach((to) => {
  const base = 'AgentFlow'
  document.title = to.meta.title ? `${to.meta.title} · ${base}` : `${base} · 企业级 AI 知识库平台`
})

export default router
