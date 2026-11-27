import { http } from './request'

/**
 * 知识库接口。表名是 knowledge_bases，路由前缀 /knowledge。
 * 全部需要登录（Authorization: Bearer <token>）。
 *
 * 返回的知识库对象字段：
 *   id / name / description / icon_url / user_id / created_at / updated_at
 *   document_num（文档数）/ str_num（字符数）/ app_num（关联应用数，暂时恒为 0）
 */

/** 新建：POST /knowledge → 201，body { name, description?, icon_url? } */
export function createKnowledge({ name, description = '', icon_url = null }) {
  return http.post('/knowledge', { name, description, icon_url })
}

/**
 * 列表：GET /knowledge?page&limit&keyword
 *
 * ⚠️ 后端这个接口**返回的是裸数组**，没有 total / 总数（和其他列表接口不一致）。
 * 所以前端只能靠「返回条数 < limit」来判断到底了，见 KnowledgeListView 的分页处理。
 */
export function listKnowledges({ page = 1, limit = 10, keyword } = {}) {
  return http.get('/knowledge', { page, limit, keyword })
}

/** 详情：GET /knowledge/{id} */
export function getKnowledge(id) {
  return http.get(`/knowledge/${id}`)
}

/**
 * 修改：POST /knowledge/{id}/update
 * 只传要改的字段；name / description 是 NOT NULL，**不能传 null**（后端 422）。
 * icon_url 传 null 表示清空。
 */
export function updateKnowledge(id, payload) {
  return http.post(`/knowledge/${id}/update`, payload)
}

/** 删除：POST /knowledge/{id}/delete，库下还有文档时返回 409 */
export function deleteKnowledge(id) {
  return http.post(`/knowledge/${id}/delete`, {})
}
