<script setup>
/**
 * 在线检索：选一个知识库，提问，拿答案 + 召回片段。
 *
 * 对应 GET /open/retrieve?knowledge_id&query —— 这是全站唯一不需要登录的业务接口。
 *
 * ⚠️ 性能预期：后端每请求都会新建 MainRAG（把整个集合拉出来重建 BM25 再重排合成），
 *    实测单次 4.6~16 秒。所以这里必须做「长耗时」的等待体验：
 *    阶段文案轮播 + 计时器，否则用户会以为页面卡死了。
 * ⚠️ 知识库没有入库文档时后端返回 400（因为空集合会让 BM25 建索引直接抛异常）。
 *
 * 答案与引用片段都是 **Markdown**（大模型默认输出 md，文档本身也常是 md），
 * 统一交给 MarkdownBlock 渲染 —— 别再直接 {{ }} 输出，那样页面上会出现
 * `## 标题` `**重点**` `| a | b |` 这类原始记号。
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import MarkdownBlock from '@/components/MarkdownBlock.vue'
import { listKnowledges } from '@/api/knowledge'
import { retrieve } from '@/api/open'
import { formatNumber } from '@/utils/format'

const kbs = ref([])
const kbLoading = ref(true)
const kbId = ref(null)

const question = ref('')
const asking = ref(false)
const elapsed = ref(0)
const errorText = ref('')

/** 会话记录（只保留当前页面生命周期，刷新即清空） */
const history = ref([])
/** 每条记录里的片段展开状态，key 是记录下标 */
const openNodes = ref(new Set())

let timer = null

const currentKb = computed(() => kbs.value.find((k) => k.id === kbId.value) || null)
const canAsk = computed(() => Boolean(kbId.value) && Boolean(question.value.trim()) && !asking.value)
/** 知识库一个文档都没有时，别让用户白等十几秒 */
const kbEmpty = computed(() => currentKb.value && !currentKb.value.document_num)

const STAGES = [
  '正在改写问题（HyDE / 多查询）…',
  '正在做向量 + BM25 混合召回…',
  '正在重排与压缩片段…',
  '正在用大模型合成答案…'
]
const stageText = computed(() => STAGES[Math.min(Math.floor(elapsed.value / 3), STAGES.length - 1)])

const EXAMPLES = [
  '文档上传后会经历哪三个步骤？',
  '这个知识库主要讲了什么内容？',
  '检索时用到了哪些召回策略？'
]

async function loadKnowledges() {
  kbLoading.value = true
  try {
    const res = await listKnowledges({ page: 1, limit: 100 })
    kbs.value = Array.isArray(res) ? res : []
    // 默认选第一个「有文档」的库，没有就退而选第一个
    const withDocs = kbs.value.find((k) => k.document_num > 0)
    kbId.value = (withDocs || kbs.value[0])?.id ?? null
  } catch (err) {
    ElMessage.error(err.message || '知识库列表加载失败')
    kbs.value = []
  } finally {
    kbLoading.value = false
  }
}

function startTimer() {
  elapsed.value = 0
  clearInterval(timer)
  timer = setInterval(() => {
    elapsed.value += 1
  }, 1000)
}

function stopTimer() {
  clearInterval(timer)
  timer = null
}

async function ask(preset) {
  const q = (preset ?? question.value).trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  if (!kbId.value) {
    ElMessage.warning('请先选择知识库')
    return
  }

  const entry = {
    id: Date.now(),
    q,
    kbId: kbId.value,
    kbName: currentKb.value?.name || `#${kbId.value}`,
    answer: '',
    nodes: [],
    ms: 0,
    ok: false,
    err: ''
  }
  history.value.unshift(entry)

  asking.value = true
  errorText.value = ''
  question.value = ''
  startTimer()
  const startedAt = Date.now()

  try {
    const res = await retrieve({ knowledge_id: kbId.value, query: q })
    entry.answer = res?.answer || '（后端没有返回答案）'
    entry.nodes = res?.nodes || []
    entry.ok = true
  } catch (err) {
    entry.err = err.message || '检索失败'
    errorText.value = entry.err
    // 出错时把问题放回输入框，省得用户重敲
    question.value = q
  } finally {
    entry.ms = Date.now() - startedAt
    asking.value = false
    stopTimer()
    await nextTick()
  }
}

