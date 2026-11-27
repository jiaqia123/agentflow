<script setup>
/**
 * 内联 SVG 图标。项目没装 @element-plus/icons-vue（沙箱装包很慢，且只有几十 KB 的收益），
 * 手写一套 24×24 stroke 图标，风格统一、零依赖、可跟随 currentColor。
 */
import { computed } from 'vue'

const props = defineProps({
  /** 图标名，见下方 PATHS */
  name: { type: String, required: true },
  /** 像素尺寸 */
  size: { type: [Number, String], default: 18 },
  /** 线宽 */
  stroke: { type: [Number, String], default: 1.7 },
  /** 是否填充（实心图标用） */
  filled: { type: Boolean, default: false }
})

const PATHS = {
  dashboard: 'M3 10.5 12 3l9 7.5M5 9.5V21h5v-6h4v6h5V9.5',
  database:
    'M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3ZM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5ZM14 3v5h5',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM21 21l-4.35-4.35',
  plus: 'M12 5v14M5 12h14',
  upload: 'M12 16V4M12 4 7 9M12 4l5 5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  download: 'M12 4v12M12 16l5-5M12 16l-5-5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2',
  logout: 'M15 17l5-5-5-5M20 12H9M12 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  lock: 'M6 11h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM8 11V8a4 4 0 0 1 8 0v3',
  mail: 'M3 6h18v12H3V6ZM3 7l9 6 9-6',
  refresh: 'M21 12a9 9 0 1 1-3-6.7M21 4v5h-5',
  back: 'M19 12H5M5 12l7-7M5 12l7 7',
  chevronRight: 'm9 6 6 6-6 6',
  sparkles: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3ZM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z',
  filter: 'M4 5h16M7 12h10M10 19h4',
  warning: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 7.8h.01',
  check: 'm5 13 4 4L19 7',
  copy: 'M9 9h10v10H9V9ZM5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1',
  layers: 'm12 3 9 5-9 5-9-5 9-5ZM3 13l9 5 9-5M3 17l9 5 9-5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  brain:
    'M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5.2A3 3 0 0 0 6 17a3 3 0 0 0 3 3V4ZM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5.2A3 3 0 0 1 18 17a3 3 0 0 1-3 3V4Z'
}

const d = computed(() => PATHS[props.name] || PATHS.file)
</script>

<template>
  <svg
    class="app-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    :fill="filled ? 'currentColor' : 'none'"
    :stroke="filled ? 'none' : 'currentColor'"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path :d="d" />
  </svg>
</template>

<style scoped>
.app-icon {
  display: block;
  flex: none;
}
</style>
