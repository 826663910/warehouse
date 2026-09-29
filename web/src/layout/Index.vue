<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed }">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="22"><Box /></el-icon>
        </div>
        <transition name="fade">
          <div v-show="!collapsed" class="logo-text">
            <span class="logo-title">云仓系统</span>
            <span class="logo-sub">WAREHOUSE</span>
          </div>
        </transition>
      </div>

      <el-scrollbar class="menu-scroll">
        <el-menu
          :default-active="activeMenu"
          :collapse="collapsed"
          :collapse-transition="false"
          background-color="transparent"
          text-color="#a6b4d0"
          active-text-color="#ffffff"
          @select="handleMenuSelect"
        >
          <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>
      </el-scrollbar>
    </aside>

    <!-- 主区域 -->
    <div class="main">
      <header class="header">
        <div class="header-left">
          <div class="collapse-btn" @click="collapsed = !collapsed">
            <el-icon :size="20">
              <Expand v-if="collapsed" />
              <Fold v-else />
            </el-icon>
          </div>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-dropdown trigger="click" @command="handleCommand">
            <div class="user-chip">
              <el-avatar :size="32" class="user-avatar">{{ avatarText }}</el-avatar>
              <span class="user-name">{{ userStore.username || '未登录' }}</span>
              <el-icon><CaretBottom /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { userStore, clearAuth } from '@/store/user'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

// 侧边菜单 = 除隐藏页外的子路由
const menus = [
  { path: '/dashboard', title: '首页概览', icon: 'Odometer' },
  { path: '/inventory', title: '库存管理', icon: 'Box' },
  { path: '/orders', title: '出入库单据', icon: 'Tickets' },
  { path: '/record', title: '出入库流水', icon: 'DataLine' },
  { path: '/supplier', title: '供应商管理', icon: 'OfficeBuilding' },
  { path: '/category', title: '分类管理', icon: 'FolderOpened' }
]

const activeMenu = computed(() => route.meta.active || route.path)

const currentTitle = computed(() => {
  if (route.name === 'order-edit') {
    return route.params.id ? '编辑单据' : '新建单据'
  }
  return route.meta?.title || ''
})

const avatarText = computed(() => (userStore.username || 'U').slice(0, 1).toUpperCase())

function handleMenuSelect(index) {
  if (index !== route.path) router.push(index)
}

async function handleCommand(cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        type: 'warning',
        confirmButtonText: '退出',
        cancelButtonText: '取消'
      })
      clearAuth()
      router.push('/login')
    } catch (e) {
      /* 取消 */
    }
  }
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: var(--app-sidebar-width);
  background: linear-gradient(180deg, #101c38 0%, #0d1730 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.25s;
  flex-shrink: 0;
}
.sidebar.collapsed {
  width: 64px;
}
.logo {
  height: var(--app-header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.logo-icon {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 10px;
  background: linear-gradient(135deg, #2f6bff, #53a0ff);
  box-shadow: 0 4px 12px rgba(47, 107, 255, 0.45);
}
.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  white-space: nowrap;
}
.logo-title {
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
}
.logo-sub {
  font-size: 10px;
  color: #5e7199;
  letter-spacing: 3px;
}
.menu-scroll {
  flex: 1;
}
.sidebar :deep(.el-menu) {
  border-right: none;
  padding: 10px 8px;
}
.sidebar :deep(.el-menu-item) {
  height: 46px;
  border-radius: 8px;
  margin-bottom: 4px;
}
.sidebar :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
}
.sidebar :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #2f6bff, #3d7dff);
  box-shadow: 0 6px 16px rgba(47, 107, 255, 0.4);
}
.sidebar :deep(.el-menu--collapse .el-menu-item) {
  padding: 0 18px;
  justify-content: center;
}

/* ===== 主区域 ===== */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.header {
  height: var(--app-header-height);
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.collapse-btn {
  cursor: pointer;
  color: #5a6478;
  display: flex;
  align-items: center;
  transition: color 0.2s;
}
.collapse-btn:hover {
  color: var(--el-color-primary);
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;
}
.user-chip:hover {
  background: #f2f5fa;
}
.user-avatar {
  background: linear-gradient(135deg, #2f6bff, #53a0ff);
  font-size: 14px;
  font-weight: 600;
}
.user-name {
  font-size: 14px;
  color: #2a3348;
}
.content {
  flex: 1;
  overflow: auto;
}

/* 转场动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.18s, transform 0.18s;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-slide-leave-to {
  opacity: 0;
}
</style>
