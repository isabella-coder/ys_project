<template>
  <div id="app">
    <div class="app-layout">
      <!-- 侧边栏 -->
      <aside class="app-sidebar" :class="{ collapsed: isCollapse }">
        <div class="sidebar-brand">
          <span class="brand-text" v-if="!isCollapse">客资中台</span>
          <span class="brand-icon" v-else>客</span>
        </div>
        <nav class="sidebar-nav">
          <div
            class="nav-item"
            :class="{ active: activeMenu === '/' }"
            @click="goTo('/')"
          >
            <Home :size="18" />
            <span v-if="!isCollapse">首页</span>
          </div>

          <div class="nav-group-label" v-if="!isCollapse">系统管理</div>
          <div class="nav-item" :class="{ active: activeMenu === '/accounts' }" @click="goTo('/accounts')">
            <Users :size="18" />
            <span v-if="!isCollapse">账号管理</span>
          </div>

          <div class="nav-group-label" v-if="!isCollapse">业务中心</div>
          <div class="nav-item" :class="{ active: activeMenu === '/leads' }" @click="goTo('/leads')">
            <FileText :size="18" />
            <span v-if="!isCollapse">线索中心</span>
          </div>
          <div class="nav-item" :class="{ active: activeMenu === '/allocation' }" @click="goTo('/allocation')">
            <GitBranch :size="18" />
            <span v-if="!isCollapse">分配管理</span>
          </div>

          <div class="nav-group-label" v-if="!isCollapse">报表分析</div>
          <div class="nav-item" :class="{ active: activeMenu === '/stats/daily' }" @click="goTo('/stats/daily')">
            <CalendarDays :size="18" />
            <span v-if="!isCollapse">日报</span>
          </div>
          <div class="nav-item" :class="{ active: activeMenu === '/stats/sales' }" @click="goTo('/stats/sales')">
            <TrendingUp :size="18" />
            <span v-if="!isCollapse">销售统计</span>
          </div>
          <div class="nav-item" :class="{ active: activeMenu === '/stats/sla' }" @click="goTo('/stats/sla')">
            <Timer :size="18" />
            <span v-if="!isCollapse">SLA 统计</span>
          </div>
        </nav>
      </aside>

      <!-- 主内容 -->
      <div class="app-content">
        <header class="app-header">
          <button class="toggle-btn" @click="isCollapse = !isCollapse">
            <PanelLeftClose :size="18" v-if="!isCollapse" />
            <PanelLeftOpen :size="18" v-else />
          </button>
          <div class="breadcrumb">
            {{ $route.name || '首页' }}
          </div>
          <div class="user-menu">
            <span class="user-name">Admin</span>
            <el-dropdown @command="handleCommand">
              <span class="user-avatar">
                <UserCircle :size="20" />
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                  <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </header>

        <main class="app-main">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from './stores/app'
import {
  Home, Users, FileText, GitBranch,
  CalendarDays, TrendingUp, Timer,
  PanelLeftClose, PanelLeftOpen, UserCircle
} from 'lucide-vue-next'

const router = useRouter()
const appStore = useAppStore()
const isCollapse = ref(false)
const activeMenu = ref('/')

const goTo = (path) => {
  router.push(path)
  activeMenu.value = path
}

const handleCommand = (command) => {
  if (command === 'logout') {
    appStore.logout()
    activeMenu.value = '/'
    router.push('/')
    ElMessage.success('已退出登录')
  }
}
</script>

<style scoped>
#app {
  width: 100%;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.app-layout {
  display: flex;
  height: 100%;
}

/* ── Sidebar ── */
.app-sidebar {
  width: 220px;
  background: #ffffff;
  border-right: 1px solid #f0f1f3;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: 60px;
}

.sidebar-brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid #f0f1f3;
}

.brand-text {
  font-size: 16px;
  font-weight: 600;
  color: #1a1d21;
  letter-spacing: -0.02em;
}

.brand-icon {
  font-size: 16px;
  font-weight: 600;
  color: #1a1d21;
  margin: 0 auto;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
}

.nav-group-label {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 16px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #6b7280;
  font-size: 14px;
  transition: all 0.15s ease;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: #f8f9fb;
  color: #1a1d21;
}

.nav-item.active {
  background: #1a1d21;
  color: #ffffff;
}

.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

/* ── Header ── */
.app-header {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #f0f1f3;
}

.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.15s ease;
}

.toggle-btn:hover {
  background: #f0f1f3;
  color: #1a1d21;
}

.breadcrumb {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #1a1d21;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-name {
  font-size: 13px;
  color: #6b7280;
}

.user-avatar {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #6b7280;
  transition: color 0.15s ease;
}

.user-avatar:hover {
  color: #1a1d21;
}

/* ── Main ── */
.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f8f9fb;
}
</style>

<!-- Global Element Plus theme overrides -->
<style>
:root {
  --el-color-primary: #1a1d21;
  --el-color-primary-light-3: #4a4d52;
  --el-color-primary-light-5: #6b7280;
  --el-color-primary-light-7: #9ca3af;
  --el-color-primary-light-9: #f0f1f3;
  --el-color-primary-dark-2: #111316;
  --el-border-radius-base: 8px;
  --el-border-radius-small: 6px;
  --el-border-color: #e8eaed;
  --el-border-color-light: #f0f1f3;
  --el-bg-color-page: #f8f9fb;
  --el-text-color-primary: #1a1d21;
  --el-text-color-regular: #3d4148;
  --el-text-color-secondary: #6b7280;
  --el-text-color-placeholder: #9ca3af;
  --el-fill-color: #f0f1f3;
  --el-fill-color-light: #f8f9fb;
  --el-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.el-card {
  border: none !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04) !important;
}

.el-table {
  border-radius: 12px;
  overflow: hidden;
}

.el-table th.el-table__cell {
  background-color: #f8f9fb !important;
  color: #6b7280 !important;
  font-weight: 500;
  font-size: 13px;
}

.el-button--primary {
  --el-button-bg-color: #1a1d21;
  --el-button-border-color: #1a1d21;
  --el-button-hover-bg-color: #3d4148;
  --el-button-hover-border-color: #3d4148;
}

.el-tag {
  border-radius: 6px;
  border: none;
}
</style>
