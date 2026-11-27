# utils/middle_refine.py
import jieba
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever


class MiddleRefine:
    """检索中优化：多路召回 + RRF 融合（对应 2.4 / 2.5）。

    输入：QueryBundle
    输出：List[NodeWithScore]（融合后的候选节点）

    说明：LlamaIndex 的 Multi-Query 改写实现在 QueryFusionRetriever 内部，
    因此用 num_queries 参数控制（>1 即启用），无需单独写在 BeforeRefine 里。
    """

    def __init__(self, index, nodes, top_k: int = 5,
                 num_queries: int = 1, mode: str = "reciprocal_rerank"):
        # 路1：稠密向量检索（语义匹配）
        vector_retriever = index.as_retriever(similarity_top_k=top_k)
        # 路2：BM25 稀疏检索（关键词匹配，jieba 中文分词）
        bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes, similarity_top_k=top_k,
            tokenizer=lambda text: list(jieba.cut(text)),
        )
        # 融合成单个检索器（RRF）
        self._fusion = QueryFusionRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            similarity_top_k=top_k,
            num_queries=num_queries,   # >1 启用 Multi-Query 查询扩展
            mode=mode,
            use_async=False,
            verbose=True,
        )

    def refine(self, query_bundle):
        print("二、检索中优化：向量 + BM25 多路召回 + RRF 融合")
        return self._fusion.retrieve(query_bundle)