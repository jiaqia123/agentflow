<script setup>
/**
 * 应用外壳：左侧栏 + 顶栏 + 内容区。
 *
 * 响应式：≥900px 侧栏常驻；<900px 收进抽屉，顶栏出现菜单按钮。
 * 焦点：抽屉里第一个链接自动获得焦点，Esc 关闭（el-drawer 自带）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import { useAuth } from '@/composables/useAuth'

const route = useRoute()
const router = useRouter()
const { state, displayName, initial, logout } = useAuth()

const drawerOpen = ref(false)

const NAV = [
  { name: 'dashboard', to: '/', label: '概览', icon: 'dashboard' },
  { name: 'knowledge', to: '/knowledge', label: '知识库', icon: 'database' },
  { name: 'documents', to: '/documents', label: '文档库', icon: 'file' },
  { name: 'retrieve', to: '/retrieve', label: '在线检索', icon: 'search' }
]

/** 详情页等子路由通过 meta.activeMenu 指回父级菜单 */
const activeName = computed(() => route.meta.activeMenu || route.name)

const pageTitle = computed(() => route.meta.title || '概览')

// 路由变化时收起抽屉，否则移动端点完菜单抽屉还盖着
watch(
  () => route.fullPath,
  () => {
    drawerOpen.value = false
  }
)

async function handleLogout() {
  try {
    await ElMessageBox.confirm('退出后需要重新登录才能继续管理知识库。', '确认退出登录？', {
      confirmButtonText: '退出登录',
      cancelButtonText: '再想想',
      type: 'warning',
      customClass: 'af-confirm'
    })
  } catch {
    return // 用户点了取消
  }
  logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <!-- ============ 侧栏（桌面常驻） ============ -->
    <aside class="nav" aria-label="主导航">
      <div class="nav__brand">
        <span class="brand__mark" aria-hidden="true">
          <AppIcon name="sparkles" :size="17" />
        </span>
        <span class="brand__text">
          <b>AgentFlow</b>
          <i>企业级 AI 知识库平台</i>
        </span>
      </div>

      <nav class="nav__list">
        <router-link
          v-for="item in NAV"
          :key="item.name"
          :to="item.to"
          class="nav__item"
          :class="{ 'is-active': activeName === item.name }"
        >
          <AppIcon :name="item.icon" :size="17" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="nav__foot">
        <div class="nav__user">
          <span class="avatar" aria-hidden="true">{{ initial }}</span>
          <span class="nav__user-meta">
            <b :title="displayName">{{ displayName }}</b>
            <i>{{ state.user?.email || '未绑定邮箱' }}</i>
          </span>
        </div>
        <button class="nav__logout" type="button" @click="handleLogout">
          <AppIcon name="logout" :size="16" />
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <!-- ============ 主区 ============ -->
    <div class="main">
      <header class="topbar">
        <button
          class="topbar__burger"
          type="button"
          aria-label="打开导航菜单"
          @click="drawerOpen = true"
        >
          <span></span><span></span><span></span>
        </button>

        <h1 class="topbar__title">{{ pageTitle }}</h1>

        <div class="topbar__right">
          <span class="pill" title="后端服务地址">
            <em aria-hidden="true"></em>
            127.0.0.1:8000
          </span>
          <span class="topbar__user" :title="displayName">
            <span class="avatar avatar--sm" aria-hidden="true">{{ initial }}</span>
            <b>{{ displayName }}</b>
          </span>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </main>
    </div>

    <!-- ============ 移动端抽屉 ============ -->
    <el-drawer
      v-model="drawerOpen"
      direction="ltr"
      size="248px"
      :with-header="false"
      class="nav-drawer"
    >
      <div class="nav nav--drawer">
        <div class="nav__brand">
          <span class="brand__mark" aria-hidden="true">
            <AppIcon name="sparkles" :size="17" />
          </span>
          <span class="brand__text">
            <b>AgentFlow</b>
            <i>企业级 AI 知识库平台</i>
          </span>
        </div>

        <nav class="nav__list">
          <router-link
            v-for="item in NAV"
            :key="item.name"
            :to="item.to"
            class="nav__item"
            :class="{ 'is-active': activeName === item.name }"
          >
            <AppIcon :name="item.icon" :size="17" />
            <span>{{ item.label }}</span>
          </router-link>
        </nav>

        <div class="nav__foot">
          <button class="nav__logout" type="button" @click="handleLogout">
            <AppIcon name="logout" :size="16" />
            <span>退出登录</span>
          </button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100%;
  background:
    radial-gradient(900px 480px at 12% -6%, #eae7fd 0%, transparent 60%),
    radial-gradient(700px 420px at 100% 0%, #e6f2fb 0%, transparent 55%),
    var(--af-bg);
}

/* ------------------------------------------------------------- 侧栏 */
.nav {
  width: var(--af-nav-width);
  flex: none;
  display: flex;
  flex-direction: column;
  padding: 16px 12px 12px;
  background: linear-gradient(168deg, var(--af-nav-1) 0%, var(--af-nav-2) 62%, #2d2560 100%);
  color: #cfcbe6;
  position: relative;
  overflow: hidden;
}
/* 记忆点：侧栏底部一条会呼吸的渐变光带 */
.nav::after {
  content: '';
  position: absolute;
  inset: auto -40% -60px -40%;
  height: 220px;
  background: radial-gradient(closest-side, rgba(124, 116, 235, 0.55), transparent 70%);
  pointer-events: none;
  animation: af-glow 7s ease-in-out infinite;
}
@keyframes af-glow {
  0%,
  100% {
    opacity: 0.55;
    transform: translateY(6px);
  }
  50% {
    opacity: 0.95;
    transform: translateY(-6px);
  }
}

.nav__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 18px;
  position: relative;
  z-index: 1;
}
.brand__mark {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #a78bfa 60%, #38bdf8);
  box-shadow: 0 6px 18px -6px rgba(109, 99, 240, 0.9);
}
.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
}
.brand__text b {
  color: #fff;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.brand__text i {
  font-style: normal;
  font-size: 11px;
  color: #9c97c4;
  white-space: nowrap;
}

.nav__list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  position: relative;
  z-index: 1;
}
.nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 9px;
  color: #b9b4d6;
  font-size: 13.5px;
  font-weight: 500;
  transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}
