<script setup>
/**
 * 知识库详情：库信息 + 该库下的文档列表 + 上传入库入口。
 *
 * ⚠️ 后端没有「按知识库统计字符数」的接口，但 knowledge_bases 上就带着
 *    document_num / str_num，直接读详情接口即可，不用自己数。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import KnowledgeFormDialog from '@/components/KnowledgeFormDialog.vue'
import DocumentUploadDrawer from '@/components/DocumentUploadDrawer.vue'
import { rememberDocument } from '@/composables/useDocumentCache'
import { deleteKnowledge, getKnowledge } from '@/api/knowledge'
import { listDocuments } from '@/api/document'
import { formatDateTime, formatNumber, formatSize, extTagType, fileExt, hueIndex } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const knowledgeId = computed(() => Number(route.params.id))

const loading = ref(true)
const error = ref('')
const kb = ref(null)

const docsLoading = ref(false)
const docs = ref([])
const docTotal = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')

const editVisible = ref(false)
const uploadVisible = ref(false)

const TONES = ['#6d63f0', '#0ea5e9', '#10a37f', '#e8a33d', '#e5484d', '#8b5cf6']
const tone = computed(() => TONES[hueIndex(kb.value?.name || knowledgeId.value)])
const collectionName = computed(() => `agentflow_kb_${knowledgeId.value}`)
const docPages = computed(() => Math.max(1, Math.ceil(docTotal.value / pageSize.value)))
/** 每份文档平均片段数，用来看切分参数是否合适 */
const avgChunks = computed(() => {
  if (!docs.value.length) return 0
  const sum = docs.value.reduce((acc, d) => acc + (d.chunk_count || 0), 0)
  return Math.round((sum / docs.value.length) * 10) / 10
})

async function loadKnowledge() {
  loading.value = true
  error.value = ''
  try {
    kb.value = await getKnowledge(knowledgeId.value)
  } catch (err) {
    error.value = err.message || '加载失败'
    kb.value = null
  } finally {
    loading.value = false
  }
}

async function loadDocs() {
  docsLoading.value = true
  try {
    const res = await listDocuments({
      knowledge_id: knowledgeId.value,
      page: page.value,
      limit: pageSize.value,
      keyword: keyword.value.trim() || undefined
    })
    docs.value = res?.items || []
    docTotal.value = res?.total || 0
  } catch (err) {
    ElMessage.error(err.message || '文档列表加载失败')
    docs.value = []
    docTotal.value = 0
  } finally {
    docsLoading.value = false
  }
}

let searchTimer = null
watch(keyword, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadDocs()
  }, 320)
})
watch(page, loadDocs)
watch(pageSize, () => {
  page.value = 1
  loadDocs()
})

/** 上传入库成功后：刷新文档列表与知识库计数 */
function onStored() {
  loadDocs()
  loadKnowledge()
}

function onSaved() {
  loadKnowledge()
}

/** 点「查看」→ 文档详情页（先把这一行缓存起来，详情页就不用再翻页找） */
function goDetail(row) {
  rememberDocument(row)
  router.push({ name: 'document-detail', params: { id: row.id } })
}

