import { http } from './request'

/**
 * 开放检索：GET /open/retrieve?knowledge_id&query
 *
 * ⚠️ 这是**唯一一个不需要登录**的业务接口（open 就是对外开放的意思）。
 *
 * 返回 { query, answer, nodes: [{ node_id, text, score, metadata }] }
 *   - answer 是 LLM 合成答案
 *   - nodes 是重排压缩后的召回片段，metadata 里可用的键：
 *     mysql_document_id / filename_uuid / file_name / knowledge_base_id
 *
 * ⚠️ 性能：后端每次请求都会 new 一个 MainRAG（要把整个 Chroma 集合拉出来重建 BM25），
 *    实测单次 4.6~16s，前端必须给足加载状态和超时提示，不能当普通接口用。
 * ⚠️ 知识库下没有入库文档时后端返回 400。
 */
export function retrieve({ knowledge_id, query }, options = {}) {
  return http.get('/open/retrieve', { knowledge_id, query }, options)
}
