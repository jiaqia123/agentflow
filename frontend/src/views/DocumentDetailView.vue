<script setup>
/**
 * 文档详情：元信息 + 正文片段 + 重新切分。
 *
 * ⚠️ 后端限制（决定了这一页的实现方式）：
 *   1 没有 `GET /document/{id}`。文档行只能从 `/document/list` 拿，而它不支持按 id 查单条，
 *     所以优先用列表页点「查看」时缓存下来的那一行（composables/useDocumentCache.js）；
 *     缓存没了（直接刷新 / 手输 URL）就翻 /document/list 扫描兜底。
 *   2 没有「按文档查已入库片段」的接口（正文在 documents_chunks 表里，但没有暴露出来），
 *     **入库时用的切分参数也没有存库**。
 *
 * 于是正文片段按三级优先取，页面上会明确标出当前用的是哪一级 —— 不假装它们一样：
 *
 *   ① 入库快照（snapshot）
 *      上传抽屉在 /store 成功那一刻，把「真实片段 + 当时参数」按 document_id 存进
 *      localStorage（useDocumentCache.rememberSnapshot）。这是**唯一**与库里内容逐块一致的来源，
 *      块数必然等于 documents.chunk_count。刷新浏览器也还在。
 *
 *   ② 自动反推参数（fitted / best-effort）
 *      换浏览器、清过缓存、或文档是别处入库的时候没有快照。
 *      这时不再傻用默认 chunk_size=512（实测这份文档 512 只能切出 1 块，而库里是 4 块
 *      —— 就是「列表说 4 块、详情页只有 1 块」那个 bug 的根因），
 *      而是拿 char_count / chunk_count 估一个量级，再逐个 chunk_size 试切，命中就停。
 *
 *   ③ 手动参数（manual）
 *      用户点「重新切分」自己指定参数，只刷新本页预览，不动已入库的片段。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import MarkdownBlock from '@/components/MarkdownBlock.vue'
import SplitParamsDialog from '@/components/SplitParamsDialog.vue'
import { getCachedDocument, getSnapshot } from '@/composables/useDocumentCache'
import { listDocuments, splitDocument } from '@/api/document'
import { getKnowledge } from '@/api/knowledge'
import { DEFAULT_SPLIT_PARAMS, separatorLabel, separatorPreview } from '@/utils/split'
import { formatDateTime, formatNumber, fileExt } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const docId = computed(() => Number(route.params.id))

const loading = ref(true)
const loadError = ref('')
const doc = ref(null)
const kb = ref(null)

const params = ref({ ...DEFAULT_SPLIT_PARAMS })
const paramsVisible = ref(false)

const chunkLoading = ref(false)
const chunkError = ref('')
const chunks = ref([])
/**
 * 片段的来源：
 *   snapshot   入库那一刻的真实片段（本地快照）
 *   fitted     自动反推参数，块数已与库里一致
 *   best-effort 自动反推没命中，给的是最接近的一次
 *   manual     用户手动指定参数重新切
 *   none       还没拿到
 */
const chunkSource = ref('none')
const fitTried = ref(0)
const fitTotal = ref(0)

const visibleCount = ref(30)
const expandedChunks = ref(new Set())

/** 自动反推时要试的 chunk_size 档位（128 是后端的硬下限，元数据就占 100 token） */
const SIZE_CANDIDATES = [128, 160, 192, 256, 320, 384, 448, 512, 640, 768, 1024, 1280, 1536, 2048, 3072, 4096]
/** 尝试次数上限。实测自适应跳步通常 1~3 次收敛，留 8 次是给噪声情形兜底 */
const FIT_MAX_TRIES = 8
/** 起始档位的估算系数：中文大约 1 个字符 0.75 个 token（512 token ≈ 680 汉字） */
const TOKEN_PER_CHAR = 0.75

const shownChunks = computed(() => chunks.value.slice(0, visibleCount.value))
const hasMoreChunks = computed(() => chunks.value.length > visibleCount.value)

const kbName = computed(
  () => kb.value?.name || (doc.value ? `知识库 #${doc.value.knowledge_base_id}` : '')
)

/** 平均每块多少字，用来看切分粒度是否合适 */
const avgChunkChars = computed(() => {
  const d = doc.value
  if (!d?.chunk_count) return 0
  return Math.round((d.char_count || 0) / d.chunk_count)
})

