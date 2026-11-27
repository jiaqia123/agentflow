<script setup>
/**
 * 概览页。
 *
 * 数据来源说明（很重要，决定了这里能算出哪些数）：
 *  - 知识库列表 GET /knowledge 返回的是**裸数组**，没有 total。所以知识库「总数」最多只能
 *    取到 limit 条；这里 limit=100，够用但严格来说不是精确总数。
 *  - 文档总数 GET /document/list 有 total，精确。
 *  - 文档数 / 字符数 直接累加知识库上的 document_num / str_num ——
 *    这两个字段由后端 /document/store 成功入库后维护，比前端自己数更准。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import StatCard from '@/components/StatCard.vue'
import { listKnowledges } from '@/api/knowledge'
import { listDocuments } from '@/api/document'
import { formatNumber, fromNow, formatSize } from '@/utils/format'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const knowledges = ref([])
const docTotal = ref(0)
const recentDocs = ref([])

const sum = (arr, key) => arr.reduce((acc, item) => acc + (Number(item[key]) || 0), 0)

const kbCount = computed(() => knowledges.value.length)
const docCount = computed(() => sum(knowledges.value, 'document_num'))
const charCount = computed(() => sum(knowledges.value, 'str_num'))
const appCount = computed(() => sum(knowledges.value, 'app_num'))

/** 卡片上的附属信息 */
const charHint = computed(() => `约 ${formatSize(charCount.value)} 文本`)

/** 知识库按文档数排序，取前 5 做对比条 */
const topKnowledges = computed(() => {
  const list = [...knowledges.value].sort((a, b) => (b.document_num || 0) - (a.document_num || 0))
  return list.slice(0, 5)
})
const maxDocNum = computed(() => Math.max(1, ...topKnowledges.value.map((k) => k.document_num || 0)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [kbs, docs] = await Promise.all([
      listKnowledges({ page: 1, limit: 100 }),
      listDocuments({ page: 1, limit: 5 })
    ])
    knowledges.value = Array.isArray(kbs) ? kbs : []
    docTotal.value = docs?.total || 0
    recentDocs.value = docs?.items || []
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="af-page">
    <div class="af-page-head">
      <div>
        <h2 class="af-page-title">概览</h2>
        <p class="af-page-desc">知识库、文档与向量化数据的整体情况</p>
      </div>
      <el-button :loading="loading" @click="load">
        <AppIcon name="refresh" :size="15" style="margin-right: 6px" />
        刷新
      </el-button>
    </div>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="mb"
    >
      <template #default>
        <span>{{ error }}　</span>
        <el-button link type="primary" size="small" @click="load">重试</el-button>
      </template>
    </el-alert>

    <!-- 统计卡 -->
    <div v-loading="loading" class="stats">
      <StatCard
        label="知识库"
        :value="formatNumber(kbCount)"
        unit="个"
        icon="database"
        tone="#4f46e5"
        hint="每人只能看到自己的知识库"
      />
      <StatCard
        label="已入库文档"
        :value="formatNumber(docTotal)"
        unit="份"
        icon="file"
        tone="#0ea5e9"
        :hint="`知识库累计计数 ${formatNumber(docCount)} 份`"
      />
      <StatCard
        label="已向量化字符"
        :value="formatNumber(charCount)"
        icon="layers"
        tone="#10a37f"
        :hint="charHint"
      />
      <StatCard
        label="关联应用"
        :value="formatNumber(appCount)"
        unit="个"
        icon="brain"
        tone="#e8a33d"
        hint="应用模块尚未开放，app_num 目前恒为 0"
      />
    </div>

    <div class="grid">
      <!-- 知识库分布 -->
      <section class="af-card af-card--pad">
        <header class="sec-head">
          <h3>知识库文档分布</h3>
          <router-link class="sec-link" to="/knowledge">
            全部知识库 <AppIcon name="chevronRight" :size="13" />
          </router-link>
        </header>

        <div v-if="loading" class="skeleton">
          <el-skeleton :rows="4" animated />
        </div>

        <div v-else-if="!topKnowledges.length" class="af-empty">
          <p>还没有知识库</p>
          <el-button type="primary" size="small" @click="router.push('/knowledge')">
            <AppIcon name="plus" :size="14" style="margin-right: 5px" />
            去创建
          </el-button>
        </div>

        <ul v-else class="bars">
          <li v-for="kb in topKnowledges" :key="kb.id">
            <router-link class="bars__row" :to="`/knowledge/${kb.id}`">
              <span class="bars__name" :title="kb.name">{{ kb.name }}</span>
              <span class="bars__track">
                <i :style="{ width: `${((kb.document_num || 0) / maxDocNum) * 100}%` }"></i>
              </span>
              <span class="bars__num">{{ kb.document_num || 0 }}</span>
            </router-link>
          </li>
        </ul>
      </section>

      <!-- 最近入库 -->
      <section class="af-card af-card--pad">
        <header class="sec-head">
          <h3>最近入库文档</h3>
          <router-link class="sec-link" to="/documents">
            全部文档 <AppIcon name="chevronRight" :size="13" />
          </router-link>
        </header>

        <div v-if="loading" class="skeleton">
          <el-skeleton :rows="4" animated />
        </div>

        <div v-else-if="!recentDocs.length" class="af-empty">
          <p>还没有入库文档</p>
          <el-button type="primary" size="small" @click="router.push('/retrieve')">
            <AppIcon name="upload" :size="14" style="margin-right: 5px" />
            去上传
          </el-button>
        </div>

        <ul v-else class="recent">
          <li v-for="doc in recentDocs" :key="doc.id">
            <span class="recent__ico" aria-hidden="true"><AppIcon name="file" :size="15" /></span>
            <span class="recent__main">
              <b :title="doc.filename_original">{{ doc.filename_original }}</b>
              <i>{{ doc.chunk_count }} 个片段 · {{ formatNumber(doc.char_count) }} 字符</i>
            </span>
            <span class="recent__time">{{ fromNow(doc.created_at) }}</span>
          </li>
        </ul>
      </section>
    </div>

    <!-- 快捷入口 -->
    <section class="quick">
      <router-link class="quick__item af-card" to="/knowledge">
        <span class="quick__ico" style="--tone: #4f46e5"><AppIcon name="database" :size="17" /></span>
        <span class="quick__txt"><b>管理知识库</b><i>新建、改名、删除，设置图标</i></span>
        <AppIcon name="chevronRight" :size="15" class="quick__arrow" />
      </router-link>

      <router-link class="quick__item af-card" to="/documents">
        <span class="quick__ico" style="--tone: #0ea5e9"><AppIcon name="upload" :size="17" /></span>
        <span class="quick__txt"><b>文档与上传</b><i>上传 → 切分预览 → 向量入库</i></span>
        <AppIcon name="chevronRight" :size="15" class="quick__arrow" />
      </router-link>

      <router-link class="quick__item af-card" to="/retrieve">
        <span class="quick__ico" style="--tone: #10a37f"><AppIcon name="search" :size="17" /></span>
        <span class="quick__txt"><b>在线检索</b><i>提问，看答案与引用片段</i></span>
        <AppIcon name="chevronRight" :size="15" class="quick__arrow" />
      </router-link>
    </section>
  </div>
</template>

<style scoped>
.mb {
  margin-bottom: 16px;
  border-radius: var(--af-radius);
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}
.sec-head h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
}
.sec-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12.5px;
  font-weight: 500;
}

