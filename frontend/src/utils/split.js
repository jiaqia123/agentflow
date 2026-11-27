/**
 * 文档切分参数：常见切分方式的预设 + 默认值 + 展示工具。
 *
 * ⚠️ 后端的 `separator` 会原样透传给 llama_index 的 SentenceSplitter，
 *    它是**一个普通字符串，不是正则** —— 传 `\n` 就是按换行符切，传 `。` 就是按句号切。
 * ⚠️ `chunk_size` / `chunk_overlap` 的单位是 **token 不是字符**。
 *    llama_index 会先用 separator 把文本切成「句」，再把句子合并到不超过 chunk_size 个 token。
 */

/** 默认参数，与后端 schemas/document.py 的默认值保持一致 */
export const DEFAULT_SPLIT_PARAMS = {
  separator: '\n',
  chunk_size: 512,
  chunk_overlap: 50
}

/**
 * 常见切分方式。value 直接就是提交给后端的 separator 字面量。
 * 用户从下拉里选，不用自己敲转义字符。
 *
 * ⚠️ 实测（llama_index 0.14.25）：separator 是切分优先级里**最低的一层兜底**，
 *    带标点的普通文档无论选哪个结果都一样。详见 SplitParamsDialog.vue 顶部注释。
 *    这里仍然保留完整下拉 —— 一是满足「让用户选常见方式」，二是没有标点的纯文本确实会用到它。
 */
export const SEPARATOR_PRESETS = [
  {
    value: '\n',
    label: '按换行切分（默认）',
    hint: '每一行独立成句，适合 .txt / .md 这类一行一条的文本'
  },
  {
    value: '\n\n',
    label: '按空行切分（整段）',
    hint: '以空行分段，一个自然段尽量不被拆散，适合结构清晰的文档'
  },
  {
    value: '。',
    label: '按中文句号切分',
    hint: '按句子切分，片段最细、检索命中率最高，适合中文长文'
  },
  {
    value: '；',
    label: '按中文分号切分',
    hint: '粒度介于句子与段落之间，适合条款、条目式内容'
  },
  {
    value: '.',
    label: '按英文句点切分',
    hint: '适合英文文档'
  },
  {
    value: '\t',
    label: '按制表符切分',
    hint: '适合从 Excel / TSV 导出的表格文本'
  }
]

/** 自定义选项的取值（不是真实分隔符，只用于 el-select 的占位） */
export const CUSTOM_SEPARATOR = '__custom__'

/** 预设里找得到就返回中文名，找不到按「自定义」处理 */
export function separatorLabel(value) {
  return SEPARATOR_PRESETS.find((p) => p.value === value)?.label || '自定义'
}

/** 预设里找得到就返回说明，找不到给一句自定义的提示 */
export function separatorHint(value) {
  return (
    SEPARATOR_PRESETS.find((p) => p.value === value)?.hint ||
    '自己填一个字符串，后端按字面量切分（不是正则，别写 \\s 这类）'
  )
}

/**
 * 展示用：把不可见字符变成看得见的转义。
 * '\n' → "\n"（四个字符），避免界面上只看到一段空白。
 */
export function separatorPreview(value) {
  return JSON.stringify(String(value ?? ''))
}