/** 当前片段与库里记录是否对得上（对不上就必须在界面上说清楚） */
const countMismatch = computed(
  () => Boolean(doc.value?.chunk_count) && chunks.value.length !== doc.value.chunk_count
)

const sourceMeta = computed(() => {
  switch (chunkSource.value) {
    case 'snapshot':
      return { text: '入库快照', type: 'success' }
    case 'fitted':
      return { text: '已还原入库参数', type: 'primary' }
    case 'best-effort':
      return { text: '未能精确还原', type: 'warning' }
    case 'manual':
      return { text: '手动参数预览', type: 'info' }
    default:
      return null
  }
})

/** 缓存里没有就翻 /document/list 找（每页最多 100，最多翻 10 页 = 1000 份） */
async function findDocument(id) {
  const limit = 100
  for (let p = 1; p <= 10; p += 1) {
    const res = await listDocuments({ page: p, limit })
    const items = res?.items || []
    const hit = items.find((item) => item.id === id)
    if (hit) return hit
    if (items.length < limit || (res?.total ?? 0) <= p * limit) break
  }
  return null
}

async function loadDoc() {
  loading.value = true
  loadError.value = ''
  try {
    let found = getCachedDocument(docId.value)
    if (!found) found = await findDocument(docId.value)
    if (!found) {
      doc.value = null
      loadError.value = `没找到 ID 为 ${docId.value} 的文档 —— 可能已被删除，或不属于当前账号`
      return
    }
    doc.value = found
  } catch (err) {
    loadError.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

/** 知识库名只为展示，拉不到就用 #id 兜底，不阻塞页面 */
async function loadKb() {
  if (!doc.value?.knowledge_base_id) return
  try {
    kb.value = await getKnowledge(doc.value.knowledge_base_id)
  } catch {
    kb.value = null
  }
}

/** 按给定参数切一次。404 = 磁盘文件没了、400 = 解析失败，这两种重试也没用 */
async function splitOnce(size, separator) {
  const res = await splitDocument({
    new_filename: doc.value.filename_uuid,
    separator,
    chunk_size: Number(size),
    chunk_overlap: Number(params.value.chunk_overlap)
  })
  return res?.chunks || []
}

/**
 * 在还没试过的档位里挑一个最接近 size 的。
 * 距离相同时取更大的那个 —— 切多了需要把 chunk_size 调大，别在原地来回跳。
 */
function nearestUntried(size, tried) {
  let pick = null
  for (const c of SIZE_CANDIDATES) {
    if (tried.has(c)) continue
    if (pick === null) {
      pick = c
      continue
    }
    const d = Math.abs(c - size)
    const dp = Math.abs(pick - size)
    if (d < dp || (d === dp && c > pick)) pick = c
  }
  return pick
}

/**
 * 按库里的片段数反推 chunk_size。
 *
 * 先用平均每块字数估一个起始档位，之后**每试一次就按实测块数跳一步**：
 * 块数大致与 chunk_size 成反比，所以 `下一个 ≈ 当前 × 实测块数 / 目标块数`。
 * 实测（5561 字符的文档、目标 14 块）：逐个试要 6 次才命中，自适应 3 次就收敛。
 *
 * @returns {Promise<{chunks: Array, chunkSize: number|null, matched: boolean, error: Error|null}>}
 */
async function autoFitSplit(target, charCount) {
  const tried = new Set()
  let best = null
  let lastError = null

  const estimate =
    target > 0 && charCount > 0
      ? (charCount / target) * TOKEN_PER_CHAR
      : DEFAULT_SPLIT_PARAMS.chunk_size

  fitTried.value = 0
  fitTotal.value = target > 0 ? FIT_MAX_TRIES : 1

  let size = nearestUntried(estimate, tried)

  for (let attempt = 0; attempt < FIT_MAX_TRIES && size; attempt += 1) {
    tried.add(size)
    fitTried.value = attempt + 1
    try {
      const got = await splitOnce(size, DEFAULT_SPLIT_PARAMS.separator)
      const diff = Math.abs(got.length - target)
      if (!best || diff < best.diff) best = { chunks: got, chunkSize: size, diff }
      if (target > 0 && got.length === target) {
        return { chunks: got, chunkSize: size, matched: true, error: null }
      }
      if (target <= 0) break
      const nextSize = got.length > 0 ? size * (got.length / target) : size * 2
      size = nearestUntried(nextSize, tried)
    } catch (err) {
      lastError = err
      // 文件在磁盘上没了 / 解析不了 → 换参数也没用，直接停
      if (err?.status === 404 || err?.status === 400) break
      // 其它错误（例如 500 元数据超长）换个档位继续试
      size = nearestUntried(size * 2, tried)
    }
  }

  if (!best) return { chunks: [], chunkSize: null, matched: false, error: lastError }
  return { chunks: best.chunks, chunkSize: best.chunkSize, matched: false, error: null }
}

/**
 * 自动取片段：入库快照优先，没有则反推参数。
 * 供 onMounted 与「重新加载」按钮使用。
 */
async function loadChunks() {
  if (!doc.value?.filename_uuid) return
  chunkLoading.value = true
  chunkError.value = ''
  visibleCount.value = 30
  expandedChunks.value = new Set()

  // ① 入库快照：与库里内容一致，直接用，不再请求接口
  const snap = getSnapshot(docId.value, doc.value)
  if (snap) {
    params.value = { ...DEFAULT_SPLIT_PARAMS, ...snap.params }
    chunks.value = snap.chunks
    chunkSource.value = 'snapshot'
    chunkLoading.value = false
    return
  }

  // ② 没有快照 → 按库里的片段数反推参数
  try {
    const target = Number(doc.value.chunk_count) || 0
    const charCount = Number(doc.value.char_count) || 0
    const fit = await autoFitSplit(target, charCount)

    if (!fit.chunks.length) {
      chunks.value = []
      chunkSource.value = 'none'
      const err = fit.error
      if (err?.status === 404) {
        chunkError.value = '磁盘上已找不到这个文件（可能被清理过），读不到正文片段'
      } else if (err?.status === 400) {
        chunkError.value = err.message || '文件解析失败，读不出内容'
      } else {
        chunkError.value = err?.message || '片段加载失败'
      }
      return
    }

    chunks.value = fit.chunks
    params.value = { ...DEFAULT_SPLIT_PARAMS, chunk_size: fit.chunkSize }
    chunkSource.value = fit.matched ? 'fitted' : 'best-effort'
  } catch (err) {
    chunks.value = []
    chunkSource.value = 'none'
    chunkError.value = err.message || '片段加载失败'
  } finally {
    chunkLoading.value = false
  }
}

/** 手动「重新切分」：按用户指定的参数切一次，只刷新本页预览 */
async function onSplitConfirm(next) {
  params.value = { ...next }
  if (!doc.value?.filename_uuid) return
  chunkLoading.value = true
  chunkError.value = ''
  visibleCount.value = 30
  expandedChunks.value = new Set()
  try {
    chunks.value = await splitOnce(next.chunk_size, next.separator)
    chunkSource.value = 'manual'
  } catch (err) {
    chunks.value = []
    chunkSource.value = 'none'
    if (err.status === 404) {
      chunkError.value = '磁盘上已找不到这个文件（可能被清理过），读不到正文片段'
    } else if (err.status === 400) {
      chunkError.value = err.message || '文件解析失败，读不出内容'
    } else {
      chunkError.value = err.message || '片段加载失败'
    }
  } finally {
    chunkLoading.value = false
  }
}

function toggleChunk(index) {
  const next = new Set(expandedChunks.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  expandedChunks.value = next
}

async function copy(text, label = '已复制') {
  if (!text) return
  try {
    await navigator.clipboard.writeText(String(text))
    ElMessage.success(label)
  } catch {
    ElMessage.warning('当前环境不支持自动复制，请手动选中复制')
  }
}

onMounted(async () => {
  await loadDoc()
  if (!doc.value) return
  loadKb()
  loadChunks()
})
</script>

<template>
  <div class="af-page">
    <!-- 加载中 -->
    <div v-if="loading" class="af-card af-card--pad">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 找不到 -->
    <div v-else-if="loadError" class="af-card af-empty">
      <span class="empty-ico" aria-hidden="true"><AppIcon name="warning" :size="24" /></span>
      <h3>找不到这份文档</h3>
      <p>{{ loadError }}</p>
      <el-button @click="router.replace('/documents')">返回文档库</el-button>
    </div>

    <template v-else-if="doc">
      <button class="back" type="button" @click="router.push('/documents')">
        <AppIcon name="back" :size="15" />
        返回文档库
      </button>

      <!-- 文档信息 -->
      <section class="hero af-card">
        <div class="hero__main">
          <span class="hero__ext" aria-hidden="true">
            {{ fileExt(doc.filename_original).replace('.', '') || '?' }}
          </span>

          <div class="hero__text">
            <h2 :title="doc.filename_original">{{ doc.filename_original }}</h2>
            <div class="hero__meta">
              <span>文档 ID <b class="af-mono">#{{ doc.id }}</b></span>
              <i></i>
              <span>入库于 {{ formatDateTime(doc.created_at) }}</span>
              <i></i>
              <span>
                所属知识库
                <router-link :to="`/knowledge/${doc.knowledge_base_id}`">{{ kbName }}</router-link>
              </span>
            </div>
            <p class="hero__uuid">
              磁盘唯一名
              <em class="af-mono">{{ doc.filename_uuid }}</em>
              <el-button link type="primary" size="small" @click="copy(doc.filename_uuid, '唯一名已复制')">
                复制
              </el-button>
            </p>
          </div>
        </div>

        <div class="hero__actions">
          <el-button :disabled="chunkLoading" @click="paramsVisible = true">
            <AppIcon name="filter" :size="15" style="margin-right: 5px" />
            重新切分
          </el-button>
          <el-button :loading="chunkLoading" @click="loadChunks">
            <AppIcon name="refresh" :size="15" style="margin-right: 5px" />
            重新加载
          </el-button>
        </div>
      </section>

      <!-- 指标 -->
      <div class="metrics">
        <div class="metric">
          <span>字符数</span>
          <b>{{ formatNumber(doc.char_count) }}<em>字符</em></b>
        </div>
        <div class="metric">
          <span>入库片段数</span>
          <b>{{ formatNumber(doc.chunk_count) }}<em>块</em></b>
        </div>
        <div class="metric">
          <span>平均片段长度</span>
          <b>{{ formatNumber(avgChunkChars) }}<em>字符/块</em></b>
        </div>
      </div>

      <!-- 正文片段 -->
      <section class="af-card af-card--pad">
        <header class="chunks__head">
          <div>
            <h3>
              正文片段
              <el-tag v-if="sourceMeta" :type="sourceMeta.type" size="small" effect="light" class="src-tag">
                {{ sourceMeta.text }}
              </el-tag>
            </h3>
            <p>
              <template v-if="chunks.length">
                共 <b>{{ chunks.length }}</b> 块
                <template v-if="countMismatch">
                  <em class="warn">库里记录为 {{ doc.chunk_count }} 块</em>
                </template>
                <i>·</i>
              </template>
              长度 <b>{{ params.chunk_size }}</b> token
              <i>·</i>
              重叠 <b>{{ params.chunk_overlap }}</b>
              <i>·</i>
              切分方式 <b>{{ separatorLabel(params.separator) }}</b>
              <em class="af-mono">{{ separatorPreview(params.separator) }}</em>
            </p>
          </div>
          <div class="chunks__tools">
            <el-button :disabled="chunkLoading" @click="paramsVisible = true">
              <AppIcon name="filter" :size="15" style="margin-right: 5px" />
              重新切分
            </el-button>
            <el-button :loading="chunkLoading" title="重新取片段" @click="loadChunks">
              <AppIcon name="refresh" :size="15" />
            </el-button>
          </div>
        </header>

        <el-alert
          v-if="chunkSource === 'snapshot'"
          type="success"
          show-icon
          :closable="false"
          class="notice"
        >
          <template #default>
            这些是<b>入库那一刻</b>真实切分出来的片段（保存在本机的入库快照），逐块与库里内容一致，
            共 {{ doc.chunk_count }} 块。
          </template>
        </el-alert>

        <el-alert
          v-else-if="chunkSource === 'fitted'"
          type="info"
          show-icon
          :closable="false"
          class="notice"
        >
          <template #default>
            后端没有保存入库时使用的切分参数，这里按库里记录的
            <b>{{ doc.chunk_count }}</b> 块自动反推出等价参数（长度
            <b>{{ params.chunk_size }}</b> token）并重新切分，<b>块数已对齐</b>。
            片段正文与入库内容可能有个别字符级差异。
          </template>
        </el-alert>

        <el-alert
          v-else-if="chunkSource === 'best-effort'"
          type="warning"
          show-icon
          :closable="false"
          class="notice"
        >
          <template #default>
            试了 <b>{{ fitTried }}</b> 组参数都没能复现库里的
            <b>{{ doc.chunk_count }}</b> 块，下面是最接近的一次（<b>{{ chunks.length }}</b> 块）。
            本机没有这份文档的入库快照 —— 在「文档库」里重新上传入库一次，就能拿到逐块一致的快照。
          </template>
        </el-alert>

        <el-alert
          v-else-if="chunkSource === 'manual'"
          type="info"
          show-icon
          :closable="false"
          class="notice"
        >
          <template #default>
            这是用你手动指定的参数重新切分出来的预览，<b>不会改动已入库的片段</b>，
            仅用于观察不同参数下的切分效果。
          </template>
        </el-alert>

        <!-- 反推进度 -->
        <div v-if="chunkLoading && fitTotal > 1 && !chunks.length" class="fitting">
          <span class="fitting__spinner" aria-hidden="true"></span>
          <span>
            正在按库里的 {{ doc.chunk_count }} 块反推切分参数…（第 {{ fitTried }} 次尝试，最多 {{ fitTotal }} 次）
          </span>
        </div>

        <div v-if="chunkLoading && !chunks.length && fitTotal <= 1" class="skeleton">
          <el-skeleton :rows="6" animated />
        </div>

        <el-alert v-else-if="chunkError" type="warning" show-icon :closable="false" class="mb">
          <template #default>
            <span>{{ chunkError }}　</span>
            <el-button link type="primary" size="small" @click="loadChunks">重试</el-button>
          </template>
        </el-alert>

        <div v-else-if="!chunks.length && !chunkLoading" class="af-empty">
          <span class="empty-ico" aria-hidden="true"><AppIcon name="file" :size="24" /></span>
          <h3>没有切出片段</h3>
          <p>可能是文件内容为空，或所选参数不适合这份文档</p>
          <el-button @click="paramsVisible = true">换个参数试试</el-button>
        </div>

        <template v-else-if="chunks.length">
          <ul class="chunks" v-loading="chunkLoading">
            <li
              v-for="c in shownChunks"
              :key="c.index"
              class="chunk"
              :class="{ 'is-open': expandedChunks.has(c.index) }"
            >
              <div class="chunk__head">
                <span class="chunk__idx">#{{ c.index }}</span>
                <span class="chunk__range af-mono">{{ c.char_start }}–{{ c.char_end }}</span>
                <span class="chunk__len af-dim">{{ c.text.length }} 字</span>
                <button class="chunk__toggle" type="button" @click="toggleChunk(c.index)">
                  {{ expandedChunks.has(c.index) ? '收起' : '展开' }}
                  <AppIcon
                    name="chevronRight"
                    :size="11"
                    :style="{
                      transform: expandedChunks.has(c.index) ? 'rotate(90deg)' : 'none',
                      transition: 'transform .18s ease'
                    }"
                  />
                </button>
              </div>
              <!-- 片段正文按 Markdown 渲染（文档本身多半就是 md），不再原样吐记号 -->
              <div
                class="chunk__body"
                :class="{ 'is-clamp': !expandedChunks.has(c.index) }"
                @click="toggleChunk(c.index)"
              >
                <MarkdownBlock :source="c.text" />
              </div>
            </li>
          </ul>

          <div class="chunks__more">
            <el-button v-if="hasMoreChunks" @click="visibleCount += 30">
              显示更多（还有 {{ chunks.length - visibleCount }} 块）
            </el-button>
            <span v-else class="af-dim">已显示全部 {{ chunks.length }} 块</span>
          </div>
        </template>
      </section>

      <SplitParamsDialog
        v-model="paramsVisible"
        :params="params"
        :loading="chunkLoading"
        hint="确认后按新参数重新切分该文档，只刷新本页预览，不会改动已入库的片段"
        @confirm="onSplitConfirm"
      />
    </template>
  </div>
</template>

<style scoped>
.back {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 12px;
  padding: 5px 9px 5px 7px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--af-ink-3);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.back:hover {
  background: #fff;
  border-color: var(--af-line);
  color: var(--af-primary);
}

/* ---- 文档信息 ---- */
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 18px;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: linear-gradient(90deg, #6d63f0, transparent 70%);
}
.hero__main {
  display: flex;
  gap: 14px;
  min-width: 0;
  flex: 1;
}
.hero__ext {
  width: 56px;
  height: 56px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 15px;
  font-family: var(--af-font-mono);
  font-size: 13px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #a78bfa);
  box-shadow: 0 10px 22px -12px #6d63f0;
}
.hero__text {
  min-width: 0;
}
.hero__text h2 {
  margin: 0 0 6px;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.02em;
  word-break: break-all;
}
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--af-ink-3);
}
.hero__meta b {
  color: var(--af-ink-1);
}
.hero__meta i {
  width: 1px;
  height: 10px;
  background: var(--af-line);
}
.hero__uuid {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin: 9px 0 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.hero__uuid em {
  font-style: normal;
  padding: 1px 6px;
  border-radius: 5px;
  background: #f1effb;
  color: #5a50d8;
  word-break: break-all;
}
.hero__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---- 指标 ---- */
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0;
}
.metric {
  padding: 12px 14px;
  border-radius: var(--af-radius-lg);
  background: #fff;
  border: 1px solid var(--af-line);
}
.metric span {
  display: block;
  font-size: 12px;
  color: var(--af-ink-3);
  margin-bottom: 4px;
}
.metric b {
  font-family: var(--af-font-mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.metric b em {
  font-style: normal;
  font-family: var(--af-font);
  font-size: 11.5px;
  color: var(--af-ink-4);
  margin-left: 3px;
}

/* ---- 片段 ---- */
.chunks__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.chunks__head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 14.5px;
  font-weight: 620;
}
.src-tag {
  font-weight: 400;
}
.chunks__head p {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--af-ink-3);
}
.chunks__head p i {
  font-style: normal;
  color: var(--af-ink-4);
}
.chunks__head b {
  color: var(--af-ink-1);
}
.chunks__head em {
  font-style: normal;
  margin-left: 3px;
  padding: 0 5px;
  border-radius: 5px;
  background: #eceafd;
  color: #5a50d8;
}
/* 片数对不上时的高亮：这是用户最容易困惑的地方 */
.chunks__head em.warn {
  background: #fdf0f0;
  color: #a8322f;
}
.chunks__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notice {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}
.mb {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}
.skeleton {
  padding: 6px 0;
}

