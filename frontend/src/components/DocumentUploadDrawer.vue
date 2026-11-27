<script setup>
/**
 * 文档上传入库抽屉：上传 → 切分（填参数）→ 入库。
 *
 * 交互与后端三步流水线一一对应，每步一个按钮，用户不会漏掉切分参数：
 *   1 选择文件后点「上传文件」    POST /document/upload  落盘，拿到 new_filename
 *   2 点「切分」→ 弹参数对话框 → 确认后 POST /document/split
 *                             只切分，返回片段列表（不向量化、不入库），用来预览
 *   3 点「确认入库」             POST /document/store    用同一套参数重新切一遍，双写 MySQL + Chroma
 *
 * 关键约束（写在 UI 上也写在注释里）：
 *   - 后缀白名单 .pdf .doc .docx .txt .md .xls .xlsx；单文件 ≤50MB
 *   - 切分参数的单位是 **token**，且重叠度必须小于分段长度
 *   - 同一个知识库里已经入库过的同一文件，/store 会跳过，不会重复切向量
 *   - 单个文件失败不影响其他文件
 *
 * ⚠️ 入库成功那一刻会把「真实片段 + 当时参数」写进 useDocumentCache 的**入库快照**。
 *    因为后端没有存这次用的切分参数，详情页只能拿默认参数重新切，
 *    切出来的块数会跟入库时对不上（出现过「列表说 4 块、详情页只有 1 块」）。
 *    快照就是详情页的准数据源，别把这段删了。
 */
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import MarkdownBlock from '@/components/MarkdownBlock.vue'
import SplitParamsDialog from '@/components/SplitParamsDialog.vue'
import { splitDocument, storeDocuments, uploadDocument } from '@/api/document'
import { rememberSnapshot } from '@/composables/useDocumentCache'
import { formatNumber, formatSize, fileExt, extTagType } from '@/utils/format'
import { DEFAULT_SPLIT_PARAMS, separatorLabel, separatorPreview } from '@/utils/split'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 目标知识库；必填，/store 需要 knowledge_id */
  knowledge: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'stored'])

const ACCEPT = '.pdf,.doc,.docx,.txt,.md,.xls,.xlsx'
const MAX_SIZE = 50 * 1024 * 1024

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const params = reactive({ ...DEFAULT_SPLIT_PARAMS })
const paramsVisible = ref(false)

/** files 里每一项：{ uid, file, name, size, status, new_filename, url, chunks, splitParams, error } */
const files = ref([])
const busy = ref(false)
const result = ref(null)
const expanded = ref(new Set())

const uploadRef = ref(null)

const STATUS = {
  pending: { text: '待上传', type: 'info' },
  uploading: { text: '上传中', type: 'info' },
  uploaded: { text: '已上传·待切分', type: 'info' },
  splitting: { text: '切分中', type: 'warning' },
  ready: { text: '已切分', type: 'success' },
  storing: { text: '入库中', type: 'warning' },
  stored: { text: '已入库', type: 'success' },
  skipped: { text: '已存在·跳过', type: 'info' },
  failed: { text: '失败', type: 'danger' }
}

const hasFiles = computed(() => files.value.length > 0)

/** 还没落盘的（上传失败也算）→ 可以（重新）上传 */
const isUploadable = (f) =>
  !f.new_filename && (f.status === 'pending' || f.status === 'failed')
/** 已落盘、可以（重新）切分的 */
const isSplittable = (f) =>
  Boolean(f.new_filename) && ['uploaded', 'ready', 'failed'].includes(f.status)

const uploadableCount = computed(() => files.value.filter(isUploadable).length)
const splittableCount = computed(() => files.value.filter(isSplittable).length)
const readyCount = computed(() => files.value.filter((f) => f.status === 'ready').length)

/** el-steps 的当前步：0 选文件 / 1 上传 / 2 切分 / 3 入库 */
const step = computed(() => {
  if (!hasFiles.value) return 0
  if (files.value.some((f) => f.status === 'pending' || f.status === 'uploading')) return 1
  if (files.value.some((f) => f.status === 'uploaded' || f.status === 'splitting')) return 2
  return 3
})