function toggleNodes(id) {
  const next = new Set(openNodes.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openNodes.value = next
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('浏览器拒绝了剪贴板权限，请手动选择复制')
  }
}

function clearAll() {
  history.value = []
  openNodes.value = new Set()
  errorText.value = ''
}

/** 片段元数据里对用户有意义的键，其余（file_path 等）不展示 */
const META_LABELS = {
  mysql_document_id: '文档ID',
  filename_uuid: '文件唯一名',
  file_name: '原文件名',
  knowledge_base_id: '知识库',
  creation_date: '入库时间'
}
function pickMeta(meta) {
  if (!meta) return []
  return Object.entries(META_LABELS)
    .filter(([key]) => meta[key] !== undefined && meta[key] !== null && meta[key] !== '')
    .map(([key, label]) => ({ key, label, value: String(meta[key]) }))
}

/** score 越高越相关，映射成一个小进度条让学生一眼看出排序 */
function scoreWidth(score) {
  if (score === null || score === undefined) return 0
  // 重排分和向量分的量纲不同，这里只做相对展示，封顶在 1
  return Math.max(6, Math.min(100, Math.round(Number(score) * 100)))
}

onMounted(loadKnowledges)
</script>

<template>
  <div class="af-page retrieve-page">
    <div class="af-page-head">
      <div>
        <h2 class="af-page-title">在线检索</h2>
        <p class="af-page-desc">
          选定知识库后提问，返回大模型合成的答案与召回片段（含相关度分数）
        </p>
      </div>
      <el-button v-if="history.length" :disabled="asking" @click="clearAll">
        <AppIcon name="trash" :size="15" style="margin-right: 5px" />
        清空对话
      </el-button>
    </div>

    <!-- 知识库选择 -->
    <div class="selector af-card">
      <label class="selector__field">
        <span>检索范围</span>
        <el-select
          v-model="kbId"
          placeholder="选择一个知识库"
          filterable
          :loading="kbLoading"
          :disabled="asking"
          style="width: 260px"
        >
          <el-option
            v-for="k in kbs"
            :key="k.id"
            :label="k.name"
            :value="k.id"
            :disabled="!k.document_num"
          >
            <span class="opt">
              <span class="opt__name">{{ k.name }}</span>
              <span class="opt__num" :class="{ zero: !k.document_num }">
                {{ k.document_num ? `${k.document_num} 份` : '无文档' }}
              </span>
            </span>
          </el-option>
        </el-select>
      </label>

      <div class="selector__info">
        <template v-if="currentKb">
          <span class="chip">
            <AppIcon name="database" :size="13" />
            {{ currentKb.name }}
          </span>
          <span class="chip">
            <AppIcon name="layers" :size="13" />
            {{ formatNumber(currentKb.document_num) }} 份文档
          </span>
          <span class="chip af-mono">agentflow_kb_{{ currentKb.id }}</span>
        </template>
        <span v-else class="af-dim">还没有可选的知识库，先去「知识库」里创建一个</span>
      </div>
    </div>

    <el-alert
      v-if="kbEmpty"
      type="warning"
      show-icon
      :closable="false"
      class="mb"
      title="这个知识库还没有入库文档，检索会直接失败"
    >
      <template #default>
        请先到
        <router-link :to="`/knowledge/${kbId}`">知识库详情</router-link>
        上传并入库文档。
      </template>
    </el-alert>

    <!-- 对话区 -->
    <section class="thread">
      <!-- 首屏引导 -->
      <div v-if="!history.length" class="guide af-card">
        <span class="guide__ico" aria-hidden="true"><AppIcon name="sparkles" :size="24" /></span>
        <h3>问点什么试试</h3>
        <p>答案由大模型基于召回片段合成，下方会列出引用到的片段与相关度</p>
        <div class="guide__examples">
          <button
            v-for="ex in EXAMPLES"
            :key="ex"
            type="button"
            class="example"
            :disabled="asking || !kbId"
            @click="ask(ex)"
          >
            <AppIcon name="search" :size="14" />
            {{ ex }}
          </button>
        </div>
      </div>

      <!-- 每条问答 -->
      <article v-for="item in history" :key="item.id" class="turn">
        <div class="q">
          <span class="q__avatar" aria-hidden="true"><AppIcon name="user" :size="14" /></span>
          <div class="q__body">
            <p class="q__text">{{ item.q }}</p>
            <p class="q__meta">
              <span>{{ item.kbName }}</span>
              <i></i>
              <span>{{ item.ms ? `${(item.ms / 1000).toFixed(1)}s` : '…' }}</span>
            </p>
          </div>
        </div>

        <div class="a">
          <span class="a__avatar" aria-hidden="true"><AppIcon name="sparkles" :size="14" /></span>
          <div class="a__body">
            <!-- 出错 -->
            <div v-if="item.err" class="a__error">
              <AppIcon name="warning" :size="15" style="margin-right: 6px" />
              <span>{{ item.err }}</span>
            </div>

            <!-- 成功 -->
            <template v-else>
              <div class="answer">
                <MarkdownBlock class="answer__md" :source="item.answer" />
                <div class="answer__tools">
                  <el-button link size="small" @click="copyText(item.answer)">
                    <AppIcon name="copy" :size="13" style="margin-right: 4px" />
                    复制答案
                  </el-button>
                  <span class="af-dim">{{ item.nodes.length }} 引用片段</span>
                </div>
              </div>

              <!-- 引用片段 -->
              <div v-if="item.nodes.length" class="nodes">
                <button
                  type="button"
                  class="nodes__toggle"
                  :aria-expanded="openNodes.has(item.id)"
                  @click="toggleNodes(item.id)"
                >
                  <AppIcon
                    name="chevronRight"
                    :size="13"
                    :style="{
                      transform: openNodes.has(item.id) ? 'rotate(90deg)' : 'none',
                      transition: 'transform .18s ease'
                    }"
                  />
                  引用片段（{{ item.nodes.length }}）
                </button>

                <ul v-show="openNodes.has(item.id)" class="nodes__list">
                  <li v-for="node in item.nodes" :key="node.node_id" class="node">
                    <header class="node__head">
                      <span class="node__id af-mono" :title="node.node_id">{{ node.node_id }}</span>
                      <span class="node__score" :title="`相关度 ${node.score}`">
                        <i :style="{ width: `${scoreWidth(node.score)}%` }"></i>
                        <em>{{ node.score === null ? '—' : Number(node.score).toFixed(3) }}</em>
                      </span>
                    </header>
                    <MarkdownBlock class="node__text" :source="node.text" />
                    <div v-if="pickMeta(node.metadata).length" class="node__meta">
                      <span v-for="m in pickMeta(node.metadata)" :key="m.key" class="node__meta-item">
                        <b>{{ m.label }}</b>{{ m.value }}
                      </span>
                    </div>
                  </li>
                </ul>
              </div>
            </template>
          </div>
        </div>
      </article>

      <!-- 等待中 -->
      <article v-if="asking" class="turn">
        <div class="q">
          <span class="q__avatar" aria-hidden="true"><AppIcon name="user" :size="14" /></span>
          <div class="q__body">
            <p class="q__text af-dim">正在思考…</p>
          </div>
        </div>
        <div class="a">
          <span class="a__avatar a__avatar--busy" aria-hidden="true">
            <AppIcon name="sparkles" :size="14" />
          </span>
          <div class="a__body">
            <div class="pending">
              <span class="pending__dots" aria-hidden="true"><i></i><i></i><i></i></span>
              <span class="pending__text">{{ stageText }}</span>
              <span class="pending__time af-mono">{{ elapsed }}s</span>
            </div>
            <p class="pending__tip">
              完整链路要跑「问题改写 → 向量+BM25 融合召回 → 重排压缩 → 大模型合成」，
              单次通常需要 5~15 秒，请稍候。
            </p>
          </div>
        </div>
      </article>
    </section>

    <!-- 输入区 -->
    <div class="composer">
      <div class="composer__box af-card">
        <textarea
          v-model="question"
          class="composer__input"
          rows="2"
          placeholder="输入你的问题，Enter 发送，Shift + Enter 换行"
          :disabled="asking"
          @keydown.enter.exact.prevent="ask()"
        ></textarea>
        <div class="composer__foot">
          <span class="composer__hint">
            <template v-if="!kbId">请先选择一个知识库</template>
            <template v-else-if="kbEmpty">该知识库暂无文档，检索不可用</template>
            <template v-else>将检索「{{ currentKb?.name }}」</template>
          </span>
          <el-button
            type="primary"
            :loading="asking"
            :disabled="!canAsk || kbEmpty"
            @click="ask()"
          >
            {{ asking ? '检索中…' : '发送' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 输入区吸底，给内容留出空间 */
.retrieve-page {
  padding-bottom: 150px;
}
.mb {
  margin-bottom: 12px;
  border-radius: var(--af-radius);
}

/* ---- 选择器 ---- */
.selector {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 13px 16px;
  margin-bottom: 14px;
}
.selector__field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.selector__field > span {
  font-size: 12px;
  color: var(--af-ink-3);
}
.selector__info {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  font-size: 12px;
  padding-bottom: 4px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  background: #f4f3fb;
  border: 1px solid var(--af-line);
  color: var(--af-ink-2);
}
.opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.opt__num {
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.opt__num.zero {
  color: var(--af-danger);
}

/* ---- 引导 ---- */
.guide {
  padding: 34px 22px;
  text-align: center;
}
.guide__ico {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 13px;
  border-radius: 16px;
  color: #7f76ee;
  background: linear-gradient(135deg, #efecfe, #e6f3fc);
}
.guide h3 {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 620;
}
.guide p {
  margin: 0 auto 20px;
  font-size: 12.5px;
  color: var(--af-ink-3);
  max-width: 460px;
  line-height: 1.7;
}
.guide__examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.example {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 13px;
  min-height: 36px;
  border-radius: 999px;
  border: 1px solid var(--af-line);
  background: #fff;
  color: var(--af-ink-2);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}
.example:hover:not(:disabled) {
  border-color: var(--af-primary);
  color: var(--af-primary);
  transform: translateY(-1px);
}
.example:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---- 对话 ---- */
.thread {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.turn {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.q,
.a {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.q__avatar,
.a__avatar {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 9px;
}
.q__avatar {
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #38bdf8);
}
.a__avatar {
  color: #fff;
  background: linear-gradient(135deg, #10a37f, #34d399);
}
.a__avatar--busy {
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(16, 163, 127, 0.45);
  }
  50% {
    box-shadow: 0 0 0 7px rgba(16, 163, 127, 0);
  }
}

.q__body,
.a__body {
  flex: 1;
  min-width: 0;
}
.q__text {
  margin: 0;
  padding: 9px 13px;
  border-radius: 12px 12px 12px 3px;
  background: #fff;
  border: 1px solid var(--af-line);
  font-size: 13.5px;
  line-height: 1.65;
  word-break: break-word;
}
.q__meta {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 5px 0 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.q__meta i {
  width: 1px;
  height: 9px;
  background: var(--af-line);
}

/* 答案卡 */
.answer {
  padding: 13px 15px;
  border-radius: 12px 12px 12px 3px;
  background: linear-gradient(180deg, #ffffff, #fafbff);
  border: 1px solid #d9d6ee;
  box-shadow: var(--af-shadow-sm);
}
/* 答案正文：排版交给 MarkdownBlock（.md-body），这里只管字号与行距 */
.answer__md {
  font-size: 13.5px;
  line-height: 1.78;
}
.answer__tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px dashed var(--af-line);
}

.a__error {
  display: flex;
  align-items: center;
  padding: 11px 13px;
  border-radius: var(--af-radius);
  background: #fdf0f0;
  border: 1px solid #f7d4d4;
  color: #a8322f;
  font-size: 13px;
}

/* 引用片段 */
.nodes {
  margin-top: 8px;
}
.nodes__toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  min-height: 32px;
  border-radius: 8px;
  border: 1px solid var(--af-line);
  background: #fff;
  color: var(--af-ink-2);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}
.nodes__toggle:hover {
  border-color: var(--af-primary);
  color: var(--af-primary);
}
.nodes__list {
  list-style: none;
  margin: 9px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.node {
  padding: 11px 13px;
  border-radius: var(--af-radius);
  background: #fff;
  border: 1px solid var(--af-line);
}
.node__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
}
.node__id {
  color: #6d63f0;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node__score {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: none;
  width: 128px;
}
.node__score i {
  display: block;
  height: 5px;
  border-radius: 3px;
  background: linear-gradient(90deg, #6d63f0, #10a37f);
  transition: width 0.35s ease;
}
.node__score em {
  font-style: normal;
  font-family: var(--af-font-mono);
  font-size: 11px;
  color: var(--af-ink-3);
  margin-left: auto;
}
/* 召回片段：同样是 Markdown（文档正文本身），由 MarkdownBlock 渲染 */
.node__text {
  font-size: 12.5px;
  color: var(--af-ink-2);
}
.node__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px dashed var(--af-line);
}
.node__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f5f4fc;
  font-family: var(--af-font-mono);
  font-size: 10.5px;
  color: var(--af-ink-3);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node__meta-item b {
  font-family: var(--af-font);
  font-weight: 500;
  color: var(--af-ink-4);
}

/* 等待 */
.pending {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 12px 12px 12px 3px;
  background: #fff;
  border: 1px solid var(--af-line);
}
.pending__dots {
  display: inline-flex;
  gap: 3px;
}
.pending__dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8b83ee;
  animation: bounce 1.2s ease-in-out infinite;
}
.pending__dots i:nth-child(2) {
  animation-delay: 0.16s;
}
.pending__dots i:nth-child(3) {
  animation-delay: 0.32s;
}
@keyframes bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}
.pending__text {
  font-size: 13px;
  color: var(--af-ink-2);
}
.pending__time {
  margin-left: auto;
  font-size: 12px;
  color: var(--af-ink-4);
}
.pending__tip {
  margin: 9px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--af-ink-4);
}

/* ---- 输入区（吸底） ---- */
.composer {
  position: fixed;
  left: var(--af-nav-width);
  right: 0;
  bottom: 0;
  padding: 12px 24px 16px;
  background: linear-gradient(180deg, rgba(246, 245, 251, 0), var(--af-bg) 42%);
  z-index: 15;
}
.composer__box {
  max-width: 1352px; /* 和 .af-page 的内容宽度对齐（1400 - 2×24） */
  margin: 0 auto;
  padding: 10px 12px;
  box-shadow: var(--af-shadow-lg);
}
.composer__input {
  display: block;
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-family: inherit;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--af-ink-1);
  max-height: 140px;
}
.composer__input::placeholder {
  color: var(--af-ink-4);
}
.composer__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px solid var(--af-line-soft);
}
.composer__hint {
  font-size: 11.5px;
  color: var(--af-ink-4);
}

@media (max-width: 900px) {
  .composer {
    left: 0;
    padding: 10px 14px 14px;
  }
  .retrieve-page {
    padding-bottom: 170px;
  }
  .selector__field {
    width: 100%;
  }
  .selector__field :deep(.el-select) {
    width: 100% !important;
  }
  .node__score {
    width: 88px;
  }
}
</style>
