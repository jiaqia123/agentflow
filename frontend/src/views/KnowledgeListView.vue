<script setup>
/**
 * 知识库列表：搜索、翻页、新建 / 编辑 / 删除。
 *
 * ⚠️ 后端 GET /knowledge 返回的是**裸数组**（没有 total），所以这里只能做
 *    「上一页 / 下一页」式翻页：当本页返回条数小于 pageSize 时认为没有下一页。
 *    这是接口设计导致的限制，已列入待后端补充项。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import KnowledgeFormDialog from '@/components/KnowledgeFormDialog.vue'
import { deleteKnowledge, listKnowledges } from '@/api/knowledge'
import { formatNumber, fromNow, hueIndex } from '@/utils/format'

const router = useRouter()

const PAGE_SIZE = 12

const loading = ref(false)
const error = ref('')
const items = ref([])
const page = ref(1)
const keyword = ref('')
const hasNext = ref(false)

const dialogVisible = ref(false)
const editing = ref(null)

/** 图标为空时给一个稳定色块，颜色由名称哈希决定，刷新不变 */
const TONES = ['#6d63f0', '#0ea5e9', '#10a37f', '#e8a33d', '#e5484d', '#8b5cf6']

const isEmpty = computed(() => !loading.value && !items.value.length)
const isSearching = computed(() => Boolean(keyword.value.trim()))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await listKnowledges({
      page: page.value,
      limit: PAGE_SIZE,
      keyword: keyword.value.trim() || undefined
    })
    const list = Array.isArray(res) ? res : []
    items.value = list
    hasNext.value = list.length === PAGE_SIZE
  } catch (err) {
    error.value = err.message || '加载失败'
    items.value = []
    hasNext.value = false
  } finally {
    loading.value = false
  }
}

/** 搜索要回到第一页，否则会停在一个空页上 */
let searchTimer = null
watch(keyword, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 320)
})

watch(page, load)

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}

function openEdit(kb) {
  editing.value = kb
  dialogVisible.value = true
}

