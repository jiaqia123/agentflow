<script setup>
/**
 * Markdown 文本展示块。
 *
 * 把「用户上传的文档正文 / 大模型回答 / 检索召回片段」按 Markdown 渲染成排版后的 HTML，
 * 而不是把 `## 标题` `**重点**` `| a | b |` 这些记号原样怼到页面上。
 *
 * 安全：渲染器（utils/markdown.js）先整体转义 HTML 再解析，输出里所有标签都是它自己拼的，
 * 所以这里的 v-html 不存在注入面 —— 上传一份带 <script> 的文档也执行不了。
 *
 * mode：
 *   auto（默认）—— 有 Markdown 结构才解析；纯文本（中文段落、日志）保留原样换行，
 *                  避免把作者敲的换行按 GFM 折叠成空格
 *   markdown    —— 强制解析
 *   plain       —— 强制纯文本
 */
import { computed } from 'vue'
import { renderMarkdown, renderPlain, renderSmart } from '@/utils/markdown'

const props = defineProps({
  source: { type: String, default: '' },
  mode: { type: String, default: 'auto' },
  /** 紧凑排版：用于抽屉里的小预览，标题/段落间距压到最小 */
  compact: { type: Boolean, default: false }
})

const rendered = computed(() => {
  const text = String(props.source ?? '')
  if (props.mode === 'plain') return { html: renderPlain(text), kind: 'plain' }
  if (props.mode === 'markdown') return { html: renderMarkdown(text), kind: 'markdown' }
  return renderSmart(text)
})
</script>

<template>
  <div
    class="md-body"
    :class="[`md-body--${rendered.kind}`, { 'md-body--compact': compact }]"
    v-html="rendered.html"
  />
</template>
