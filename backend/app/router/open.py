"""开放检索接口（/open）。

给一个知识库编号，去它专属的 Chroma 集合里召回片段，并合成答案。

集合命名规则和 /document/store 一致：``agentflow_kb_{knowledge_id}``，
所以调用方只要知道知识库编号就能定位到它的向量数据。

    GET /open/retrieve?knowledge_id=11&query=文档上传后会经历三个步骤?
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
# 必须在导入 app.utils.index 之前读 .env：utils/shared.py 在 import 那一刻就把 ALIYUN_API_KEY 取走了
load_dotenv(BACKEND_DIR / ".env")

from app.db.mysql import get_db                                    # noqa: E402
from app.models.knowledge import Knowledge                         # noqa: E402
from app.schemas.open import RetrieveNodeOut, RetrieveOut          # noqa: E402
from app.utils.index import MainRAG                                # noqa: E402
from app.utils.load_yaml import Settings                           # noqa: E402
from app.utils.shared import CHROMA_INTERNAL_KEYS                  # noqa: E402

router = APIRouter(prefix="/open", tags=["open"])


@router.get("/retrieve")
def retrieve(
    knowledge_id: int,
    query: str,
    db: Session = Depends(get_db),
):
    # 获取过滤参数  knowledge_id（知识库编号）、query（用户问题）
    # 前置校验
    # 1 问题不能为空
    if not query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")
    # 2 按 id 查知识库  不存在 404
    knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识库不存在")
    # 3 （补充校验）库下还没有入库文档时直接挡住：集合里没有向量时，
    #   MainRAG 里的 BM25Retriever 会拿 nodes=[] 去建索引，抛
    #   ValueError: Please pass exactly one of index, nodes, or docstore. → 接口 500
    if not knowledge.document_num:
        raise HTTPException(status_code=400, detail="该知识库还没有入库文档，无法检索")

    # 操作
    # 1 集合名用 agentflow_kb_{knowledge_id}，只召回该知识库自己的向量（入库时按库分集合）
    # 2 走 取.py 同一套 MainRAG：检索前改写 -> 向量+BM25 融合 -> 重排压缩 -> 合成答案
    settings = Settings.from_yaml()
    rag = MainRAG({
        "collection_name": f"agentflow_kb_{knowledge.id}",
        "top_k": settings.retrieval.top_k,
        "fusion_mode": settings.retrieval.fusion_mode,
        "num_queries": settings.retrieval.num_queries,
        "enable_hyde": settings.before_refine.enable_hyde,
        "enable_rerank": settings.after_refine.enable_rerank,
        "rerank_top_n": settings.after_refine.rerank_top_n,
        "enable_compression": settings.after_refine.enable_compression,
    })
    result = rag.query(query)

    # 返回数据  原问题、答案、召回片段（node_id / text / score / metadata）
    # 注：metadata 里滤掉引擎内部字段 —— _node_content 是整段节点的 JSON（又长又没用），
    #     doc_id / ref_doc_id / document_id 是 llama_index 覆写进去的随机 UUID，不是 MySQL 主键，
    #     真正能对回 documents 表的是 mysql_document_id（见 document.py 的入库注释）
    nodes = [
        RetrieveNodeOut(
            node_id=node.node_id,
            text=node.text,
            score=float(node.score) if node.score is not None else None,
            metadata={
                k: v
                for k, v in (node.metadata or {}).items()
                if not k.startswith("_") and k not in CHROMA_INTERNAL_KEYS and k != "document_id"
            },
        )
        for node in result["final_nodes"]
    ]
    return RetrieveOut(
        query=result["query"],
        answer=result["answer"],
        nodes=nodes,
    )