.nav__item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}
.nav__item.is-active {
  background: linear-gradient(96deg, rgba(109, 99, 240, 0.34), rgba(109, 99, 240, 0.1));
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(147, 138, 255, 0.36);
}
.nav__item.is-active svg {
  color: #a89fff;
}

.nav__foot {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
  position: relative;
  z-index: 1;
}
.nav__user {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  min-width: 0;
}
.avatar {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #38bdf8);
}
.avatar--sm {
  width: 24px;
  height: 24px;
  font-size: 11px;
}
.nav__user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.3;
}
.nav__user-meta b {
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav__user-meta i {
  font-style: normal;
  font-size: 11px;
  color: #9c97c4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav__logout {
  width: 100%;
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  min-height: 36px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 9px;
  background: transparent;
  color: #cfcbe6;
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.nav__logout:hover {
  background: rgba(229, 72, 77, 0.16);
  border-color: rgba(229, 72, 77, 0.5);
  color: #ffb4b6;
}

/* ------------------------------------------------------------- 主区 */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: var(--af-header-height);
  flex: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--af-line);
  position: sticky;
  top: 0;
  z-index: 20;
}
.topbar__burger {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 40px;
  height: 40px;
  padding: 0 9px;
  border: 1px solid var(--af-line);
  border-radius: 9px;
  background: #fff;
  cursor: pointer;
}
.topbar__burger span {
  display: block;
  height: 1.6px;
  border-radius: 2px;
  background: var(--af-ink-2);
}
.topbar__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.topbar__right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f2fa;
  border: 1px solid var(--af-line);
  font-size: 12px;
  color: var(--af-ink-3);
  font-family: var(--af-font-mono);
}
.pill em {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--af-success);
  box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.16);
}
.topbar__user {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--af-ink-2);
  max-width: 180px;
}
.topbar__user b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

/* 抽屉里的侧栏：撑满、去掉圆角背景 */
.nav--drawer {
  width: 100%;
  height: 100%;
  background: linear-gradient(168deg, var(--af-nav-1) 0%, var(--af-nav-2) 70%);
}

@media (max-width: 900px) {
  .nav:not(.nav--drawer) {
    display: none;
  }
  .topbar__burger {
    display: flex;
  }
  .topbar {
    padding: 0 14px;
  }
  .pill {
    display: none;
  }
  .topbar__user b {
    display: none;
  }
}
</style>

<style>
/* 抽屉内容默认有 padding，这里清掉让侧栏铺满 */
.nav-drawer .el-drawer__body {
  padding: 0;
}
.af-confirm {
  border-radius: var(--af-radius-lg);
}
</style>
