<script setup>
/**
 * 注册页。
 * 前端校验与后端 schemas/auth.py 的 UserRegister 严格对齐：
 *   username 3~64 字符、password ≥6 且 UTF-8 ≤72 字节（bcrypt 上限）、email 可选。
 * 注册成功后端直接返回 token，所以这里直接当作登录态用，不再跳登录页。
 */
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { register } = useAuth()

const formRef = ref(null)
const loading = ref(false)
const serverError = ref('')

const form = reactive({ username: '', password: '', confirm: '', email: '' })

const byteLength = (s) => new TextEncoder().encode(s || '').length

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '长度 3 ~ 64 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        // 后端 bcrypt 只吃前 72 字节，超了会静默丢字符，这里先拦一道
        if (byteLength(value) > 72) callback(new Error('密码过长（UTF-8 编码后不能超过 72 字节）'))
        else callback()
      },
      trigger: 'blur'
    }
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

/** 密码强度：只做「长度 + 字符种类」的粗判断，够用就行 */
const strength = computed(() => {
  const p = form.password
  if (!p) return { level: 0, text: '', color: 'transparent' }
  let score = 0
  if (p.length >= 6) score += 1
  if (p.length >= 10) score += 1
  if (/[a-z]/.test(p) && /[A-Z]/.test(p)) score += 1
  if (/\d/.test(p)) score += 1
  if (/[^\w\s]/.test(p)) score += 1
  if (score <= 1) return { level: 1, text: '偏弱', color: 'var(--af-danger)' }
  if (score <= 3) return { level: 2, text: '一般', color: 'var(--af-warning)' }
  return { level: 3, text: '较强', color: 'var(--af-success)' }
})