/** 底部随时告诉用户「下一步该点哪个按钮」 */
const footerTip = computed(() => {
  if (!hasFiles.value) return '先选择文件'
  if (uploadableCount.value) return `还有 ${uploadableCount.value} 个文件没落盘，点「上传文件」`
  if (!readyCount.value && splittableCount.value) return '文件已落盘，点「切分」填写参数后开始切分'
  if (readyCount.value) return `已切分 ${readyCount.value} 个，点「确认入库」完成流程`
  return '流程已完成'
})

// 抽屉关闭时保留结果让用户看一眼，重新打开才清空
watch(visible, (open) => {
  if (open) reset()
})

function reset() {
  files.value = []
  result.value = null
  busy.value = false
  expanded.value = new Set()
  uploadRef.value?.clearFiles?.()
}

function onSelect(uploadFile, uploadFiles) {
  // el-upload 自己维护列表，这里只把「新增的」同步进我们的数据
  const known = new Set(files.value.map((f) => f.uid))
  uploadFiles.forEach((item) => {
    if (known.has(item.uid)) return

    const raw = item.raw
    const ext = fileExt(raw.name)
    if (!ACCEPT.includes(ext)) {
      ElMessage.error(`「${raw.name}」格式不支持，仅支持 ${ACCEPT}`)
      return
    }
    if (raw.size > MAX_SIZE) {
      ElMessage.error(`「${raw.name}」超过 50MB 上限`)
      return
    }
    files.value.push({
      uid: item.uid,
      file: raw,
      name: raw.name,
      size: raw.size,
      status: 'pending',
      new_filename: '',
      url: '',
      chunks: [],
      // 切分成功时把当时的参数一起记下来，入库写快照要用
      splitParams: null,
      error: ''
    })
  })
}

function removeFile(uid) {
  if (busy.value) return
  files.value = files.value.filter((f) => f.uid !== uid)
}

function toggleExpand(idx) {
  const next = new Set(expanded.value)
  if (next.has(idx)) next.delete(idx)
  else next.add(idx)
  expanded.value = next
}

/** 第 1 步：把还没落盘的文件上传到服务器 */
async function uploadFiles() {
  const targets = files.value.filter(isUploadable)
  if (!targets.length) {
    ElMessage.warning('没有待上传的文件')
    return
  }

  busy.value = true
  result.value = null

  for (const item of targets) {
    try {
      item.status = 'uploading'
      item.error = ''
      const up = await uploadDocument(item.file)
      item.new_filename = up.new_filename
      item.url = up.url
      item.status = 'uploaded'
    } catch (err) {
      item.status = 'failed'
      item.error = err.message || '上传失败'
    }
  }

  busy.value = false

  const ok = targets.filter((f) => f.status === 'uploaded').length
  const bad = targets.filter((f) => f.status === 'failed').length
  if (ok && !bad) ElMessage.success(`${ok} 个文件已上传，接下来点「切分」`)
  else if (ok) ElMessage.warning(`${ok} 个已上传，${bad} 个失败`)
}

/** 点「切分」→ 先弹参数对话框，填好确认才会真的开始切 */
function openSplitDialog() {
  if (!splittableCount.value) {
    ElMessage.warning('没有待切分的文件，请先上传')
    return
  }
  paramsVisible.value = true
}

/** 参数对话框确认：写回参数，然后开始切分 */
async function onSplitConfirm(next) {
  Object.assign(params, next)
  await runSplit()
}

/** 第 2 步：按当前参数逐个切分（已入库的不再动） */
async function runSplit() {
  const targets = files.value.filter(isSplittable)
  if (!targets.length) return

  busy.value = true
  result.value = null

  for (const item of targets) {
    item.chunks = []
    try {
      item.status = 'splitting'
      item.error = ''
      const sp = await splitDocument({
        new_filename: item.new_filename,
        separator: params.separator,
        chunk_size: Number(params.chunk_size),
        chunk_overlap: Number(params.chunk_overlap)
      })
      item.chunks = sp.chunks || []
      item.splitParams = { ...params }
      item.status = 'ready'
    } catch (err) {
      item.splitParams = null
      item.status = 'failed'
      item.error = err.message || '切分失败'
    }
  }

  busy.value = false

  const ok = files.value.filter((f) => f.status === 'ready').length
  const bad = targets.filter((f) => f.status === 'failed').length
  if (ok && !bad) ElMessage.success(`切分完成，共 ${targets.length} 个文件，可以预览片段后入库了`)
  else if (bad) ElMessage.warning(`${bad} 个文件切分失败（失败项不会入库）`)
}

