# utils/after_refine.py
import os

from llama_index.core import Settings
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank
from llama_index.core.postprocessor import SentenceEmbeddingOptimizer
from dotenv import load_dotenv

load_dotenv()

class AfterRefine:
    """检索后优化：重排序 + 上下文压缩（对应 2.7 / 2.8）。

    输入：List[NodeWithScore] + QueryBundle
    输出：List[NodeWithScore]（精排 + 压缩后的节点）
    """

    def __init__(self, enable_rerank: bool = True, rerank_top_n: int = 3,
                 enable_compression: bool = True):
        self._reranker = (
            DashScopeRerank(model="qwen3-rerank", top_n=rerank_top_n,
                            api_key=os.getenv("ALIYUN_API_KEY"))
            if enable_rerank else None
        )
        self._compressor = (
            SentenceEmbeddingOptimizer(embed_model=Settings.embed_model,
                                       percentile_cutoff=0.5)
            if enable_compression else None
        )

    def refine(self, nodes, query_bundle):
        print("三、检索后优化：重排 + 压缩")
        if self._reranker is not None:
            nodes = self._reranker.postprocess_nodes(nodes, query_bundle=query_bundle)
        if self._compressor is not None:
            nodes = self._compressor.postprocess_nodes(nodes, query_bundle=query_bundle)
        return nodes