/* 反推参数时的进度提示 */
.fitting {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  margin-bottom: 12px;
  border-radius: var(--af-radius);
  background: #f8f7fd;
  border: 1px dashed #dcd9f1;
  font-size: 12.5px;
  color: var(--af-ink-3);
}
.fitting__spinner {
  width: 14px;
  height: 14px;
  flex: none;
  border-radius: 50%;
  border: 2px solid #dcd9f1;
  border-top-color: var(--af-primary);
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.chunks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chunk {
  border: 1px solid var(--af-line);
  border-radius: var(--af-radius);
  background: #fff;
  padding: 9px 11px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.chunk.is-open {
  border-color: #c9c4ef;
  box-shadow: var(--af-shadow-sm);
}
.chunk__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}
.chunk__idx {
  font-family: var(--af-font-mono);
  font-size: 11.5px;
  font-weight: 600;
  color: #6d63f0;
  min-width: 34px;
}
.chunk__range {
  font-size: 10.5px;
  color: var(--af-ink-4);
}
.chunk__len {
  font-size: 10.5px;
}
.chunk__toggle {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 7px;
  border: 1px solid var(--af-line);
  border-radius: 999px;
  background: #fff;
  color: var(--af-ink-3);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}
.chunk__toggle:hover {
  border-color: var(--af-primary-light-5);
  color: var(--af-primary);
}
/* 正文是 Markdown 渲染出来的块级结构，-webkit-line-clamp 对块级子元素不生效，
   折叠只能用 max-height 截断（约 5 行） */
.chunk__body {
  font-size: 12.5px;
  cursor: pointer;
}
.chunk__body.is-clamp {
  max-height: 7.4em;
  overflow: hidden;
  position: relative;
}
.chunk__body.is-clamp::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 1.8em;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), #fff 72%);
  pointer-events: none;
}
.chunks__more {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
  font-size: 12px;
}

.empty-ico {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 13px;
  border-radius: 16px;
  color: #8b83ee;
  background: linear-gradient(135deg, #f0edfe, #e7f2fb);
}
.af-empty h3 {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--af-ink-1);
}
.af-empty p {
  margin: 0 0 16px;
  font-size: 12.5px;
}

@media (max-width: 760px) {
  .metrics {
    grid-template-columns: 1fr;
  }
  .hero__actions {
    width: 100%;
  }
  .chunks__tools {
    width: 100%;
  }
}
</style>
