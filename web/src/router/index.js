import { createRouter, createWebHashHistory } from 'vue-router'
import { userStore } from '@/store/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layout/Index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页概览', icon: 'Odometer' }
      },
      {
        path: 'inventory',
        name: 'inventory',
        component: () => import('@/views/Inventory.vue'),
        meta: { title: '库存管理', icon: 'Box' }
      },
      {
        path: 'orders',
        name: 'orders',
        component: () => import('@/views/OrderList.vue'),
        meta: { title: '出入库单据', icon: 'Tickets' }
      },
      {
        path: 'orders/edit/:id?',
        name: 'order-edit',
        component: () => import('@/views/OrderEdit.vue'),
        meta: { title: '单据编辑', icon: 'EditPen', active: '/orders' }
      },
      {
        path: 'orders/detail/:id',
        name: 'order-detail',
        component: () => import('@/views/OrderDetail.vue'),
        meta: { title: '单据详情', icon: 'View', active: '/orders' }
      },
      {
        path: 'record',
        name: 'record',
        component: () => import('@/views/Record.vue'),
        meta: { title: '出入库流水', icon: 'DataLine' }
      },
      {
        path: 'supplier',
        name: 'supplier',
        component: () => import('@/views/Supplier.vue'),
        meta: { title: '供应商管理', icon: 'OfficeBuilding' }
      },
      {
        path: 'category',
        name: 'category',
        component: () => import('@/views/Category.vue'),
        meta: { title: '分类管理', icon: 'FolderOpened' }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// 全局路由守卫：校验登录态
router.beforeEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 库存管理系统` : '库存管理系统'
  if (!userStore.token && to.name !== 'login') {
    return { name: 'login' }
  }
  if (userStore.token && to.name === 'login') {
    return { name: 'dashboard' }
  }
  return true
})

export default router
