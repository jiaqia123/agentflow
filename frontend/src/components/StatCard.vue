<script setup>
/** 概览页的统计卡。数值用等宽字体，避免数字跳动时宽度抽搐。 */
import AppIcon from '@/components/AppIcon.vue'

defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  unit: { type: String, default: '' },
  icon: { type: String, default: 'chart' },
  /** 卡片强调色（CSS 颜色值），只用在图标底衬和顶部细线上 */
  tone: { type: String, default: '#4f46e5' },
  hint: { type: String, default: '' }
})
</script>

<template>
  <div class="stat af-card" :style="{ '--tone': tone }">
    <div class="stat__top">
      <span class="stat__label">{{ label }}</span>
      <span class="stat__ico" aria-hidden="true"><AppIcon :name="icon" :size="16" /></span>
    </div>
    <div class="stat__value">
      <b>{{ value }}</b>
      <em v-if="unit">{{ unit }}</em>
    </div>
    <p v-if="hint" class="stat__hint" :title="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.stat {
  position: relative;
  padding: 15px 16px 14px;
  overflow: hidden;
}
/* 顶部一条细强调线：比整块上色克制，但一眼能区分四张卡 */
.stat::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 2.5px;
  background: linear-gradient(90deg, var(--tone), transparent 85%);
}
.stat__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.stat__label {
  font-size: 12.5px;
  color: var(--af-ink-3);
  font-weight: 500;
}
.stat__ico {
  width: 28px;
  height: 28px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--tone);
  background: color-mix(in srgb, var(--tone) 11%, transparent);
}
.stat__value {
  display: flex;
  align-items: baseline;
  gap: 5px;
  margin-top: 9px;
}
.stat__value b {
  font-family: var(--af-font-mono);
  font-size: 25px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--af-ink-1);
  line-height: 1.1;
}
.stat__value em {
  font-style: normal;
  font-size: 12px;
  color: var(--af-ink-4);
}
.stat__hint {
  margin: 7px 0 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
