# rag_tools/shared.py
# 全局共享：Settings（embedding + LLM）、文档、索引、检索器
import os

from llama_index.core import Settings, Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.llms.dashscope import DashScope
from dotenv import load_dotenv

load_dotenv()

# LlamaIndex 写入 Chroma 时会把这些内部字段扁平进 metadata，接口返回时需要滤掉
CHROMA_INTERNAL_KEYS = ("_node_content", "_node_type", "doc_id", "ref_doc_id")

API_KEY = os.getenv("ALIYUN_API_KEY")

# ---- 全局配置：embedding + LLM（对应 2.2）----
Settings.embed_model = DashScopeEmbedding(
    model_name="text-embedding-v3", api_key=API_KEY,
)
Settings.llm = DashScope(
    model_name="qwen3.7-max", api_key=API_KEY, temperature=0.1,
)

# ---- 教学文档（对应 2.3）----
# RAW_DOCS = [
#     "Python 是一种高级、解释型的编程语言。它由 Guido van Rossum 创建，于 1991 年首次发布，强调代码可读性和简洁性。",
#     "RAG（检索增强生成，Retrieval-Augmented Generation）将信息检索系统与大语言模型相结合，以生成更准确、信息更丰富的回答。",
#     "机器学习是人工智能的一个子集，使系统能够从数据中学习和改进而无需显式编程。基本概念包括监督学习、无监督学习和强化学习。",
#     "Transformer 架构由 Vaswani 等人在 2017 年的论文《Attention Is All You Need》中提出，彻底改变了自然语言处理领域。",
#     "ChatGPT 是由 OpenAI 开发的对话式人工智能模型，基于 GPT（生成式预训练 Transformer）架构。",
#     "向量检索是一种基于向量表示来查找相似项的技术，常用于推荐系统和信息检索中，能捕获语义相似性。",
#     "BM25 是一种经典的排序函数，搜索引擎用它来估算文档与查询的相关性，基于概率检索框架，擅长精确关键词匹配。",
#     "HyDE（假设文档嵌入）是一种先由 LLM 生成假设性答案、再用它进行检索的查询改写技术。",
#     "重排序（Reranking）使用更精确但成本更高的模型重新排列检索结果，可显著提升最终排序质量。",
#     "上下文压缩（Context Compression）通过只保留最相关的句子来缩短检索文档，从而在 LLM 上下文窗口中容纳更多有效信息。",
# ]


def build_index_and_nodes(collection_name: str = "agentflow"):

    import chromadb
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.core.schema import TextNode
    from .load_yaml import ROOT_PATH

    chroma_client = chromadb.PersistentClient(path= ROOT_PATH / "data" / "chroma_db")
    chroma_collection = chroma_client.get_or_create_collection(name=collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)

    # BM25 需要节点文本：从 Chroma 取出全部文档重建节点
    chroma_data = chroma_collection.get(include=["documents", "metadatas"])
    nodes = [
        TextNode(
            text=text,
            id_=doc_id,
            metadata=meta or {},
        )
        for doc_id, text, meta in zip(
            chroma_data["ids"],
            chroma_data["documents"],
            chroma_data["metadatas"] or [{}] * len(chroma_data["ids"]),
        )
    ]

    """文档 -> 节点 -> 向量索引（对应 2.3）。返回 (index, nodes)。"""
    # documents = [Document(text=t) for t in RAW_DOCS]
    # splitter = SentenceSplitter(chunk_size=256, chunk_overlap=32)
    # nodes = splitter.get_nodes_from_documents(documents)
    # index = VectorStoreIndex(nodes)
    print(f"  [shared] 索引构建完成，节点数：{len(nodes)}")
    return index, nodes