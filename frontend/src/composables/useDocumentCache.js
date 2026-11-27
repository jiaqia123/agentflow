/**
 * 文档详情页需要的两类跨页面数据。
 *
 * 后端**没有** `GET /document/{id}`，也没有「按文档查已入库片段」的接口：
 *   - `/document/list` 是唯一能拿到文档行的接口，只支持按 knowledge_id / keyword 过滤，
 *     不能按 id 查单条，也不返回正文（正文在 documents_chunks 表里）。
 *
 * 于是这里存两样东西：
 *
 * 1 文档行（内存级，刷新即失效）
 *   列表页点「查看」时把那一行塞进来，详情页直接取，省一次全量翻页扫描。
 *   刷新 / 手输 URL 时缓存为空，详情页会退化成扫 `/document/list` 兜底。
 *
 * 2 **入库快照**（localStorage 持久化，刷新仍在）—— 这个是关键
 *   /document/store 返回的 success[] 里有 document_id 和 chunk_count，
 *   而入库用的 separator / chunk_size / chunk_overlap 没有存进数据库。
 *   详情页若拿默认参数去 /document/split 重新切一遍，切出来的块数会**跟入库时不一样**
 *   （实测同一份文档 chunk_size=512 → 1 块，=256 → 5 块），
 *   于是就出现「列表说 4 块、详情页只有 1 块」的自相矛盾。
 *   所以入库成功那一刻，把**真实的片段 + 当时的参数**按 document_id 存下来，
 *   详情页优先读它 —— 这才是准确反映库里内容的那份数据。
 *
 * 容量控制：localStorage 默认只有 5MB 左右，一份大文档的片段正文可能几百 KB，
 * 所以同时限制「条数」和「总字节数」，超了就按入库时间淘汰最旧的。
 *
 * ⚠️ 淘汰顺序必须靠**自增写入序号**，不能只靠 Date.now()：
 *   同一毫秒连续写多份（一次入库多个文件）时时间戳完全相同，
 *   加上 snapshots 的 key 是数字型字符串 —— JS 对这类 key 会按**数值升序**重排，
 *   不保留插入顺序，于是「淘汰最旧的」会退化成「随机淘汰」，可能把用户刚存的那条踢掉。
 */
import { reactive } from 'vue'

const SNAPSHOT_KEY = 'af_doc_snapshots_v1'
const MAX_ENTRIES = 24
const MAX_BYTES = 400 * 1024

const cache = reactive({})
const snapshots = reactive({})
/** 单调递增的写入序号，只用于淘汰排序（保证「后写的不会被先写的挤掉」） */
let writeSeq = 0

// ---------------------------------------------------------------- 文档行缓存

/** 记住一行文档（传进来的是 /document/list 的 items 元素） */
export function rememberDocument(doc) {
  if (doc?.id === undefined || doc?.id === null) return
  cache[doc.id] = doc
}

/** 取缓存的行，没有则返回 null */
export function getCachedDocument(id) {
  return cache[id] || null
}

export function forgetDocument(id) {
  delete cache[id]
}

// ---------------------------------------------------------------- 入库快照

/** localStorage 在隐私模式 / 配额满时会抛异常，所有读写都必须兜住 */
function safeGet(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key, value) {
  try {
    window.localStorage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

function loadFromStorage() {
  const raw = safeGet(SNAPSHOT_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      Object.assign(snapshots, parsed)
      // 续上已有的序号，避免刷新后又从 0 开始、跟旧数据撞号
      writeSeq = Object.values(snapshots).reduce(
        (max, s) => Math.max(max, Number(s?.seq) || 0),
        0
      )
    }
  } catch {
    // 数据坏了就当没有，不影响页面
    try {
      window.localStorage.removeItem(SNAPSHOT_KEY)
    } catch {
      /* 忽略 */
    }
  }
}

/** 超出条数 / 字节上限时，按写入顺序淘汰最旧的 */
function persist() {
  const entries = Object.entries(snapshots).sort((a, b) => {
    const bySeq = (Number(b[1]?.seq) || 0) - (Number(a[1]?.seq) || 0)
    if (bySeq !== 0) return bySeq
    return (b[1]?.storedAt || 0) - (a[1]?.storedAt || 0)
  })

  const kept = {}
  let bytes = 0
  entries.slice(0, MAX_ENTRIES).forEach(([id, snap]) => {
    const size = JSON.stringify(snap).length
    if (bytes + size > MAX_BYTES && Object.keys(kept).length) return
    bytes += size
    kept[id] = snap
  })

  Object.keys(snapshots).forEach((id) => {
    if (!kept[id]) delete snapshots[id]
  })

  safeSet(SNAPSHOT_KEY, JSON.stringify(kept))
}

loadFromStorage()

/**
 * 记下「入库那一刻」的真实片段与参数。
 * @param {number} documentId /document/store 返回的 success[].document_id
 * @param {{params: object, chunks: Array, charCount: number, chunkCount: number}} data
 */
export function rememberSnapshot(documentId, data) {
  if (!documentId) return
  if (!Array.isArray(data?.chunks) || !data.chunks.length) return
  writeSeq += 1
  snapshots[documentId] = {
    params: { ...(data.params || {}) },
    chunks: data.chunks,
    charCount: Number(data.charCount) || 0,
    chunkCount: Number(data.chunkCount) || data.chunks.length,
    storedAt: Date.now(),
    seq: writeSeq
  }
  persist()
}

/**
 * 取入库快照。
 *
 * ⚠️ 会跟文档行做一致性校验：库里记的 chunk_count / char_count
 *    与快照对不上，说明这份文档被重新入库过，旧快照已经过期，直接丢弃。
 */
export function getSnapshot(documentId, doc) {
  const snap = snapshots[documentId]
  if (!snap) return null
  if (doc) {
    if (snap.chunkCount && doc.chunk_count && snap.chunkCount !== doc.chunk_count) return null
    if (snap.charCount && doc.char_count && snap.charCount !== doc.char_count) return null
  }
  return snap
}

export function forgetSnapshot(documentId) {
  if (!snapshots[documentId]) return
  delete snapshots[documentId]
  persist()
}

/** 有几个文档直接刷新的用户，可以靠它知道「本机存了几份快照」 */
export function snapshotCount() {
  return Object.keys(snapshots).length
}