/** 第 3 步：把就绪的文件提交入库 */
async function commitStore() {
  const targets = files.value.filter((f) => f.status === 'ready')
  if (!targets.length) {
    ElMessage.warning('没有可入库的文件，请先上传并切分')
    return
  }
  if (!props.knowledge?.id) {
    ElMessage.error('缺少知识库信息')
    return
  }

  busy.value = true
  targets.forEach((f) => {
    f.status = 'storing'
    f.error = ''
  })

  try {
    const res = await storeDocuments({
      knowledge_id: props.knowledge.id,
      files: targets.map((f) => ({
        filename_uuid: f.new_filename,
        filename_original: f.name
      })),
      separator: params.separator,
      chunk_size: Number(params.chunk_size),
      chunk_overlap: Number(params.chunk_overlap)
    })

    result.value = res

    const successIds = new Set((res.success || []).map((s) => s.filename_uuid))
    const skippedIds = new Set(res.skipped || [])
    const failedMap = new Map((res.failed || []).map((f) => [f.filename_uuid, f.reason]))

    // 入库成功的，把「真实片段 + 当时参数」写成入库快照给详情页用
    // （后端没存这次用的参数，详情页拿默认参数重新切会切出对不上的块数）
    const byUuid = new Map(targets.map((f) => [f.new_filename, f]))
    ;(res.success || []).forEach((s) => {
      const item = byUuid.get(s.filename_uuid)
      if (!item) return
      rememberSnapshot(s.document_id, {
        params: item.splitParams || { ...params },
        chunks: item.chunks,
        charCount: s.char_count,
        chunkCount: s.chunk_count
      })
    })

    targets.forEach((f) => {
      if (successIds.has(f.new_filename)) f.status = 'stored'
      else if (skippedIds.has(f.new_filename)) f.status = 'skipped'
      else if (failedMap.has(f.new_filename)) {
        // 退回「已切分」：片段还在，改参数或换时机再点一次「确认入库」即可重试
        f.status = 'ready'
        f.error = `入库失败：${failedMap.get(f.new_filename) || '未知原因'}`
      }
    })

    if (res.success_count) {
      ElMessage.success(`入库完成：成功 ${res.success_count} 份，共 ${res.chunk_count} 个片段`)
      emit('stored')
    } else if (res.skipped_count) {
      ElMessage.info('所选文件均已入库过，已跳过')
    } else {
      ElMessage.error('全部入库失败，请查看列表里的原因')
    }
  } catch (err) {
    ElMessage.error(err.message || '入库请求失败')
    targets.forEach((f) => {
      f.status = 'ready' // 整体失败（如 403/404），退回就绪状态让用户能重试
    })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <el-drawer
    v-model="visible"
    :size="760"
    :close-on-click-modal="!busy"
    :close-on-press-escape="!busy"
    class="upload-drawer"
  >
    <template #header>
      <div class="drawer-head">
        <span class="drawer-head__ico" aria-hidden="true"><AppIcon name="upload" :size="16" /></span>
        <span class="drawer-head__txt">
          <b>上传文档入库</b>
          <i v-if="knowledge">
            目标知识库：{{ knowledge.name }}（#{{ knowledge.id }}）
          </i>
        </span>
      </div>
    </template>

    <!-- 步骤指示 -->
    <el-steps :active="step" simple class="steps">
      <el-step title="选择文件" />
      <el-step title="上传" />
      <el-step title="切分" />
      <el-step title="入库" />
    </el-steps>

    <!-- 当前切分参数（只读摘要，点「切分」时可在弹窗里改） -->
    <div class="summary">
      <span class="summary__ico" aria-hidden="true"><AppIcon name="filter" :size="14" /></span>
      <span class="summary__main">
        切分方式 <b>{{ separatorLabel(params.separator) }}</b>
        <em class="af-mono">{{ separatorPreview(params.separator) }}</em>
        <i>·</i>
        长度 <b>{{ params.chunk_size }}</b> token
        <i>·</i>
        重叠 <b>{{ params.chunk_overlap }}</b>
      </span>
      <span class="summary__tip">点底部「切分」可修改</span>
    </div>

    <!-- 选文件 -->
    <el-upload
      ref="uploadRef"
      class="drop"
      drag
      multiple
      :accept="ACCEPT"
      :auto-upload="false"
      :show-file-list="false"
      :on-change="onSelect"
      :disabled="busy"
    >
      <div class="drop__inner">
        <span class="drop__ico" aria-hidden="true"><AppIcon name="upload" :size="22" /></span>
        <p class="drop__main">把文件拖到这里，或<em>点击选择</em></p>
        <p class="drop__sub">支持 {{ ACCEPT.replaceAll(',', ' / ') }}，单个文件 ≤ 50MB</p>
        <p class="drop__flow">选好后依次点：上传文件 → 切分（填参数）→ 确认入库</p>
      </div>
    </el-upload>

    <!-- 文件列表 -->
    <div v-if="hasFiles" class="list">
      <div class="list__head">
        <span>已选 {{ files.length }} 个文件</span>
        <div class="list__head-right">
          <span v-if="readyCount" class="ready-badge">{{ readyCount }} 个可入库</span>
          <el-button link type="primary" size="small" :disabled="busy" @click="reset">
            清空
          </el-button>
        </div>
      </div>

      <ul class="list__body">
        <li v-for="(f, idx) in files" :key="f.uid" class="file">
          <div class="file__row">
            <el-tag :type="extTagType(fileExt(f.name))" size="small" effect="light" class="file__ext">
              {{ fileExt(f.name).replace('.', '') || '?' }}
            </el-tag>

            <span class="file__main">
              <b :title="f.name">{{ f.name }}</b>
              <i>
                {{ formatSize(f.size) }}
                <template v-if="f.new_filename">
                  · <span class="af-mono">{{ f.new_filename }}</span>
                </template>
              </i>
            </span>

            <el-tag :type="STATUS[f.status].type" size="small" effect="plain" class="file__status">
              {{ STATUS[f.status].text }}
            </el-tag>

            <el-button
              v-if="f.chunks.length"
              link
              size="small"
              :disabled="busy"
              @click="toggleExpand(idx)"
            >
              {{ f.chunks.length }} 片段
              <AppIcon
                name="chevronRight"
                :size="12"
                :style="{
                  marginLeft: '3px',
                  transform: expanded.has(idx) ? 'rotate(90deg)' : 'none',
                  transition: 'transform .18s ease'
                }"
              />
            </el-button>

            <el-button
              link
              type="danger"
              size="small"
              :disabled="busy"
              title="移除"
              @click="removeFile(f.uid)"
            >
              <AppIcon name="trash" :size="14" />
            </el-button>
          </div>

          <p v-if="f.error" class="file__error">
            <AppIcon name="warning" :size="13" style="margin-right: 4px" />
            {{ f.error }}
          </p>

          <!-- 切分预览（按 Markdown 渲染，跟详情页的显示保持一致） -->
          <div v-if="expanded.has(idx) && f.chunks.length" class="chunks">
            <div v-for="c in f.chunks" :key="c.index" class="chunk">
              <span class="chunk__idx">#{{ c.index }}</span>
              <span class="chunk__text">
                <MarkdownBlock :source="c.text" compact />
              </span>
              <span class="chunk__pos af-mono">{{ c.char_start }}~{{ c.char_end }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <!-- 入库结果 -->
    <div v-if="result" class="result">
      <h4>入库结果</h4>
      <div class="result__grid">
        <span class="ok"><b>{{ result.success_count }}</b> 成功</span>
        <span class="skip"><b>{{ result.skipped_count }}</b> 跳过</span>
        <span class="bad"><b>{{ result.failed_count }}</b> 失败</span>
        <span class="chunk"><b>{{ formatNumber(result.chunk_count) }}</b> 新片段</span>
      </div>
      <p class="result__meta">
        知识库「{{ knowledge?.name }}」当前共
        <b>{{ formatNumber(result.document_num) }}</b> 份文档 ·
        <b>{{ formatNumber(result.str_num) }}</b> 字符
        <span class="af-mono result__coll">集合 {{ result.collection }}</span>
      </p>
      <ul v-if="result.failed?.length" class="result__failed">
        <li v-for="(f, i) in result.failed" :key="i">
          <span class="af-mono">{{ f.filename_uuid }}</span> —— {{ f.reason }}
        </li>
      </ul>
    </div>

    <template #footer>
      <div class="footer">
        <span class="footer__tip">{{ footerTip }}</span>
        <div class="footer__btns">
          <el-button :disabled="busy" @click="visible = false">关闭</el-button>
          <el-button :disabled="busy || !uploadableCount" @click="uploadFiles">
            上传文件{{ uploadableCount ? `（${uploadableCount}）` : '' }}
          </el-button>
          <el-button :disabled="busy || !splittableCount" @click="openSplitDialog">
            切分{{ splittableCount ? `（${splittableCount}）` : '' }}
          </el-button>
          <el-button
            type="primary"
            :disabled="busy || !readyCount"
            @click="commitStore"
          >
            确认入库{{ readyCount ? `（${readyCount}）` : '' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-drawer>

  <!-- 切分参数：只有在这里点「确认并开始切分」才会真的切 -->
  <SplitParamsDialog
    v-model="paramsVisible"
    :params="params"
    :loading="busy"
    :hint="`将对 ${splittableCount} 个已上传文件执行切分，确认后立即开始`"
    @confirm="onSplitConfirm"
  />
</template>

<style scoped>
.drawer-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.drawer-head__ico {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: #fff;
  background: linear-gradient(135deg, #6d63f0, #a78bfa);
}
.drawer-head__txt {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
  min-width: 0;
}
.drawer-head__txt b {
  font-size: 14.5px;
  font-weight: 620;
}
.drawer-head__txt i {
  font-style: normal;
  font-size: 11.5px;
  color: var(--af-ink-3);
}

.steps {
  margin-bottom: 14px;
}

/* 切分参数摘要条 */
.summary {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 14px;
  padding: 9px 12px;
  border-radius: var(--af-radius);
  background: #f7f6fd;
  border: 1px dashed #dcd9f1;
}
.summary__ico {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex: none;
  border-radius: 7px;
  color: #6d63f0;
  background: #eceafd;
}
.summary__main {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  color: var(--af-ink-3);
}
.summary__main b {
  color: var(--af-ink-1);
  font-weight: 600;
}
.summary__main em {
  font-style: normal;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 5px;
  background: #eceafd;
  color: #5a50d8;
}
.summary__main i {
  font-style: normal;
  margin: 0 2px;
  color: var(--af-ink-4);
}
.summary__tip {
  flex: none;
  font-size: 11.5px;
  color: var(--af-ink-4);
}

/* 拖拽区 */
.drop :deep(.el-upload-dragger) {
  padding: 22px 16px;
  border: 1.5px dashed #ccc8e2;
  border-radius: var(--af-radius-lg);
  background: linear-gradient(180deg, #fbfaff, #f5f3fc);
  transition: border-color 0.16s ease, background-color 0.16s ease;
}
.drop :deep(.el-upload-dragger:hover) {
  border-color: var(--af-primary);
  background: #f4f2fe;
}
.drop__inner {
  text-align: center;
}
.drop__ico {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin: 0 auto 10px;
  border-radius: 13px;
  color: #8b83ee;
  background: #eceafd;
}
.drop__main {
  margin: 0 0 4px;
  font-size: 13.5px;
  color: var(--af-ink-2);
}
.drop__main em {
  font-style: normal;
  color: var(--af-primary);
  font-weight: 600;
}
.drop__sub {
  margin: 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.drop__flow {
  margin: 9px 0 0;
  padding-top: 9px;
  border-top: 1px dashed #e2dff4;
  font-size: 11.5px;
  color: #7a6fd0;
}

/* 文件列表 */
.list {
  margin-top: 16px;
}
.list__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  color: var(--af-ink-3);
  margin-bottom: 8px;
}
.list__head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ready-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: #e8f7f2;
  color: #0a7a5f;
  font-size: 11.5px;
}
.list__body {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.file {
  border: 1px solid var(--af-line);
  border-radius: var(--af-radius);
  background: #fff;
  padding: 9px 11px;
}
.file__row {
  display: flex;
  align-items: center;
  gap: 9px;
}
.file__ext {
  flex: none;
  text-transform: uppercase;
  width: 42px;
  justify-content: center;
}
.file__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.file__main b {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file__main i {
  font-style: normal;
  font-size: 11px;
  color: var(--af-ink-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file__status {
  flex: none;
}
.file__error {
  display: flex;
  align-items: center;
  margin: 7px 0 0;
  padding: 6px 9px;
  border-radius: 7px;
  background: #fdf0f0;
  color: #a8322f;
  font-size: 11.5px;
  line-height: 1.5;
}

/* 切分预览 */
.chunks {
  margin-top: 9px;
  max-height: 230px;
  overflow-y: auto;
  border-radius: 9px;
  background: #faf9fe;
  border: 1px solid var(--af-line-soft);
  padding: 7px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.chunk {
  display: grid;
  grid-template-columns: 34px 1fr auto;
  gap: 8px;
  align-items: start;
  padding: 6px 8px;
  border-radius: 7px;
  background: #fff;
  border: 1px solid var(--af-line-soft);
}
.chunk__idx {
  font-family: var(--af-font-mono);
  font-size: 11px;
  color: #6d63f0;
  padding-top: 1px;
}
.chunk__text {
  font-size: 12px;
  line-height: 1.6;
  color: var(--af-ink-2);
  word-break: break-word;
  /* 内置 MarkdownBlock 是块级元素，-webkit-line-clamp 对块级子元素不生效，
     这里改用 max-height 截断（3 行 ≈ 3.9em） */
  max-height: 3.9em;
  overflow: hidden;
}
.chunk__pos {
  font-size: 10.5px;
  color: var(--af-ink-4);
  padding-top: 2px;
}

/* 结果 */
.result {
  margin-top: 16px;
  padding: 14px;
  border-radius: var(--af-radius-lg);
  background: linear-gradient(180deg, #f8f7fe, #f3f6fd);
  border: 1px solid #e2dff4;
}
.result h4 {
  margin: 0 0 11px;
  font-size: 13.5px;
  font-weight: 620;
}
.result__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.result__grid span {
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: 9px;
  background: #fff;
  border: 1px solid var(--af-line);
  font-size: 11.5px;
  color: var(--af-ink-3);
}
.result__grid b {
  font-family: var(--af-font-mono);
  font-size: 21px;
  font-weight: 600;
  line-height: 1.25;
}
.result__grid .ok b {
  color: #0a7a5f;
}
.result__grid .skip b {
  color: var(--af-ink-3);
}
.result__grid .bad b {
  color: var(--af-danger);
}
.result__grid .chunk b {
  color: #5a50d8;
}
.result__meta {
  margin: 11px 0 0;
  font-size: 12px;
  color: var(--af-ink-3);
}
.result__meta b {
  color: var(--af-ink-1);
  font-family: var(--af-font-mono);
}
.result__coll {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  background: #eceafd;
  color: #5a50d8;
  font-size: 11px;
}
.result__failed {
  list-style: none;
  margin: 11px 0 0;
  padding: 9px 11px;
  border-radius: 9px;
  background: #fdf0f0;
  color: #a8322f;
  font-size: 11.5px;
  line-height: 1.7;
}

/* 底部 */
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.footer__tip {
  font-size: 12px;
  color: var(--af-ink-3);
}
.footer__btns {
  display: flex;
  gap: 8px;
}

@media (max-width: 760px) {
  .result__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .file__row {
    flex-wrap: wrap;
  }
  .summary {
    flex-wrap: wrap;
  }
  .footer__btns {
    flex-wrap: wrap;
  }
}
</style>

<style>
/* 抽屉宽度不能超过视口，窄屏直接铺满 */
.upload-drawer {
  max-width: 100vw;
}
@media (max-width: 780px) {
  .upload-drawer.el-drawer {
    width: 100% !important;
  }
}
</style>
