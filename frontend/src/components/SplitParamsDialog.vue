<script setup>
/**
 * 切分参数对话框（上传抽屉 / 文档详情页共用）。
 *
 * 三个参数对齐后端 schemas/document.py 的 SplitIn：
 *   separator      分段标识符 —— 给「常见切分方式」下拉，不用用户自己敲 \n
 *   chunk_size     分段最大长度（token）
 *   chunk_overlap  分段重叠度，**必须小于 chunk_size**，否则 llama_index 直接抛错
 *
 * 两条实测结论（2026-10-07 拿真实 llm_index 0.14.25 + 真实后端跑出来的，别再想当然）：
 *
 * 1) chunk_size 有硬下限 128。
 *    SentenceSplitter 走的是 `split_text_metadata_aware()`，会先扣掉文档元数据的 token：
 *      effective_chunk_size = chunk_size - len(tokenize(metadata_str))
 *    本项目 file_path 里带中文（".../AgentFlow企业级AI知识库开发平台/..."），元数据实测
 *    **占 100 个 token**；于是 ≤100 时 effective ≤ 0，直接抛
 *    `ValueError: Metadata length (100) is longer than chunk size (N)` → 接口 500（纯文本，
 *    前端只能看到 "Internal Server Error"）。所以这里 min 卡 128，给足余量。
 *
 * 2) separator 对绝大多数文档**不产生任何影响**。
 *    SentenceSplitter 的切分优先级（node_parser/text/sentence.py 的 _get_splits_by_fns）：
 *      ① split_by_sep(paragraph_separator)      ← 硬编码 "\n\n\n"，后端没暴露
 *      ② nltk 分句器
 *      ③ split_by_regex(secondary_chunking_regex) ← 默认 '[^,.;。？！]+[,.;。？！]?|[,.;。？！]'
 *      ④ split_by_sep(separator)               ← ★ 就是用户选的那个
 *      ⑤ split_by_char()
 *    每一层只要「切出 >1 块」就立即胜出、不再往下试。带标点的正常文档在第 ③ 层就被吃掉了，
 *    所以实测 6 个不同的 separator 得到**逐块一致**的结果。它只在「文本没有标点、也没有空格」
 *    这种极端情况下才作为兜底生效（此时换成不同的符号，块数确实会变）。
 *    → 真正决定片段大小/数量的是 chunk_size（实测 128→12 块 / 256→5 / 512→2 / 1024→1）。
 *
 * 只有点「确认并开始切分」才 emit('confirm')，取消不改动调用方的参数。
 */
import { computed, reactive, ref, watch } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import {
  CUSTOM_SEPARATOR,
  DEFAULT_SPLIT_PARAMS,
  SEPARATOR_PRESETS,
  separatorHint,
  separatorPreview
} from '@/utils/split'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 当前生效的参数，每次打开时回填 */
  params: { type: Object, default: null },
  /** 顶部说明文案，按调用场景传（抽屉里说文件数，详情页说重新切分） */
  hint: { type: String, default: '' },
  /** 切分进行中：不允许再改参数 */
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

/** chunk_size 的常用档位，点一下就填上 */
const SIZE_PRESETS = [128, 256, 512, 1024, 2048]

/** 后端能接受的最小分段长度：元数据要吃掉约 100 token，留点余量取 128 */
const MIN_CHUNK_SIZE = 128

const formRef = ref(null)
const form = reactive({
  preset: DEFAULT_SPLIT_PARAMS.separator,
  custom: '',
  chunk_size: DEFAULT_SPLIT_PARAMS.chunk_size,
  chunk_overlap: DEFAULT_SPLIT_PARAMS.chunk_overlap
})

const isCustom = computed(() => form.preset === CUSTOM_SEPARATOR)
/** 真正会提交给后端的分隔符 */
const separator = computed(() => (isCustom.value ? form.custom : form.preset))

const rules = {
  custom: [
    {
      validator: (_rule, value, cb) => {
        if (isCustom.value && !String(value ?? '').length) cb(new Error('请填写自定义分隔符'))
        else cb()
      },
      trigger: 'blur'
    }
  ],
  chunk_size: [
    {
      validator: (_rule, value, cb) => {
        const n = Number(value)
        if (!Number.isFinite(n) || n < MIN_CHUNK_SIZE) {
          cb(new Error(`分段长度不能小于 ${MIN_CHUNK_SIZE}：后端会把文件元数据（实测约 100 token）也算进去，填小了接口会直接报错`))
        } else {
          cb()
        }
      },
      trigger: 'change'
    }
  ],
  chunk_overlap: [
    {
      validator: (_rule, value, cb) => {
        if (Number(value) >= Number(form.chunk_size)) cb(new Error('重叠度必须小于分段长度'))
        else cb()
      },
      trigger: 'change'
    }
  ]
}

// 打开时按调用方当前的参数回填
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const p = props.params || DEFAULT_SPLIT_PARAMS
    const matched = SEPARATOR_PRESETS.some((item) => item.value === p.separator)
    form.preset = matched ? p.separator : CUSTOM_SEPARATOR
    form.custom = matched ? '' : String(p.separator ?? '')
    form.chunk_size = Number(p.chunk_size) || DEFAULT_SPLIT_PARAMS.chunk_size
    form.chunk_overlap = Number(p.chunk_overlap) || 0
    formRef.value?.clearValidate?.()
  },
  { immediate: true }
)

