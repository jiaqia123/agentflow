# rag_main.py
from llama_index.core.response_synthesizers import get_response_synthesizer

from .shared import build_index_and_nodes
from .before_refine import BeforeRefine
from .middle_refine import MiddleRefine
from .after_refine import AfterRefine

class MainRAG: 
    def __init__(self, config: dict):
        self.config = config
        # 共享资源：索引 + 节点只构建一次；集合名默认 agentflow，在线检索传 agentflow_kb_{知识库id}
        index, nodes = build_index_and_nodes(
            collection_name=config.get("collection_name", "agentflow"),
        )

        # 三个模块按配置初始化（对应 1.4 的“算子可插拔”）
        self.before_refine = BeforeRefine(
            enable_hyde=config.get("enable_hyde", False),
        )
        self.middle_refine = MiddleRefine(
            index, nodes,
            top_k=config.get("top_k", 5),
            num_queries=config.get("num_queries", 1),
            mode=config.get("fusion_mode", "reciprocal_rerank"),
        )
        self.after_refine = AfterRefine(
            enable_rerank=config.get("enable_rerank", True),
            rerank_top_n=config.get("rerank_top_n", 3),
            enable_compression=config.get("enable_compression", True),
        )
        # 生成模块：把最终节点合成答案（对应 RetrieverQueryEngine 内部职责）
        # 作用：按指定模式创建一个「把检索节点合成最终答案」的合成器对象
        # 参数：response_mode 声明「把检索到的节点怎么塞进 LLM、怎么生成答案」
        # - compact 尽量把多个节点压进一次（或尽量少次）LLM 调用里生成答案
        # - simple_summarize 简单拼接后一次总结
        self.synthesizer = get_response_synthesizer(response_mode="compact")

    def query(self, question: str) -> dict:
        # 检索前：查询改写（不启用则原样透传）
        query_bundle = question
        if self.config.get("enable_before_refine", True):
            query_bundle = self.before_refine.refine(question)
        else:
            from llama_index.core import QueryBundle 
            query_bundle = QueryBundle(query_str=question)

        # 检索中：多路召回 + 融合（核心环节，通常必开）
        nodes = self.middle_refine.refine(query_bundle)

        # 检索后：重排 + 压缩
        if self.config.get("enable_after_refine", True):
            nodes = self.after_refine.refine(nodes, query_bundle)

        # 生成：用最终节点合成答案 -> 用问题（query_bundle）和检索到的节点（nodes）调用 LLM，合成最终答案。  self.synthesizer 就是合成器对象 
        response = self.synthesizer.synthesize(query_bundle, nodes=nodes)

        print("=" * 60)
        print(f"问题：{question}")
        print("最终喂给 LLM 的参考片段：")
        for i, n in enumerate(response.source_nodes, 1):
            score = f"{n.score:.4f}" if n.score is not None else "N/A"
            print(f"  {i}. [{score}] {n.text[:50]}...")
        print(f"答案：{response.response}")
        print("=" * 60 + "\n")

        return {"query": question,
                "final_nodes": response.source_nodes,
                "answer": str(response.response)}