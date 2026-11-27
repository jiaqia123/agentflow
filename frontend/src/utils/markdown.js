/**
 * 极简 Markdown → HTML 渲染器（无外部依赖）。
 *
 * ── 为什么不用 marked / markdown-it ───────────────────────────────────────────
 * 1 安全：本项目的文本来源是**用户上传的文档**和**大模型输出**，都不可信。
 *   marked 默认不消毒，必须再配 DOMPurify 才安全。
 *   本实现走「**先整体转义 HTML，再解析 Markdown**」的路线 ——
 *   源文本里的 `<script>` / `<img onerror=...>` 在解析前就已经变成 `&lt;script&gt;`，
 *   输出的所有标签都由本文件自己拼出来，**结构上不存在注入面**，不需要额外消毒库。
 * 2 依赖：项目刻意保持零第三方 UI 依赖（未装 axios / pinia / 图标包），不为一个渲染器破例。
 *
 * ── 支持的语法 ────────────────────────────────────────────────────────────────
 * 块级：ATX 标题 #~######、围栏代码块 ``` / ~~~（带语言标记）、引用 >、
 *      无序/有序列表（支持缩进嵌套）、表格（支持 :--: 对齐）、分隔线 ---、段落
 * 行内：行内代码 `x`、加粗 **x** / __x__、斜体 *x* / _x_、删除线 ~~x~~、
 *      链接 [文本](url)、图片 ![alt](url)、自动链接 <https://…>、反斜杠转义
 *
 * ── 与标准 Markdown 的三处**有意**不同 ───────────────────────────────────────
 * 1 段落内的单换行渲染成 <br>，不按 GFM 折叠成空格。
 *   理由：这里渲染的是中文文档片段和大模型回答，作者敲的换行就是他要的排版，
 *   折叠掉反而会让「一行一条」的内容糊成一段。
 * 2 不做 HTML 直通（标准允许内嵌 HTML）。同上，安全优先。
 * 3 URL 走白名单（http/https/mailto/tel/相对路径），`javascript:` `data:` 一律不渲染成链接。
 *
 * ── 实现上的三个坑（都踩过了，别再退回去）─────────────────────────────────
 * · 只允许在**最外层转义一次**：内部所有函数一律接收「已转义的行数组」，
 *   否则列表项里的文本会被转义两遍，`&` 变成 `&amp;amp;`。
 *   副作用：块级正则要针对**转义后**的形态写 —— 引用行是 `&gt;` 不是 `>`。
 * · 行内占位符必须带**调用序号**：链接文字、加粗内容都要递归调 inline()，
 *   若占位符只写 `\u0000N\u0000`，内层递归的还原会把外层的占位符也一起解析掉，拿到错误内容。
 * · 行内还原必须**循环替换到没有残留**：replace 不回头扫替换进去的文本，
 *   而暂存的 HTML 自己可能还含着本层占位符（如 `**外层 `code` 内层**`）。
 */

const ESCAPE_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
}

/** 把 HTML 元字符全部转义。**只在最外层调用一次。** */
function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (ch) => ESCAPE_MAP[ch])
}

/**
 * URL 白名单：只放行 http/https/相对路径/锚点/邮件/电话。
 * 挡掉 javascript: / data: / vbscript: 这些能执行脚本的协议 ——
 * 文档里写 `[点我](javascript:alert(1))` 不会变成可点的炸弹。
 */
