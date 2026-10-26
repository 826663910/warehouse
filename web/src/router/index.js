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
        // 带 id = 编辑，不带 = 新增（与 orders/edit/:id? 同一套约定）
        path: 'inventory/edit/:id?',
        name: 'inventory-edit',
        component: () => import('@/views/InventoryEdit.vue'),
        meta: { title: '物料编辑', icon: 'Box', active: '/inventory' }
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
        path: 'report',
        name: 'report',
        component: () => import('@/views/Report.vue'),
        meta: { title: '出入库报表', icon: 'Histogram' }
      },
      {
        path: 'profit',
        name: 'profit',
        component: () => import('@/views/Profit.vue'),
        meta: { title: '毛利报表', icon: 'DataAnalysis' }
      },
      {
        path: 'supplier',
        name: 'supplier',
        component: () => import('@/views/Supplier.vue'),
        meta: { title: '供应商管理', icon: 'OfficeBuilding' }
      },
      {
        path: 'customer',
        name: 'customer',
        component: () => import('@/views/Customer.vue'),
        meta: { title: '客户管理', icon: 'User' }
      },
      {
        path: 'category',
        name: 'category',
        component: () => import('@/views/Category.vue'),
        meta: { title: '分类管理', icon: 'FolderOpened' }
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/User.vue'),
        // level: 3 = 只有超级管理员可见可进（菜单 + 路由守卫双重拦截）
        meta: { title: '账号管理', icon: 'UserFilled', level: 3 }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// 全局路由守卫：校验登录态 + 页面级权限
router.beforeEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 库存管理系统` : '库存管理系统'
  if (!userStore.token && to.name !== 'login') {
    return { name: 'login' }
  }
  if (userStore.token && to.name === 'login') {
    return { name: 'dashboard' }
  }
  // 页面级权限：meta.level 声明最低级别，低于它直接踢回首页
  if (to.meta?.level && (userStore.level || 0) < to.meta.level) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
