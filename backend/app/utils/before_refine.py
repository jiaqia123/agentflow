# utils/before_refine.py
from llama_index.core import QueryBundle
from llama_index.core.indices.query.query_transform import HyDEQueryTransform


class BeforeRefine:
    """检索前优化：HyDE 查询改写（对应 2.6）。

    输入：原始查询字符串
    输出：QueryBundle（携带改写后的检索向量文本）
    """

    def __init__(self, enable_hyde: bool = False):
        self.enable_hyde = enable_hyde
        # include_original=True：同时保留原始查询，避免假设答案走偏导致漏检
        self._hyde = HyDEQueryTransform(include_original=True) if enable_hyde else None

    def refine(self, question: str) -> QueryBundle:
        if self._hyde is not None:
            print("一、检索前优化：HyDE 查询改写")
            # HyDE 用 LLM 生成假设文档，放进 QueryBundle 的 embedding_strs 供向量检索使用
            return self._hyde.run(question) # 返回一个带 HyDE 假设文档的 QueryBundle（含原问题，并用假设答案做向量检索文本）。
        print("一、检索前优化：未启用，原样透传查询")
        return QueryBundle(query_str=question) # 原样透传查询
        # return question


"""
from llama_index.core import QueryBundle
qb = QueryBundle(query_str='什么是rag')
print('repr:', repr(qb))
print('str:', str(qb))
print('query_str:', qb.query_str)

repr: QueryBundle(query_str='什么是rag', image_path=None, custom_embedding_strs=None, embedding=None)
str: 什么是rag
query_str: 什么是rag


| `QueryBundle(query_str=question)` | `return question` |
|  ---|---|---|
| 类型 | LlamaIndex 的查询对象 | 普通 `str` |
| 内容 | 至少有 `query_str`，还可带 `embedding_strs` 等 | 只有字符串本身 |
"""