function safeUrl(raw) {
  const url = String(raw ?? '').trim()
  if (!url) return ''
  if (/^(https?:|mailto:|tel:)/i.test(url)) return url
  if (/^[./#?]/.test(url)) return url
  return ''
}

/** 图片额外限制：外链 SVG 可能带脚本，直接不渲染 */
function safeImageUrl(raw) {
  const url = safeUrl(raw)
  if (!url) return ''
  if (/\.svg(\?|#|$)/i.test(url)) return ''
  return url
}

// ---------------------------------------------------------------- 行内解析

/** 每次 inline() 调用一个唯一序号，避免嵌套递归时互相解析对方的占位符 */
let inlineCallSeq = 0

/**
 * 行内语法。用「占位符暂存」处理嵌套：每处理一层就把生成的标签换成占位符，
 * 后续规则不会误伤已生成的标签（例如 `**x**` 不会被斜体规则再吃一次）。
 */
function inline(text) {
  const seq = (inlineCallSeq += 1)
  const tokens = []
  const marker = `\u0000${seq}:`
  const stash = (html) => {
    tokens.push(html)
    return `${marker}${tokens.length - 1}\u0000`
  }

  let out = text

  // 0 反斜杠转义：\* 输出字面量 *（必须最先做，否则会被后续规则当成语法）
  out = out.replace(/\\([\\`*_{}[\]()#+\-.!>~|])/g, (_, ch) => stash(escapeHtml(ch)))

  // 1 行内代码：内容已是转义后文本，直接包 <code>
  out = out.replace(/`([^`\n]+)`/g, (_, code) => stash(`<code class="md-code">${code}</code>`))

  // 2 图片 ![alt](url)（title 已被转义成 &quot;，一起吃掉）
  out = out.replace(
    /!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^)]*&quot;)?\)/g,
    (whole, alt, url) => {
      const src = safeImageUrl(url)
      if (!src) return whole
      return stash(`<img class="md-img" src="${src}" alt="${alt}" loading="lazy" />`)
    }
  )

  // 3 链接 [文本](url)，链接文字允许嵌套行内语法
  out = out.replace(
    /\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^)]*&quot;)?\)/g,
    (whole, label, url) => {
      const href = safeUrl(url)
      if (!href) return whole
      return stash(
        `<a class="md-link" href="${href}" target="_blank" rel="noopener noreferrer">${inline(label)}</a>`
      )
    }
  )

  // 4 自动链接：<https://x> 已被转义成 &lt;https://x&gt;
  out = out.replace(/&lt;((?:https?:\/\/|mailto:)[^\s&]+)&gt;/g, (_, url) =>
    stash(`<a class="md-link" href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`)
  )

  // 5 加粗（先做，避免 __ 被斜体规则按单个下划线吃掉）
  out = out.replace(/\*\*([\s\S]+?)\*\*/g, (_, t) => stash(`<strong>${inline(t)}</strong>`))
  out = out.replace(/(^|\s)__([^\s_][\s\S]*?)__(?!\w)/g, (_, pre, t) => pre + stash(`<strong>${inline(t)}</strong>`))

  // 6 斜体：开头的 * 后面必须紧跟非空白，否则 `2 * 3 * 4` 这种算式会被误判
  out = out.replace(/(^|[^*\w])\*([^\s*][^*\n]*?)\*(?!\*)/g, (_, pre, t) => pre + stash(`<em>${inline(t)}</em>`))
  out = out.replace(/(^|[^\w])_([^\s_][^_\n]*?)_(?!\w)/g, (_, pre, t) => pre + stash(`<em>${inline(t)}</em>`))

  // 7 删除线
  out = out.replace(/~~([\s\S]+?)~~/g, (_, t) => stash(`<del>${inline(t)}</del>`))

  // 8 还原本层占位符（只认自己的序号，不会碰到外层或内层的）
  //
  // ⚠️ 必须**循环替换到没有残留**：`String.replace` 不会回头扫描被替换进去的文本，
  //   而 tokens 里存的 HTML 可能**自己还含着本层的占位符**
  //   （例：`**外层 `code` 内层**` —— `<strong>` 里嵌着 `<code>` 的占位符）。
  //   单趟替换会让内层那个占位符原样留在页面上（页面上会出现 `\u0000N:M\u0000` 这种乱码）。
  const markerHead = `\u0000${seq}:`
  const mine = new RegExp(`\\u0000${seq}:(\\d+)\\u0000`, 'g')
  // 用 indexOf 判断循环条件：带 g 的正则用 test() 会推进 lastIndex，下一次 replace 会跳过头几个匹配
  for (let guard = 0; guard < 20 && out.includes(markerHead); guard += 1) {
    out = out.replace(mine, (_, i) => tokens[Number(i)] ?? '')
  }
  return out
}

// ---------------------------------------------------------------- 块级解析

