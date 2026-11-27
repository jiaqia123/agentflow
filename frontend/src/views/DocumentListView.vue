<script setup>
/**
 * 文档库：跨知识库查看当前用户名下所有已入库文档。
 *
 * 对应 GET /document/list，可以不传 knowledge_id（= 全部），
 * 也可以用顶部下拉按知识库筛选 —— 筛选时后端会先校验知识库归属。
 *
 * 说明：列表接口不返回文件下载地址（表里也没存日期目录），
 * 前端无从拼出 /static/documents/<YYMMDD>/<uuid>，所以这里不提供下载按钮。
 *
 * 点「查看」/ 点文件名 → 文档详情页（routes: documents/:id）。
 * 详情页需要的那一行数据先经 useDocumentCache 塞进内存，避免详情页再翻页扫一遍列表。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import DocumentUploadDrawer from '@/components/DocumentUploadDrawer.vue'
import { rememberDocument } from '@/composables/useDocumentCache'
import { listKnowledges } from '@/api/knowledge'
import { listDocuments } from '@/api/document'
import { formatDateTime, formatNumber, extTagType, fileExt } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref('')

const kbs = ref([])
const kbId = ref(null) // null = 全部

const docs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')

const uploadVisible = ref(false)
const uploadTarget = ref(null)

const currentKb = computed(() => kbs.value.find((k) => k.id === kbId.value) || null)
const kbName = (id) => kbs.value.find((k) => k.id === id)?.name || `#${id}`

async function loadKnowledges() {
  try {
    const res = await listKnowledges({ page: 1, limit: 100 })
    kbs.value = Array.isArray(res) ? res : []
  } catch (err) {
    // 知识库列表拉不到不致命，文档列表照样能看
    kbs.value = []
    console.warn('知识库列表加载失败：', err.message)
  }
}

async function loadDocs() {
  loading.value = true
  error.value = ''
  try {
    const res = await listDocuments({
      knowledge_id: kbId.value ?? undefined,
      page: page.value,
      limit: pageSize.value,
      keyword: keyword.value.trim() || undefined
    })
    docs.value = res?.items || []
    total.value = res?.total || 0
  } catch (err) {
    error.value = err.message || '加载失败'
    docs.value = []
    total.value = 0
  } finally {
    loading.value = false
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

watch(kbId, () => {
  page.value = 1
  loadDocs()
})

watch(page, loadDocs)
watch(pageSize, () => {
  page.value = 1
  loadDocs()
})

/**
 * 打开上传抽屉。
 * 在「全部」视图下没有目标知识库 —— 直接引导去知识库页选一个，
 * 因为 /document/store 必须带 knowledge_id。
 */
function openUpload() {
  if (!kbs.value.length) {
    ElMessage.warning('还没有知识库，请先创建一个')
    router.push('/knowledge')
    return
  }
  uploadTarget.value = currentKb.value || kbs.value[0]
  if (!currentKb.value) {
    ElMessage.info(`未筛选知识库，默认入库到「${uploadTarget.value.name}」`)
  }
  uploadVisible.value = true
}

/**
 * 打开文档详情页。
 * 先把这一行塞进缓存 —— 后端没有「按 id 查文档」的接口，详情页拿到缓存就不用再翻页找。
 */
function goDetail(row) {
  rememberDocument(row)
  router.push({ name: 'document-detail', params: { id: row.id } })
}

async function onStored() {
  await Promise.all([loadDocs(), loadKnowledges()])
}

onMounted(async () => {
  // 从知识库详情页带 query 跳过来时，直接落到对应筛选
  const qid = Number(route.query.knowledge_id)
  await loadKnowledges()
  if (qid && kbs.value.some((k) => k.id === qid)) kbId.value = qid
  loadDocs()
})
</script>

