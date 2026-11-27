<script setup>
/**
 * 登录页 —— 未登录时的第一屏。
 * 左侧品牌区 + 右侧表单；<960px 时品牌区收成顶部小条。
 *
 * 出错只高亮、绝不清空输入（用户刚敲完的账号密码不该因为一次手滑白费）。
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const route = useRoute()
const { login } = useAuth()

const formRef = ref(null)
const loading = ref(false)
const serverError = ref('')

const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const HIGHLIGHTS = [
  { icon: 'upload', title: '上传即入库', desc: 'PDF / Word / Excel / Markdown 自动切分、向量化' },
  { icon: 'layers', title: '一库一集合', desc: '每个知识库独立向量集合，检索互不污染' },
  { icon: 'brain', title: '混合召回', desc: '向量 + BM25 融合，重排压缩后合成答案' }
]

async function submit() {
  if (!formRef.value) return

  // 先过前端校验，不通过就不发请求
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  loading.value = true
  serverError.value = ''
  try {
    await login({ username: form.username.trim(), password: form.password })
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (err) {
    // 错误只提示，不清空表单
    serverError.value = err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth">
    <!-- 品牌区 -->
    <section class="auth__brand">
      <div class="brand__inner">
        <div class="brand__logo">
          <span class="brand__mark" aria-hidden="true"><AppIcon name="sparkles" :size="22" /></span>
          <b>AgentFlow</b>
        </div>

        <h2 class="brand__slogan">
          把散落的文档，<br />
          变成<span>能答问题</span>的知识库
        </h2>
        <p class="brand__sub">
          企业级 AI 知识库开发平台 · 上传、切分、向量化、检索一站式完成
        </p>

        <ul class="brand__list">
          <li v-for="item in HIGHLIGHTS" :key="item.title">
            <span class="brand__ico" aria-hidden="true"><AppIcon :name="item.icon" :size="16" /></span>
            <span class="brand__txt">
              <b>{{ item.title }}</b>
              <i>{{ item.desc }}</i>
            </span>
          </li>
        </ul>
      </div>
      <div class="brand__glow" aria-hidden="true"></div>
    </section>

    <!-- 表单区 -->
    <section class="auth__panel">
      <div class="panel__box">
        <header class="panel__head">
          <h1>欢迎回来</h1>
          <p>登录后即可管理你的知识库与文档</p>
        </header>

        <el-alert
          v-if="serverError"
          :title="serverError"
          type="error"
          :closable="true"
          show-icon
          class="panel__alert"
          @close="serverError = ''"
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              autocomplete="username"
              :disabled="loading"
            >
              <template #prefix><AppIcon name="user" :size="16" /></template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              :disabled="loading"
              @keyup.enter="submit"
            >
              <template #prefix><AppIcon name="lock" :size="16" /></template>
            </el-input>
          </el-form-item>

          <el-button
            type="primary"
            class="panel__submit"
            size="large"
            :loading="loading"
            native-type="submit"
          >
            {{ loading ? '正在登录…' : '登 录' }}
          </el-button>
        </el-form>

        <p class="panel__foot">
          还没有账号？
          <router-link to="/register">立即注册</router-link>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  height: 100%;
  min-height: 100%;
}

/* ------------------------------------------------------- 品牌区 */
.auth__brand {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  padding: 48px 56px;
  background: linear-gradient(158deg, #16142f 0%, #231d51 48%, #342a6e 100%);
  color: #fff;
}
.brand__inner {
  position: relative;
  z-index: 1;
  max-width: 460px;
}
.brand__glow {
  position: absolute;
  inset: auto -20% -30% -10%;
  height: 460px;
  background: radial-gradient(closest-side, rgba(124, 116, 235, 0.5), transparent 72%);
  animation: brand-pulse 8s ease-in-out infinite;
}
@keyframes brand-pulse {
  0%,
  100% {
    opacity: 0.5;
    transform: translate3d(0, 8px, 0) scale(1);
  }
  50% {
    opacity: 0.9;
    transform: translate3d(0, -10px, 0) scale(1.06);
  }
}

.brand__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 34px;
}
.brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #a78bfa 55%, #38bdf8);
  box-shadow: 0 10px 26px -8px rgba(109, 99, 240, 0.95);
}
.brand__logo b {
  font-size: 17px;
  letter-spacing: -0.01em;
}

.brand__slogan {
  margin: 0 0 14px;
  font-size: 34px;
  line-height: 1.28;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.brand__slogan span {
  background: linear-gradient(96deg, #a89fff, #6ee7f0);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.brand__sub {
  margin: 0 0 32px;
  font-size: 13.5px;
  line-height: 1.75;
  color: #b3aedb;
  max-width: 380px;
}

.brand__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.brand__list li {
  display: flex;
  gap: 11px;
  align-items: flex-start;
}
.brand__ico {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #c4bcff;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.brand__txt {
  display: flex;
  flex-direction: column;
  line-height: 1.5;
}
.brand__txt b {
  font-size: 13.5px;
  font-weight: 600;
}
.brand__txt i {
  font-style: normal;
  font-size: 12.5px;
  color: #9d97c9;
}

/* ------------------------------------------------------- 表单区 */
.auth__panel {
  display: grid;
  place-items: center;
  padding: 40px 24px;
  background:
    radial-gradient(620px 380px at 88% 4%, #e9e6fd 0%, transparent 60%),
    linear-gradient(180deg, #fbfaff, #f4f3fa);
}
.panel__box {
  width: 100%;
  max-width: 372px;
}
.panel__head {
  margin-bottom: 26px;
}
.panel__head h1 {
  margin: 0 0 6px;
  font-size: 25px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.panel__head p {
  margin: 0;
  font-size: 13px;
  color: var(--af-ink-3);
}
.panel__alert {
  margin-bottom: 16px;
  border-radius: var(--af-radius);
}
.panel__submit {
  width: 100%;
  margin-top: 6px;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.panel__foot {
  margin: 20px 0 0;
  text-align: center;
  font-size: 13px;
  color: var(--af-ink-3);
}
.panel__foot a {
  font-weight: 600;
}

/* ------------------------------------------------------- 响应式 */
@media (max-width: 960px) {
  .auth {
    grid-template-columns: 1fr;
    height: auto;
  }
  .auth__brand {
    padding: 26px 24px 30px;
    align-items: flex-start;
  }
  .brand__inner {
    max-width: none;
  }
  .brand__logo {
    margin-bottom: 18px;
  }
  .brand__slogan {
    font-size: 23px;
  }
  .brand__sub {
    margin-bottom: 20px;
  }
  .brand__list {
    display: none; /* 小屏优先把屏幕留给表单 */
  }
  .auth__panel {
    padding: 30px 20px 44px;
  }
}
</style>