.skeleton {
  padding: 4px 0;
}

/* ---- 分布条 ---- */
.bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.bars__row {
  display: grid;
  grid-template-columns: 96px 1fr 30px;
  align-items: center;
  gap: 10px;
  color: inherit;
}
.bars__row:hover .bars__name {
  color: var(--af-primary);
}
.bars__name {
  font-size: 12.5px;
  color: var(--af-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}
.bars__track {
  height: 7px;
  border-radius: 4px;
  background: #eeecf7;
  overflow: hidden;
}
.bars__track i {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #6d63f0, #a78bfa);
  transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.bars__num {
  text-align: right;
  font-family: var(--af-font-mono);
  font-size: 12px;
  color: var(--af-ink-3);
}

/* ---- 最近文档 ---- */
.recent {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.recent li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px dashed var(--af-line);
}
.recent li:last-child {
  border-bottom: none;
}
.recent__ico {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #6d63f0;
  background: #f1effc;
}
.recent__main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.recent__main b {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent__main i {
  font-style: normal;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.recent__time {
  flex: none;
  font-size: 11.5px;
  color: var(--af-ink-4);
}

/* ---- 快捷入口 ---- */
.quick {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.quick__item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  color: inherit;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}
.quick__item:hover {
  transform: translateY(-2px);
  box-shadow: var(--af-shadow);
  border-color: color-mix(in srgb, var(--af-primary) 32%, var(--af-line));
}
.quick__ico {
  width: 34px;
  height: 34px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: var(--tone);
  background: color-mix(in srgb, var(--tone) 11%, transparent);
}
.quick__txt {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.quick__txt b {
  font-size: 13.5px;
  font-weight: 600;
}
.quick__txt i {
  font-style: normal;
  font-size: 11.5px;
  color: var(--af-ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quick__arrow {
  flex: none;
  color: var(--af-ink-4);
}

@media (max-width: 1100px) {
  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grid {
    grid-template-columns: 1fr;
  }
  .quick {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 560px) {
  .stats {
    grid-template-columns: 1fr;
  }
  .bars__row {
    grid-template-columns: 74px 1fr 26px;
  }
}
</style>