<template>
  <div class="af-page">
    <div class="af-page-head">
      <div>
        <h2 class="af-page-title">文档库</h2>
        <p class="af-page-desc">当前账号下所有已入库的文档，可按知识库筛选</p>
      </div>
      <el-button type="primary" @click="openUpload">
        <AppIcon name="upload" :size="15" style="margin-right: 5px" />
        上传文档
      </el-button>
    </div>

    <!-- 工具条 -->
    <div class="toolbar af-card">
      <label class="toolbar__field">
        <span>知识库</span>
        <el-select
          v-model="kbId"
          placeholder="全部知识库"
          clearable
          filterable
          :disabled="loading"
          style="width: 220px"
        >
          <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id">
            <span class="opt">
              <span class="opt__name">{{ k.name }}</span>
              <span class="opt__num">{{ k.document_num }} 份</span>
            </span>
          </el-option>
        </el-select>
      </label>

      <label class="toolbar__field">
        <span>文件名</span>
        <el-input
          v-model="keyword"
          placeholder="模糊搜索"
          clearable
          :disabled="loading"
          style="width: 220px"
        >
          <template #prefix><AppIcon name="search" :size="15" /></template>
        </el-input>
      </label>

      <div class="toolbar__spacer"></div>

      <span class="toolbar__count">
        共 <b>{{ formatNumber(total) }}</b> 份文档
        <template v-if="currentKb">· 当前：{{ currentKb.name }}</template>
      </span>

      <el-button :loading="loading" @click="loadDocs">
        <AppIcon name="refresh" :size="15" />
      </el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :closable="false" class="mb">
      <template #default>
        <span>{{ error }}　</span>
        <el-button link type="primary" size="small" @click="loadDocs">重试</el-button>
      </template>
    </el-alert>

    <!-- 列表 -->
    <section class="af-card af-card--pad">
      <div v-if="loading && !docs.length" class="skeleton">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="!docs.length" class="af-empty">
        <span class="empty-ico" aria-hidden="true"><AppIcon name="file" :size="24" /></span>
        <h3>{{ keyword.trim() || kbId ? '没有匹配的文档' : '还没有入库任何文档' }}</h3>
        <p>
          {{
            keyword.trim() || kbId
              ? '试试清空筛选条件，或换个关键词'
              : '上传文档后，经过切分与向量化即可被检索命中'
          }}
        </p>
        <template v-if="keyword.trim() || kbId">
          <el-button
            @click="
              () => {
                keyword = ''
                kbId = null
              }
            "
          >
            清空筛选
          </el-button>
        </template>
        <el-button v-else type="primary" @click="openUpload">
          <AppIcon name="upload" :size="15" style="margin-right: 5px" />
          上传文档
        </el-button>
      </div>

      <template v-else>
        <!-- 桌面：表格 -->
        <el-table :data="docs" v-loading="loading" style="width: 100%" row-key="id" class="table">
          <el-table-column label="文件名" min-width="260">
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

          <el-table-column label="所属知识库" min-width="150">
            <template #default="{ row }">
              <router-link
                class="kb-link"
                :to="`/knowledge/${row.knowledge_base_id}`"
                :title="kbName(row.knowledge_base_id)"
              >
                {{ kbName(row.knowledge_base_id) }}
              </router-link>
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

          <el-table-column label="入库时间" width="170">
            <template #default="{ row }">
              <span class="af-muted">{{ formatDateTime(row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="goDetail(row)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 移动端：卡片（表格在窄屏会被挤成横向滚动，这里换成堆叠卡片） -->
        <ul class="mob-list">
          <li v-for="row in docs" :key="row.id" class="mob">
            <div class="mob__top">
              <el-tag
                :type="extTagType(fileExt(row.filename_original))"
                size="small"
                effect="light"
              >
                {{ fileExt(row.filename_original).replace('.', '') || '?' }}
              </el-tag>
              <span class="mob__name">{{ row.filename_original }}</span>
            </div>
            <div class="mob__meta">
              <router-link :to="`/knowledge/${row.knowledge_base_id}`">
                {{ kbName(row.knowledge_base_id) }}
              </router-link>
              <span>·</span>
              <span>{{ row.chunk_count }} 片段</span>
              <span>·</span>
              <span>{{ formatNumber(row.char_count) }} 字符</span>
            </div>
            <div class="mob__foot">
              <span class="mob__time">{{ formatDateTime(row.created_at) }}</span>
              <el-button link type="primary" size="small" @click="goDetail(row)">
                查看详情
              </el-button>
            </div>
          </li>
        </ul>

        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            background
            :disabled="loading"
          />
        </div>
      </template>
    </section>

    <DocumentUploadDrawer v-model="uploadVisible" :knowledge="uploadTarget" @stored="onStored" />
  </div>
</template>

<style scoped>
.mb {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}

.toolbar {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
  padding: 13px 16px;
  margin-bottom: 12px;
}
.toolbar__field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.toolbar__field > span {
  font-size: 12px;
  color: var(--af-ink-3);
}
.toolbar__spacer {
  flex: 1;
}
.toolbar__count {
  font-size: 12.5px;
  color: var(--af-ink-3);
  padding-bottom: 7px;
}
.toolbar__count b {
  color: var(--af-ink-1);
  font-family: var(--af-font-mono);
}

.opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.opt__num {
  font-size: 11.5px;
  color: var(--af-ink-4);
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
.kb-link {
  display: inline-block;
  max-width: 100%;
  font-size: 12.5px;
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

/* 移动端卡片默认隐藏 */
.mob-list {
  display: none;
  list-style: none;
  margin: 0;
  padding: 0;
  flex-direction: column;
  gap: 9px;
}
.mob {
  border: 1px solid var(--af-line);
  border-radius: var(--af-radius);
  padding: 11px 12px;
  background: #fff;
}
.mob__top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
}
.mob__name {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mob__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--af-ink-3);
}
.mob__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
}
.mob__time {
  font-size: 11.5px;
  color: var(--af-ink-4);
}

@media (max-width: 760px) {
  .table {
    display: none;
  }
  .mob-list {
    display: flex;
  }
  .toolbar {
    align-items: stretch;
  }
  .toolbar__field,
  .toolbar__field :deep(.el-select),
  .toolbar__field :deep(.el-input) {
    width: 100% !important;
  }
  .toolbar__count {
    padding-bottom: 0;
    text-align: center;
  }
  .pager {
    justify-content: center;
  }
}
</style>