async function remove() {
  try {
    await ElMessageBox.confirm(
      `删除后「${kb.value.name}」将不可见，此操作不可撤销。`,
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
    await deleteKnowledge(knowledgeId.value)
    ElMessage.success('已删除')
    router.replace('/knowledge')
  } catch (err) {
    // 库下还有文档时后端返回 409
    ElMessage.error(err.message || '删除失败')
  }
}

onMounted(() => {
  loadKnowledge()
  loadDocs()
})
</script>

<template>
  <div class="af-page">
    <!-- 加载中 -->
    <div v-if="loading" class="af-card af-card--pad">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 加载失败 -->
    <div v-else-if="error" class="af-card af-empty">
      <span class="empty-ico" aria-hidden="true"><AppIcon name="warning" :size="24" /></span>
      <h3>加载失败</h3>
      <p>{{ error }}</p>
      <el-button @click="router.replace('/knowledge')">返回知识库列表</el-button>
    </div>

    <template v-else-if="kb">
      <!-- 面包屑 / 返回 -->
      <button class="back" type="button" @click="router.push('/knowledge')">
        <AppIcon name="back" :size="15" />
        返回知识库列表
      </button>

      <!-- 库信息 -->
      <section class="hero af-card" :style="{ '--tone': tone }">
        <div class="hero__main">
          <span class="hero__icon" aria-hidden="true">
            <img v-if="kb.icon_url" :src="kb.icon_url" :alt="`${kb.name} 的图标`" />
            <b v-else>{{ (kb.name || '知').slice(0, 1) }}</b>
          </span>

          <div class="hero__text">
            <h2>{{ kb.name }}</h2>
            <p :class="{ 'is-empty': !kb.description }">{{ kb.description || '暂无描述' }}</p>
            <div class="hero__meta">
              <span class="af-mono">#{{ kb.id }}</span>
              <i></i>
              <span class="af-mono" :title="'向量集合名'">{{ collectionName }}</span>
              <i></i>
              <span>创建于 {{ formatDateTime(kb.created_at) }}</span>
            </div>
          </div>
        </div>

        <div class="hero__actions">
          <el-button :disabled="loading" @click="loadKnowledge">
            <AppIcon name="refresh" :size="15" />
          </el-button>
          <el-button @click="editVisible = true">
            <AppIcon name="edit" :size="15" style="margin-right: 5px" />
            编辑
          </el-button>
          <el-button type="danger" plain @click="remove">
            <AppIcon name="trash" :size="15" style="margin-right: 5px" />
            删除
          </el-button>
          <el-button type="primary" @click="uploadVisible = true">
            <AppIcon name="upload" :size="15" style="margin-right: 5px" />
            上传文档
          </el-button>
        </div>
      </section>

      <!-- 指标 -->
      <div class="metrics">
        <div class="metric">
          <span>已入库文档</span>
          <b>{{ formatNumber(kb.document_num) }}<em>份</em></b>
        </div>
        <div class="metric">
          <span>累计字符数</span>
          <b>{{ formatNumber(kb.str_num) }}<em>字符</em></b>
        </div>
        <div class="metric">
          <span>文本体积</span>
          <b>{{ formatSize(kb.str_num) }}</b>
        </div>
        <div class="metric">
          <span>本页平均片段</span>
          <b>{{ avgChunks }}<em>块/份</em></b>
        </div>
      </div>

      <!-- 文档列表 -->
      <section class="af-card af-card--pad docs">
        <header class="docs__head">
          <div>
            <h3>库内文档</h3>
            <p>共 {{ formatNumber(docTotal) }} 份</p>
          </div>
          <div class="docs__tools">
            <el-input v-model="keyword" placeholder="按文件名搜索" clearable class="docs__search">
              <template #prefix><AppIcon name="search" :size="15" /></template>
            </el-input>
            <el-button :loading="docsLoading" @click="loadDocs">
              <AppIcon name="refresh" :size="15" />
            </el-button>
          </div>
        </header>

        <div v-if="docsLoading && !docs.length" class="skeleton">
          <el-skeleton :rows="5" animated />
        </div>

        <div v-else-if="!docs.length" class="af-empty">
          <span class="empty-ico" aria-hidden="true"><AppIcon name="file" :size="24" /></span>
          <h3>{{ keyword.trim() ? '没有匹配的文档' : '这个知识库还没有文档' }}</h3>
          <p>
            {{
              keyword.trim()
                ? '换个关键词试试'
                : '上传 PDF / Word / Excel / Markdown，切分后入库即可被检索'
            }}
          </p>
          <el-button v-if="!keyword.trim()" type="primary" @click="uploadVisible = true">
            <AppIcon name="upload" :size="15" style="margin-right: 5px" />
            上传文档
          </el-button>
          <el-button v-else @click="keyword = ''">清空搜索</el-button>
        </div>

        <template v-else>
          <el-table :data="docs" v-loading="docsLoading" style="width: 100%" row-key="id">
            <el-table-column label="文件名" min-width="240">
              <template #default="{ row }">
                <div class="cell-file">
                  <el-tag
                    :type="extTagType(fileExt(row.filename_original))"
                    size="small"
                    effect="light"
                    class="cell-file__ext"
                  >
                    {{ fileExt(row.filename_original).replace('.', '') || '?' }}
                  </el-tag>
                  <button
                    class="cell-file__name"
                    type="button"
                    :title="`查看「${row.filename_original}」的详情`"
                    @click="goDetail(row)"
                  >
                    {{ row.filename_original }}
                  </button>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="片段数" width="90" align="right">
              <template #default="{ row }">
                <span class="af-mono">{{ formatNumber(row.chunk_count) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="字符数" width="110" align="right">
              <template #default="{ row }">
                <span class="af-mono">{{ formatNumber(row.char_count) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="文档 ID" width="90" align="right">
              <template #default="{ row }">
                <span class="af-mono af-dim">#{{ row.id }}</span>
              </template>
            </el-table-column>

            <el-table-column label="入库时间" width="170">
              <template #default="{ row }">
                <span class="af-muted">{{ formatDateTime(row.created_at) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="唯一名" min-width="180">
              <template #default="{ row }">
                <span class="af-mono af-dim cell-uuid" :title="row.filename_uuid">
                  {{ row.filename_uuid }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="goDetail(row)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50]"
              :total="docTotal"
              layout="total, sizes, prev, pager, next"
              background
              :disabled="docsLoading"
            />
          </div>
        </template>
      </section>

      <KnowledgeFormDialog v-model="editVisible" :knowledge="kb" @saved="onSaved" />
      <DocumentUploadDrawer v-model="uploadVisible" :knowledge="kb" @stored="onStored" />
    </template>
  </div>
</template>

<style scoped>
.back {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 12px;
  padding: 5px 9px 5px 7px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--af-ink-3);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.back:hover {
  background: #fff;
  border-color: var(--af-line);
  color: var(--af-primary);
}

/* ---- 库信息 ---- */
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 18px;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: linear-gradient(90deg, var(--tone), transparent 70%);
}
.hero__main {
  display: flex;
  gap: 14px;
  min-width: 0;
  flex: 1;
}
.hero__icon {
  width: 56px;
  height: 56px;
  flex: none;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 15px;
  font-size: 22px;
  font-weight: 650;
  color: #fff;
  background: linear-gradient(135deg, var(--tone), color-mix(in srgb, var(--tone) 52%, #fff));
  box-shadow: 0 10px 22px -12px var(--tone);
}
.hero__icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero__text {
  min-width: 0;
}
.hero__text h2 {
  margin: 0 0 5px;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.hero__text p {
  margin: 0 0 9px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--af-ink-3);
  max-width: 620px;
}
.hero__text p.is-empty {
  color: var(--af-ink-4);
  font-style: italic;
}
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.hero__meta i {
  width: 1px;
  height: 10px;
  background: var(--af-line);
}
.hero__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hero__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

/* ---- 指标条 ---- */
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0;
}
.metric {
  padding: 12px 14px;
  border-radius: var(--af-radius-lg);
  background: #fff;
  border: 1px solid var(--af-line);
}
.metric span {
  display: block;
  font-size: 12px;
  color: var(--af-ink-3);
  margin-bottom: 4px;
}
.metric b {
  font-family: var(--af-font-mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.metric b em {
  font-style: normal;
  font-family: var(--af-font);
  font-size: 11.5px;
  color: var(--af-ink-4);
  margin-left: 3px;
}

/* ---- 文档区 ---- */
.docs__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.docs__head h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 620;
}
.docs__head p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--af-ink-3);
}
.docs__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.docs__search {
  width: 220px;
}
.skeleton {
  padding: 6px 0;
}
.cell-file {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.cell-file__ext {
  flex: none;
  width: 42px;
  justify-content: center;
  text-transform: uppercase;
}
.cell-file__name {
  min-width: 0;
  padding: 0;
  border: none;
  background: none;
  text-align: left;
  font-family: inherit;
  font-size: 13px;
  color: var(--af-ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s ease;
}
.cell-file__name:hover {
  color: var(--af-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cell-uuid {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.empty-ico {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 13px;
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

@media (max-width: 1000px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .hero__actions {
    width: 100%;
  }
  .docs__tools {
    width: 100%;
  }
  .docs__search {
    flex: 1;
    width: auto;
  }
  .pager {
    justify-content: center;
  }
  .metrics {
    grid-template-columns: 1fr;
  }
}
</style>
