/** 展示层的小工具，纯函数，不碰 DOM。 */

/** 字节 → 人类可读。1024 进制，保留 1 位小数。 */
export function formatSize(bytes) {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = n
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${i === 0 ? value : value.toFixed(1)} ${units[i]}`
}

/** 千分位。 12345 → 12,345 */
export function formatNumber(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString('zh-CN')
}

/**
 * 后端返回的是不带时区的 `2026-10-07T15:10:00`（MySQL DATETIME），
 * 直接 new Date() 会被当本地时间 —— 后端和浏览器同机，这样处理正好。
 */
export function formatDateTime(value) {
  if (!value) return '-'
  const d = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}`
}

/** 相对时间，用于列表里的「刚刚 / 3 分钟前」 */
export function fromNow(value) {
  if (!value) return '-'
  const d = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return '-'
  const diff = Date.now() - d.getTime()
  if (diff < 0) return formatDateTime(value)
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour} 小时前`
  const day = Math.floor(hour / 24)
  if (day < 30) return `${day} 天前`
  return formatDateTime(value)
}

/** 文件名中间省略，保住后缀 */
export function ellipsisMiddle(text, head = 10, tail = 8) {
  const s = String(text || '')
  if (s.length <= head + tail + 3) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

/** 从文件名取后缀（小写，带点） */
export function fileExt(name) {
  const s = String(name || '')
  const i = s.lastIndexOf('.')
  return i > -1 ? s.slice(i).toLowerCase() : ''
}

/** 后缀 → Element Plus tag 的颜色类型 */
export function extTagType(ext) {
  switch (ext) {
    case '.pdf':
      return 'danger'
    case '.doc':
    case '.docx':
      return 'primary'
    case '.xls':
    case '.xlsx':
      return 'success'
    case '.md':
      return 'warning'
    case '.txt':
      return 'info'
    default:
      return 'info'
  }
}

/** 稳定地把字符串映射成 0~5 的下标，用来给知识库分配一个固定色调 */
export function hueIndex(seed, total = 6) {
  const s = String(seed ?? '')
  let hash = 0
  for (let i = 0; i < s.length; i += 1) {
    hash = (hash * 31 + s.charCodeAt(i)) % 100000
  }
  return hash % total
}
