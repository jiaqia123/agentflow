# main.py
from utils.index import MainRAG
from utils.load_yaml import Settings

# 配置文件逼格很高
settings = Settings.from_yaml()


if __name__ == "__main__":
    rag = MainRAG({
        "top_k": settings.retrieval.top_k,
        "fusion_mode": settings.retrieval.fusion_mode,
        "num_queries": settings.retrieval.num_queries,
        "enable_hyde": settings.before_refine.enable_hyde,
        "enable_rerank": settings.after_refine.enable_rerank,
        "rerank_top_n": settings.after_refine.rerank_top_n,
        "enable_compression": settings.after_refine.enable_compression,
    })

    # for q in ["什么是 RAG？", "什么是 BM25，它是如何工作的？", "介绍一下 Python 编程语言"]:
        # rag.query(q)
    rag.query("文档上传后会经历三个步骤?")