async function remove(kb) {
  try {
    await ElMessageBox.confirm(
      `删除后「${kb.name}」及其文档记录将不再可见，此操作不可撤销。`,
      '确认删除该知识库？',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return
  }

  try {
    await deleteKnowledge(kb.id)
    ElMessage.success('已删除')
    // 删掉当前页最后一条时回退一页，避免停在空页
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    else load()
  } catch (err) {
    // 库下还有文档时后端返回 409，这里把话说明白
    ElMessage.error(err.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="af-page">
    <div class="af-page-head">
      <div>
        <h2 class="af-page-title">知识库</h2>
        <p class="af-page-desc">
          每个知识库对应一个独立的向量集合，检索时互不干扰
        </p>
      </div>
      <div class="head-actions">
        <el-input
          v-model="keyword"
          placeholder="按名称搜索"
          clearable
          class="search"
        >
          <template #prefix><AppIcon name="search" :size="15" /></template>
        </el-input>
        <el-button @click="load" :loading="loading">
          <AppIcon name="refresh" :size="15" />
        </el-button>
        <el-button type="primary" @click="openCreate">
          <AppIcon name="plus" :size="15" style="margin-right: 5px" />
          新建知识库
        </el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" show-icon :closable="false" class="mb">
      <template #default>
        <span>{{ error }}　</span>
        <el-button link type="primary" size="small" @click="load">重试</el-button>
      </template>
    </el-alert>

    <!-- 骨架屏 -->
    <div v-if="loading" class="cards">
      <div v-for="i in 4" :key="i" class="af-card af-card--pad">
        <el-skeleton :rows="3" animated />
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="af-card af-empty">
      <span class="empty-ico" aria-hidden="true">
        <AppIcon :name="isSearching ? 'search' : 'database'" :size="26" />
      </span>
      <h3>{{ isSearching ? '没有匹配的知识库' : '还没有知识库' }}</h3>
      <p>
        {{
          isSearching
            ? '换个关键词试试，或者清空搜索框查看全部'
            : '创建第一个知识库，就可以往里上传文档了'
        }}
      </p>
      <el-button v-if="!isSearching" type="primary" @click="openCreate">
        <AppIcon name="plus" :size="15" style="margin-right: 5px" />
        新建知识库
      </el-button>
      <el-button v-else @click="keyword = ''">清空搜索</el-button>
    </div>

    <!-- 卡片网格 -->
    <div v-else class="cards">
      <article v-for="kb in items" :key="kb.id" class="kb af-card">
        <header class="kb__head">
          <span
            class="kb__icon"
            :style="{ '--tone': TONES[hueIndex(kb.name || kb.id)] }"
            aria-hidden="true"
          >
            <img v-if="kb.icon_url" :src="kb.icon_url" :alt="`${kb.name} 的图标`" />
            <b v-else>{{ (kb.name || '知').slice(0, 1) }}</b>
          </span>

          <div class="kb__title">
            <h3 :title="kb.name">{{ kb.name }}</h3>
            <p class="kb__time">
              <AppIcon name="clock" :size="12" />
              {{ fromNow(kb.created_at) }}
            </p>
          </div>
        </header>

        <p class="kb__desc" :class="{ 'is-empty': !kb.description }">
          {{ kb.description || '暂无描述' }}
        </p>

        <div class="kb__stats">
          <span><b>{{ formatNumber(kb.document_num) }}</b> 文档</span>
          <i></i>
          <span><b>{{ formatNumber(kb.str_num) }}</b> 字符</span>
        </div>

        <footer class="kb__foot">
          <el-button type="primary" size="small" @click="router.push(`/knowledge/${kb.id}`)">
            <AppIcon name="chevronRight" :size="14" style="margin-right: 4px" />
            进入管理
          </el-button>
          <div class="kb__tools">
            <el-button size="small" text @click="openEdit(kb)" title="编辑">
              <AppIcon name="edit" :size="15" />
            </el-button>
            <el-button size="small" text class="danger" @click="remove(kb)" title="删除">
              <AppIcon name="trash" :size="15" />
            </el-button>
          </div>
        </footer>
      </article>
    </div>

    <!-- 翻页（裸数组接口，只能上下页） -->
    <div v-if="!isEmpty && (page > 1 || hasNext)" class="pager">
      <el-button :disabled="page <= 1 || loading" @click="page -= 1">上一页</el-button>
      <span class="pager__now">第 {{ page }} 页</span>
      <el-button :disabled="!hasNext || loading" @click="page += 1">下一页</el-button>
    </div>

    <KnowledgeFormDialog v-model="dialogVisible" :knowledge="editing" @saved="load" />
  </div>
</template>

<style scoped>
.mb {
  margin-bottom: 16px;
  border-radius: var(--af-radius);
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.search {
  width: 220px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 12px;
}

/* ------------------------------------------------------- 知识库卡 */
.kb {
  display: flex;
  flex-direction: column;
  padding: 15px 16px 13px;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}
.kb:hover {
  transform: translateY(-2px);
  box-shadow: var(--af-shadow);
  border-color: color-mix(in srgb, var(--af-primary) 30%, var(--af-line));
}

.kb__head {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}
.kb__icon {
  width: 42px;
  height: 42px;
  flex: none;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 11px;
  font-size: 17px;
  font-weight: 650;
  color: #fff;
  background: linear-gradient(135deg, var(--tone), color-mix(in srgb, var(--tone) 55%, #ffffff));
  box-shadow: 0 6px 14px -8px var(--tone);
}
.kb__icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.kb__title {
  min-width: 0;
  flex: 1;
}
.kb__title h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 620;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb__time {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
}

.kb__desc {
  margin: 12px 0 auto;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--af-ink-3);
  min-height: 42px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kb__desc.is-empty {
  color: var(--af-ink-4);
  font-style: italic;
}

.kb__stats {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 13px 0 12px;
  padding: 8px 10px;
  border-radius: 9px;
  background: #f7f6fc;
  font-size: 12px;
  color: var(--af-ink-3);
}
.kb__stats b {
  font-family: var(--af-font-mono);
  font-size: 13px;
  color: var(--af-ink-1);
  margin-right: 2px;
}
.kb__stats i {
  width: 1px;
  height: 11px;
  background: var(--af-line);
}

.kb__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 11px;
  border-top: 1px solid var(--af-line-soft);
}
.kb__tools {
  display: flex;
  gap: 0;
}
.kb__tools :deep(.el-button + .el-button) {
  margin-left: 0;
}
.danger {
  color: var(--af-danger);
}

/* 空态 */
.empty-ico {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  margin: 0 auto 14px;
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

/* 翻页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}
.pager__now {
  font-size: 12.5px;
  color: var(--af-ink-3);
  min-width: 56px;
  text-align: center;
}

@media (max-width: 640px) {
  .head-actions {
    width: 100%;
  }
  .search {
    flex: 1;
    width: auto;
    min-width: 140px;
  }
  .cards {
    grid-template-columns: 1fr;
  }
}
</style>