async function submit() {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  loading.value = true
  serverError.value = ''
  try {
    await register({
      username: form.username.trim(),
      password: form.password,
      email: form.email.trim()
    })
    ElMessage.success('注册成功，已自动登录')
    router.replace('/')
  } catch (err) {
    serverError.value = err.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth">
    <section class="auth__brand">
      <div class="brand__inner">
        <div class="brand__logo">
          <span class="brand__mark" aria-hidden="true"><AppIcon name="sparkles" :size="22" /></span>
          <b>AgentFlow</b>
        </div>

        <h2 class="brand__slogan">
          三步搭好<br />
          你的<span>专属知识库</span>
        </h2>
        <p class="brand__sub">注册即可创建知识库，上传文档后立刻可以对话式检索</p>

        <ol class="steps">
          <li><em>1</em><span><b>上传文档</b><i>PDF / Word / Excel / Markdown</i></span></li>
          <li><em>2</em><span><b>切分预览</b><i>按 token 切块，可调块长与重叠</i></span></li>
          <li><em>3</em><span><b>向量入库</b><i>写入 MySQL 与该库专属 Chroma 集合</i></span></li>
        </ol>
      </div>
      <div class="brand__glow" aria-hidden="true"></div>
    </section>

    <section class="auth__panel">
      <div class="panel__box">
        <header class="panel__head">
          <h1>创建账号</h1>
          <p>只需要用户名和密码，邮箱可以留空</p>
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
              placeholder="3 ~ 64 个字符"
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
              placeholder="至少 6 位"
              autocomplete="new-password"
              show-password
              :disabled="loading"
            >
              <template #prefix><AppIcon name="lock" :size="16" /></template>
            </el-input>
            <div v-if="form.password" class="strength">
              <span class="strength__bars">
                <i
                  v-for="i in 3"
                  :key="i"
                  :style="{ background: i <= strength.level ? strength.color : 'var(--af-line)' }"
                ></i>
              </span>
              <span class="strength__text" :style="{ color: strength.color }">
                密码强度：{{ strength.text }}
              </span>
            </div>
          </el-form-item>

          <el-form-item label="确认密码" prop="confirm">
            <el-input
              v-model="form.confirm"
              type="password"
              placeholder="再输一次"
              autocomplete="new-password"
              show-password
              :disabled="loading"
              @keyup.enter="submit"
            >
              <template #prefix><AppIcon name="lock" :size="16" /></template>
            </el-input>
          </el-form-item>

          <el-form-item label="邮箱（可选）" prop="email">
            <el-input
              v-model="form.email"
              placeholder="选填，用于登录找回"
              autocomplete="email"
              :disabled="loading"
              @keyup.enter="submit"
            >
              <template #prefix><AppIcon name="mail" :size="16" /></template>
            </el-input>
          </el-form-item>

          <el-button
            type="primary"
            class="panel__submit"
            size="large"
            :loading="loading"
            native-type="submit"
          >
            {{ loading ? '正在创建…' : '注 册' }}
          </el-button>
        </el-form>

        <p class="panel__foot">
          已经有账号了？
          <router-link to="/login">返回登录</router-link>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth {
  display: grid;
  grid-template-columns: 1fr 1.05fr;
  height: 100%;
  min-height: 100%;
}
.auth__brand {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  padding: 48px 52px;
  background: linear-gradient(158deg, #16142f 0%, #231d51 48%, #342a6e 100%);
  color: #fff;
}
.brand__inner {
  position: relative;
  z-index: 1;
  max-width: 420px;
}
.brand__glow {
  position: absolute;
  inset: auto -20% -30% -10%;
  height: 440px;
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
  margin-bottom: 30px;
}
.brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(135deg, #6d63f0, #a78bfa 55%, #38bdf8);
  box-shadow: 0 10px 26px -8px rgba(109, 99, 240, 0.95);
}
.brand__logo b {
  font-size: 17px;
}
.brand__slogan {
  margin: 0 0 14px;
  font-size: 32px;
  line-height: 1.3;
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
  margin: 0 0 30px;
  font-size: 13.5px;
  line-height: 1.75;
  color: #b3aedb;
  max-width: 340px;
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.steps li {
  display: flex;
  gap: 12px;
  align-items: center;
}
.steps em {
  width: 26px;
  height: 26px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-style: normal;
  font-size: 12.5px;
  font-weight: 700;
  color: #cfc7ff;
  background: rgba(124, 116, 235, 0.22);
  border: 1px solid rgba(147, 138, 255, 0.4);
}
.steps span {
  display: flex;
  flex-direction: column;
  line-height: 1.45;
}
.steps b {
  font-size: 13.5px;
  font-weight: 600;
}
.steps i {
  font-style: normal;
  font-size: 12.5px;
  color: #9d97c9;
}

.auth__panel {
  display: grid;
  place-items: center;
  padding: 36px 24px;
  background:
    radial-gradient(620px 380px at 12% 4%, #e9e6fd 0%, transparent 60%),
    linear-gradient(180deg, #fbfaff, #f4f3fa);
}
.panel__box {
  width: 100%;
  max-width: 372px;
}
.panel__head {
  margin-bottom: 22px;
}
.panel__head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.panel__head p {
  margin: 0;
  font-size: 13px;
  color: var(--af-ink-3);
}
.panel__alert {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}
.strength {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.strength__bars {
  display: flex;
  gap: 4px;
}
.strength__bars i {
  width: 26px;
  height: 4px;
  border-radius: 2px;
  transition: background-color 0.2s ease;
}
.strength__text {
  font-size: 11.5px;
}
.panel__submit {
  width: 100%;
  margin-top: 4px;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.panel__foot {
  margin: 18px 0 0;
  text-align: center;
  font-size: 13px;
  color: var(--af-ink-3);
}
.panel__foot a {
  font-weight: 600;
}

/* 表单密集，把 Element 默认间距压一点 */
.el-form-item {
  margin-bottom: 16px;
}

@media (max-width: 960px) {
  .auth {
    grid-template-columns: 1fr;
    height: auto;
  }
  .auth__brand {
    padding: 26px 24px 28px;
    align-items: flex-start;
  }
  .brand__inner {
    max-width: none;
  }
  .brand__logo {
    margin-bottom: 16px;
  }
  .brand__slogan {
    font-size: 22px;
  }
  .brand__sub {
    margin-bottom: 0;
  }
  .steps {
    display: none;
  }
  .auth__panel {
    padding: 26px 20px 40px;
  }
}
</style>
