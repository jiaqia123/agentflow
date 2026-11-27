<script setup>
/**
 * 知识库「新建 / 编辑」对话框（列表页和详情页共用）。
 *
 * 与后端 schemas/knowledge.py 的对齐点：
 *  - name 1~64 必填（且同一用户下不能重名，重名时后端 409）
 *  - description ≤256，库里是 NOT NULL，**不能传 null**
 *  - icon_url ≤512，传 null 表示清空
 *  - 修改接口是 POST /knowledge/{id}/update，且只提交「真正改动过的字段」
 */
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppIcon from '@/components/AppIcon.vue'
import { createKnowledge, updateKnowledge } from '@/api/knowledge'
import { uploadImage } from '@/api/document'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 传入知识库对象 = 编辑模式；null / undefined = 新建模式 */
  knowledge: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const isEdit = computed(() => Boolean(props.knowledge?.id))
const formRef = ref(null)
const saving = ref(false)
const uploading = ref(false)
const serverError = ref('')

const form = reactive({ name: '', description: '', icon_url: '' })

const rules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { max: 64, message: '不超过 64 个字符', trigger: 'blur' }
  ],
  description: [{ max: 256, message: '不超过 256 个字符', trigger: 'blur' }]
}

// 打开时按当前模式回填
watch(
  () => [props.modelValue, props.knowledge],
  ([open]) => {
    if (!open) return
    serverError.value = ''
    form.name = props.knowledge?.name || ''
    form.description = props.knowledge?.description || ''
    form.icon_url = props.knowledge?.icon_url || ''
    // 清掉上一次的校验红字
    formRef.value?.clearValidate?.()
  },
  { immediate: true }
)

/** icon_url 全是外部地址，预览时原样用即可（/static 由 vite 代理到后端） */
const previewUrl = computed(() => form.icon_url || '')
const fallbackInitial = computed(() => (form.name || '知').trim().slice(0, 1))

/** 图标上传：走公共图片接口 POST /upload/image，字段名固定 image */
async function customUpload(option) {
  uploading.value = true
  try {
    const res = await uploadImage(option.file)
    form.icon_url = res.url
    ElMessage.success('图标已上传')
    option.onSuccess?.(res)
  } catch (err) {
    const message = err.message || '图标上传失败'
    serverError.value = message
    containerError(message)
    option.onError?.(err)
  } finally {
    uploading.value = false
  }
}

/** el-upload 不走全局消息时会静默失败，这里补一次提示 */
function containerError(message) {
  ElMessage.error(message)
}

function beforeUpload(file) {
  const isImage = /^image\//.test(file.type)
  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('图片不能超过 10MB')
    return false
  }
  return true
}

async function submit() {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  saving.value = true
  serverError.value = ''
  try {
    const name = form.name.trim()
    const description = form.description.trim()
    const icon_url = form.icon_url || null

    if (isEdit.value) {
      // 只提交改动过的字段：name/description 是 NOT NULL，值没变就不传
      const payload = {}
      if (name !== (props.knowledge.name || '')) payload.name = name
      if (description !== (props.knowledge.description || '')) payload.description = description
      if (icon_url !== (props.knowledge.icon_url || null)) payload.icon_url = icon_url

      if (!Object.keys(payload).length) {
        ElMessage.info('没有检测到修改')
        visible.value = false
        return
      }
      await updateKnowledge(props.knowledge.id, payload)
    } else {
      await createKnowledge({ name, description, icon_url })
    }

    ElMessage.success(isEdit.value ? '已保存' : '知识库创建成功')
    emit('saved')
    visible.value = false
  } catch (err) {
    serverError.value = err.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑知识库' : '新建知识库'"
    width="460px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-alert
      v-if="serverError"
      :title="serverError"
      type="error"
      show-icon
      :closable="false"
      class="dlg-alert"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="图标">
        <div class="icon-row">
          <span class="icon-preview">
            <img v-if="previewUrl" :src="previewUrl" alt="知识库图标预览" />
            <b v-else>{{ fallbackInitial }}</b>
          </span>

          <div class="icon-actions">
            <el-upload
              :show-file-list="false"
              :before-upload="beforeUpload"
              :http-request="customUpload"
              accept="image/*"
            >
              <el-button size="small" :loading="uploading">
                <AppIcon name="upload" :size="14" style="margin-right: 5px" />
                {{ previewUrl ? '替换图片' : '上传图片' }}
              </el-button>
            </el-upload>

            <el-button v-if="previewUrl" size="small" text @click="form.icon_url = ''">
              移除
            </el-button>
          </div>
          <p class="icon-tip">支持 jpg / png / gif / webp，≤10MB，可留空</p>
        </div>
      </el-form-item>

      <el-form-item label="名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="例如：产品手册知识库"
          maxlength="64"
          show-word-limit
          :disabled="saving"
        />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="这个知识库放什么内容（可不填）"
          maxlength="256"
          show-word-limit
          :disabled="saving"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">
        {{ isEdit ? '保存修改' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-alert {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}
.icon-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.icon-preview {
  width: 52px;
  height: 52px;
  flex: none;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid var(--af-line);
  background: linear-gradient(135deg, #eee9fd, #e3f0fb);
  color: #6d63f0;
  font-size: 20px;
  font-weight: 650;
}
.icon-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.icon-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.icon-tip {
  flex-basis: 100%;
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--af-ink-4);
  line-height: 1.5;
}
</style>
