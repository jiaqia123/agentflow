import { http } from './request'

/**
 * 文档接口，前缀 /document。三步流水线：上传 → 切分 → 入库。
 * 落盘规则：backend/data/documents/<YYMMDD>/<uuid>.<后缀>
 */

/**
 * 1 上传：POST /document/upload（multipart/form-data，字段名固定 file）
 * 返回 { original_filename, new_filename, url, size }
 *   - new_filename 是后续切分/入库要用的唯一标识
 *   - 后端只认后缀白名单：.pdf .doc .docx .txt .md .xls .xlsx，上限 50MB
 * ⚠️ 后端这个接口**没有做鉴权**（upload / split 都不校验 token）。
 *    前端仍然带上 Authorization —— 后端现在忽略它，将来加上鉴权前端就不用改了。
 */
export function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return http.upload('/document/upload', form)
}

/**
 * 2 切分预览：POST /document/split（JSON）
 * body { new_filename, separator, chunk_size, chunk_overlap }
 * 返回 { new_filename, total, chunks: [{ index, text, char_start, char_end }] }
 * ⚠️ 只切分，不向量化、不入库。
 * ⚠️ chunk_size 的单位是 **token 不是字符**（llama_index 的 SentenceSplitter），
 *    512 大约能装 500~900 个汉字，别按字符数理解。
 */
export function splitDocument({ new_filename, separator = '\n', chunk_size = 512, chunk_overlap = 50 }) {
  return http.post('/document/split', { new_filename, separator, chunk_size, chunk_overlap })
}

/**
 * 3 入库：POST /document/store（JSON，**需要 token**）
 * body { knowledge_id, files: [{ filename_uuid, filename_original }], separator, chunk_size, chunk_overlap }
 * 返回汇总：{ success_count, skipped_count, failed_count, chunk_count,
 *            document_num, str_num, success[], skipped[], failed[] }
 *   - 已入库过的同一文件会进 skipped
 *   - 单个文件失败进 failed（附 reason），不影响其他文件
 */
export function storeDocuments({ knowledge_id, files, separator = '\n', chunk_size = 512, chunk_overlap = 50 }) {
  return http.post('/document/store', {
    knowledge_id,
    files,
    separator,
    chunk_size,
    chunk_overlap
  })
}

/**
 * 列表：GET /document/list?knowledge_id&page&limit&keyword
 * 返回 { total, page, limit, items: [{ id, filename_uuid, filename_original,
 *        char_count, chunk_count, knowledge_base_id, created_at }] }
 * ⚠️ items 里**没有 url**，表里也没存日期目录，前端拼不出 /static/documents/<日期>/<uuid>，
 *    所以文档列表只做展示，不提供下载链接（已在交付说明里列为后端待补项）。
 * ⚠️ knowledge_id 不传 = 列出当前用户名下全部文档。
 */
export function listDocuments({ knowledge_id, page = 1, limit = 10, keyword } = {}) {
  return http.get('/document/list', { knowledge_id, page, limit, keyword })
}

/**
 * 通用图片上传：POST /upload/image（multipart/form-data，字段名 image）
 * 返回 { filename, size, path, url, dir }，上限 10MB，只收 .jpg/.jpeg/.png/.gif/.webp/.bmp/.tif/.tiff
 * 用来给知识库设置图标 —— icon_url 存这个 url（/static/uploads/...）
 */
export function uploadImage(file) {
  const form = new FormData()
  form.append('image', file)
  return http.upload('/upload/image', form, { auth: false })
}