const RE_HEADING = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/
const RE_HR = /^ {0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/
const RE_FENCE = /^ {0,3}(`{3,}|~{3,})\s*([\w+#.-]*)\s*$/
const RE_QUOTE = /^ {0,3}(?:&gt;|>)\s?(.*)$/
const RE_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/
const RE_INDENT = /^\s{2,}\S/

function hasPipe(line) {
  return line.includes('|') && line.trim() !== ''
}

function splitTableRow(line) {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').map((c) => c.trim())
}

/** 表格分隔行：| --- | :--: | 之类 */
function isTableDelim(line) {
  const cells = splitTableRow(line)
  if (!cells.length) return false
  return cells.every((c) => /^:?-{1,}:?$/.test(c))
}

function parseAligns(line) {
  return splitTableRow(line).map((c) => {
    const left = c.startsWith(':')
    const right = c.endsWith(':')
    if (left && right) return 'center'
    if (right) return 'right'
    if (left) return 'left'
    return ''
  })
}

function alignAttr(a) {
  return a ? ` style="text-align:${a}"` : ''
}

function renderTable(rows, aligns) {
  const head = rows[0]
  const body = rows.slice(1)
  const th = head.map((c, i) => `<th${alignAttr(aligns[i])}>${inline(c)}</th>`).join('')
  const tb = body
    .map(
      (r) =>
        `<tr>${head.map((_, i) => `<td${alignAttr(aligns[i])}>${inline(r[i] ?? '')}</td>`).join('')}</tr>`
    )
    .join('')
  return (
    '<div class="md-table-wrap"><table class="md-table">' +
    `<thead><tr>${th}</tr></thead>` +
    (tb ? `<tbody>${tb}</tbody>` : '') +
    '</table></div>'
  )
}

/** 判断某一行是不是块级结构的起点（段落据此断行） */
function startsBlock(lines, idx) {
  const cur = lines[idx]
  if (cur === undefined) return false
  if (cur.trim() === '') return true // 空行 = 段落结束
  if (RE_HEADING.test(cur) || RE_FENCE.test(cur) || RE_HR.test(cur)) return true
  if (RE_QUOTE.test(cur) || RE_LIST.test(cur)) return true
  return hasPipe(cur) && idx + 1 < lines.length && isTableDelim(lines[idx + 1])
}

/**
 * 列表解析：用一个「缩进栈」实现嵌套。
 * 缩进比上一个项更深的列表项不另起一个 item，而是原样塞进上一项的 lines，
 * 交给递归的 parseBlocks 处理 —— 这样 `- a` / `  - b` 会正确变成嵌套的 <ul>。
 */
function parseList(lines, start, out) {
  const items = []
  let i = start

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      // 空行后如果还是列表项（缩进不小于当前项）就续上，否则列表结束
      const next = lines[i + 1]
      const nextMatch = next ? next.match(RE_LIST) : null
      if (nextMatch && nextMatch[1].replace(/\t/g, '    ').length >= (items.at(-1)?.indent ?? 0)) {
        i += 1
        continue
      }
      break
    }

    const m = line.match(RE_LIST)
    if (m) {
      const indent = m[1].replace(/\t/g, '    ').length
      if (items.length && indent > items.at(-1).indent) {
        // 更深缩进 → 属于上一项的子列表，原样留给递归
        items.at(-1).lines.push(line)
        i += 1
        continue
      }
      items.push({
        indent,
        ordered: /\d/.test(m[2]),
        start: Number.parseInt(m[2], 10) || 1,
        lines: [m[3]]
      })
      i += 1
      continue
    }

    // 续行：比当前项缩进更深的普通文本，接到当前项上
    if (RE_INDENT.test(line) && items.length) {
      items.at(-1).lines.push(line.trim())
      i += 1
      continue
    }

    break
  }

  const ordered = items[0]?.ordered
  const startNo = items[0]?.start ?? 1
  const tag = ordered ? 'ol' : 'ul'
  const attr = ordered && startNo !== 1 ? ` start="${startNo}"` : ''
  const html = items.map((it) => `<li>${parseBlocks(it.lines, true)}</li>`).join('')

  out.push(`<${tag}${attr} class="md-list">${html}</${tag}>`)
  return i
}

/**
 * 主解析循环。
 * @param {string[]} lines **已转义**的行数组（内部递归也传已转义的行，绝不重复转义）
 * @param {boolean} loose 松散模式（列表项内部）：纯文本不再包 <p>
 */
function parseBlocks(lines, loose = false) {
  const out = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // 空行
    if (line.trim() === '') {
      i += 1
      continue
    }

    // 围栏代码块
    const fence = line.match(RE_FENCE)
    if (fence) {
      const marker = fence[1][0]
      const lang = fence[2] || ''
      const closeRe = new RegExp(`^ {0,3}\\${marker}{3,}\\s*$`)
      const body = []
      i += 1
      while (i < lines.length && !closeRe.test(lines[i])) {
        body.push(lines[i])
        i += 1
      }
      i += 1 // 跳过结束围栏（或已到文件结尾）
      const cls = lang ? ` class="md-pre language-${lang}"` : ' class="md-pre"'
      out.push(`<pre${cls}><code>${body.join('\n')}</code></pre>`)
      continue
    }

    // 分隔线（必须排在列表之前，否则 `---` 会被当成列表项）
    if (RE_HR.test(line)) {
      out.push('<hr class="md-hr" />')
      i += 1
      continue
    }

    // 标题
    const head = line.match(RE_HEADING)
    if (head) {
      const level = head[1].length
      out.push(`<h${level} class="md-h">${inline(head[2])}</h${level}>`)
      i += 1
      continue
    }

    // 表格：当前行有 |，且下一行是分隔行
    if (hasPipe(line) && i + 1 < lines.length && isTableDelim(lines[i + 1])) {
      const rows = [splitTableRow(line)]
      const aligns = parseAligns(lines[i + 1])
      i += 2
      while (i < lines.length && hasPipe(lines[i])) {
        rows.push(splitTableRow(lines[i]))
        i += 1
      }
      out.push(renderTable(rows, aligns))
      continue
    }

    // 引用：连续 > 行合并后递归
    if (RE_QUOTE.test(line)) {
      const buf = []
      while (i < lines.length && RE_QUOTE.test(lines[i])) {
        buf.push(lines[i].match(RE_QUOTE)[1])
        i += 1
      }
      out.push(`<blockquote class="md-quote">${parseBlocks(buf)}</blockquote>`)
      continue
    }

    // 列表
    if (RE_LIST.test(line)) {
      i = parseList(lines, i, out)
      continue
    }

    // 段落：吃到空行或下一个块级起点
    const buf = [line]
    i += 1
    while (i < lines.length && !startsBlock(lines, i)) {
      buf.push(lines[i])
      i += 1
    }
    const content = buf.map((l) => inline(l)).join('<br />')
    out.push(loose ? content : `<p class="md-p">${content}</p>`)
  }

  return out.join('')
}

// ---------------------------------------------------------------- 对外接口

/** Markdown → HTML。输入不可信，输出可直接交给 v-html。 */
export function renderMarkdown(source) {
  const lines = String(source ?? '')
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(escapeHtml) // ← 全局唯一一次转义
  return parseBlocks(lines)
}

/**
 * 判断一段文本「值不值得」按 Markdown 渲染。
 *
 * 纯中文段落、日志、代码片段之类没有 Markdown 语法的文本，
 * 走 Markdown 会把换行和空格改掉 —— 那种内容应该原样保留（pre-wrap）。
 * 所以这里只在**确实出现 Markdown 结构**时才返回 true。
 */
export function isMarkdownLike(source) {
  const text = String(source ?? '')
  if (!text.trim()) return false

  return (
    /^ {0,3}#{1,6}\s+\S/m.test(text) || // 标题
    /```|~~~/.test(text) || // 围栏代码块
    /^ {0,3}(?:&gt;|>)\s?\S/m.test(text) || // 引用
    /^ {0,3}([-*+]|\d{1,9}[.)])\s+\S/m.test(text) || // 列表
    /^ {0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/m.test(text) || // 分隔线
    /\*\*[^\s*][\s\S]*?\*\*/.test(text) || // 加粗
    /~~[^\s~][\s\S]*?~~/.test(text) || // 删除线
    /`[^`\n]+`/.test(text) || // 行内代码
    /!\[[^\]]*\]\([^)\s]+\)/.test(text) || // 图片
    /\[[^\]]+\]\([^)\s]+\)/.test(text) || // 链接
    /\n\s*\|[^\n]*\|/.test(text) // 表格
  )
}

/** 纯文本 → 安全 HTML（换行交给 CSS 的 white-space: pre-wrap 处理） */
export function renderPlain(source) {
  return escapeHtml(source)
}

/**
 * 统一入口：按内容自动选择渲染方式。
 * @returns {{ html: string, kind: 'markdown' | 'plain' }}
 */
export function renderSmart(source) {
  const text = String(source ?? '')
  const markdown = isMarkdownLike(text)
  return {
    html: markdown ? renderMarkdown(text) : renderPlain(text),
    kind: markdown ? 'markdown' : 'plain'
  }
}