// 换选切分方式后把上一次的红字清掉
watch(
  () => form.preset,
  () => formRef.value?.clearValidate?.()
)

const overlapWarning = computed(
  () => Number(form.chunk_overlap) >= Number(form.chunk_size) && Number(form.chunk_size) > 0
)

async function confirm() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  emit('confirm', {
    separator: separator.value,
    chunk_size: Number(form.chunk_size),
    chunk_overlap: Number(form.chunk_overlap)
  })
  visible.value = false
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="设置切分参数"
    width="520px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-alert
      v-if="hint"
      :title="hint"
      type="info"
      show-icon
      :closable="false"
      class="dlg-alert"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <!-- 1 分段标识符：下拉选常见切分方式 -->
      <el-form-item label="分段标识符" prop="preset">
        <el-select v-model="form.preset" :disabled="loading" style="width: 100%">
          <el-option
            v-for="item in SEPARATOR_PRESETS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
          <el-option label="自定义…" :value="CUSTOM_SEPARATOR" />
        </el-select>
        <p class="hint">
          {{ separatorHint(separator) }}
          <em class="af-mono">{{ separatorPreview(separator) }}</em>
        </p>
      </el-form-item>

      <el-form-item v-if="isCustom" label="自定义分隔符" prop="custom">
        <el-input
          v-model="form.custom"
          :disabled="loading"
          placeholder="例如：|  或 ::  （不支持正则）"
        />
      </el-form-item>

      <!-- 2 分段最大长度 -->
      <el-form-item label="分段最大长度（token）" prop="chunk_size">
        <div class="num-row">
          <el-input-number
            v-model="form.chunk_size"
            :min="MIN_CHUNK_SIZE"
            :max="4096"
            :step="64"
            :disabled="loading"
            controls-position="right"
            style="width: 170px"
          />
          <span class="quick">
            常用
            <el-button
              v-for="s in SIZE_PRESETS"
              :key="s"
              link
              type="primary"
              size="small"
              :disabled="loading"
              @click="form.chunk_size = s"
            >
              {{ s }}
            </el-button>
          </span>
        </div>
      </el-form-item>

      <!-- 3 分段重叠度 -->
      <el-form-item label="分段重叠度" prop="chunk_overlap">
        <el-input-number
          v-model="form.chunk_overlap"
          :min="0"
          :max="2048"
          :step="10"
          :disabled="loading"
          controls-position="right"
          style="width: 170px"
        />
      </el-form-item>

      <div class="notes" :class="{ 'notes--bad': overlapWarning }">
        <p>
          <AppIcon name="warning" :size="13" />
          <span>
            <b>真正决定片段大小的是「分段长度」</b>，单位是 <b>token</b> 不是字符（512 token ≈
            500~900 个汉字）。实测同一份文档：长度 128 → 12 块、256 → 5 块、512 → 2 块、1024 → 1 块。
          </span>
        </p>
        <p>
          <AppIcon name="warning" :size="13" />
          <span>
            长度不能小于 <b>{{ MIN_CHUNK_SIZE }}</b>：文件路径等元数据实测要占 100 token，
            填小了后端会直接报错（接口只回一句 Internal Server Error）。重叠度也必须<b>小于</b>分段长度。
          </span>
        </p>
        <p>
          <AppIcon name="info" :size="13" />
          <span>
            <b>分段标识符影响有限</b>：llama_index 会先按「连续空行 → 内置分句器 → 标点正则」切，
            前几层能切开就用不到它，所以带标点的普通文档改它<b>不会改变结果</b>；
            只有通篇没有标点的文本才会用它兜底。
          </span>
        </p>
      </div>

      <div class="live">
        本次将按
        <em class="af-mono">{{ separatorPreview(separator) }}</em> 切分 · 长度
        <b>{{ form.chunk_size }}</b> token · 重叠 <b>{{ form.chunk_overlap }}</b>
      </div>
    </el-form>

    <template #footer>
      <el-button :disabled="loading" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="confirm">
        确认并开始切分
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-alert {
  margin-bottom: 14px;
  border-radius: var(--af-radius);
}
.hint {
  margin: 5px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--af-ink-4);
}
.hint em {
  font-style: normal;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 5px;
  background: #f1effb;
  color: #5a50d8;
}
.num-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.quick {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11.5px;
  color: var(--af-ink-4);
}
.notes {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 9px;
  background: #fdf7ec;
  border: 1px solid #f5e3c4;
}
.notes p {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  font-size: 11.5px;
  line-height: 1.65;
  color: #8a6a2a;
}
.notes p svg {
  margin-top: 2px;
  color: #c08a2e;
}
.notes b {
  color: #7a5a1c;
}
.notes--bad {
  background: #fdf0f0;
  border-color: #f2cfd0;
}
.notes--bad p,
.notes--bad p svg,
.notes--bad b {
  color: #a8322f;
}
.live {
  padding: 9px 11px;
  border-radius: 9px;
  background: #f7f6fd;
  border: 1px dashed #dcd9f1;
  font-size: 12px;
  color: var(--af-ink-3);
}
.live em {
  font-style: normal;
  color: #5a50d8;
}
.live b {
  font-family: var(--af-font-mono);
  color: var(--af-ink-1);
}
</style>
