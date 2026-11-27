"""文档接口（骨架）。

一个知识库下挂多份文档，文档要经过三步处理流水线：

    上传文件 -> 切分成片段 -> 向量化入库

上传落盘规则：backend/data/documents/<YYMMDD>/<全球唯一文件名>
路由前缀是 /document，对应的数据库表是 **documents**（表名用复数）。
"""

import os
from datetime import datetime
from pathlib import Path
import uuid

import chromadb
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.utils import get_tokenizer
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.mysql import get_db
from app.models.auth import User
from app.models.document import Document, DocumentChunk
from app.models.knowledge import Knowledge
from app.router.knowledge import get_current_user, get_own_knowledge
from app.schemas.document import DocumentListQuery, StoreIn

router = APIRouter(prefix="/document", tags=["document"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = BACKEND_DIR / "data" / "documents"
CHROMA_DIR = BACKEND_DIR / "data" / "chroma_db"

# pdf / word / txt / excel / markdown
ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx"}
CHUNK_SIZE = 1024 * 1024
MAX_SIZE = 50 * 1024 * 1024

# 向量化相关（照 app/存.py）
EMBED_MODEL = "text-embedding-v3"
EMBED_BATCH_SIZE = 10          # text-embedding-v3 单批最多 10

# 显式给路径：main.py 没有 load_dotenv，且 os.getenv 读不到 .env
load_dotenv(BACKEND_DIR / ".env")
TOKENIZER = get_tokenizer()


# ------------------------------------------------------------------ 接口
@router.post("/upload")
def upload_document(file: UploadFile = File(...)):
    """上传文档：pdf、word、txt、xls、xlsx、md。"""
    # 1 文件名只取末段（挡 ../../），后缀必须在白名单里
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持：{', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    # 2 目录名按天：data/documents/240814/
    day_dir = DOCUMENT_DIR / datetime.now().strftime("%y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    # 3 全局唯一文件名
    new_filename = f"{uuid.uuid4().hex}{suffix}"
    dest = day_dir / new_filename

    # 4 边读边写 + 大小上限
    size = 0
    try:
        file.file.seek(0)
        with dest.open("wb") as f:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(status_code=413, detail="文件过大，上限 50MB")
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)   # 只删自己，不删目录（目录按天共享）
        raise

    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 5 返回原文件名、新文件名、访问地址、文件大小
    return {
        "original_filename": filename,
        "new_filename": new_filename,
        "url": f"/static/documents/{day_dir.name}/{new_filename}",
        "size": size,
    }


class SplitIn(BaseModel):
    """切分参数。"""

    new_filename: str = Field(..., description="上传接口返回的文件唯一标识")
    separator: str = Field("\n", description="分段标识符")
    chunk_size: int = Field(512, gt=0, description="分段最大长度")
    chunk_overlap: int = Field(50, ge=0, description="分段重叠度")


@router.post("/split")
def split_document(params: SplitIn):
    """切分文档，只返回切分后的数据（不向量化、不入库）。"""
    # 1 接收前端传递的 filename 唯一标识
    raw = (params.new_filename or "").strip()
    name = raw.replace("\\", "/").split("/")[-1]
    if not name or name != raw or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="new_filename 非法")

    path = next(
        (d / name for d in sorted(DOCUMENT_DIR.iterdir()) if (d / name).is_file()),
        None,
    )
    if path is None:
        raise HTTPException(status_code=404, detail="文件不存在，请先上传")

    # 2 加载文档（照 app/存.py 的写法）
    documents = SimpleDirectoryReader(input_files=[str(path)]).load_data()
    if not documents:
        # 读取器解析失败时是「跳过」而不是抛异常，这里必须自己兜住
        raise HTTPException(status_code=400, detail=f"文件解析失败，读不出内容（{path.suffix}）")

    # 3 切分
    nodes = SentenceSplitter(
        separator=params.separator,
        chunk_size=params.chunk_size,
        chunk_overlap=params.chunk_overlap,
    ).get_nodes_from_documents(documents)

    # 4 返回切分后的数据 —— 到此为止，不做 embedding、不建 index、不写向量库
    return {
        "new_filename": name,
        "total": len(nodes),
        "chunks": [
            {
                "index": i,
                "text": node.get_content(),
                "char_start": node.start_char_idx,
                "char_end": node.end_char_idx,
            }
            for i, node in enumerate(nodes)
        ],
    }

# ---------------------------------------------------------------- Chroma 客户端
_chroma_client = None


def get_chroma_client():
    """Chroma 持久化客户端，进程内复用（每次 new 都要初始化，很慢）。"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def find_document_file(name: str) -> Path | None:
    """按 filename_uuid 在 data/documents/<YYMMDD>/ 下找磁盘文件。

    逐天目录拼路径找，不用 glob —— 免得名字里的 * ? [ ] 被当通配符。
    找不到返回 None，由调用方决定报什么错。
    """
    raw = (name or "").strip()
    safe = raw.replace("\\", "/").split("/")[-1]
    if not safe or safe != raw or safe in {".", ".."}:
        return None
    return next(
        (d / safe for d in sorted(DOCUMENT_DIR.iterdir()) if (d / safe).is_file()),
        None,
    )


def build_nodes(path: Path, separator: str, chunk_size: int, chunk_overlap: int):
    """加载 + 切分，返回 (nodes, 全文)。"""
    documents = SimpleDirectoryReader(input_files=[str(path)]).load_data()
    if not documents:
        # 读取器解析失败时是「跳过」而不是抛异常，这里必须自己兜住
        raise ValueError(f"文件解析失败，读不出内容（{path.suffix}）")
    nodes = SentenceSplitter(
        separator=separator,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ).get_nodes_from_documents(documents)
    return nodes, "".join(d.text for d in documents)


# ---------------------------------------------------------------- 入参
# 请求体统一放 app/schemas/document.py（StoreFile / StoreIn），这里只做注入


# ---------------------------------------------------------------- 接口
@router.post("/store")
def store_document(
    params: StoreIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 明确：这接口特殊，不要用ai生成思路  我自己手写
    # 简单步骤
    # 1 拿 knowledge_id、文件列表、切分参数，JWT 取 user_id
    # 2 校验知识库归属、文件在磁盘上、同库同文件未入库
    # 3 按文件再切一遍（不吃 /split 预览），同一批 nodes 写 MySQL + 该库 Chroma 集合
    # 4 失败则删掉本条已写入数据；成功则更新计数并返回
    # 详细步骤
    # 获取过滤参数  knowledge_id；文件列表（每项：filename_uuid 磁盘唯一名，filename_original 展示原名）
    #              separator 分段标识符、chunk_size 分段最大长度、chunk_overlap 分段重叠度
    #              请求头 Authorization，解析 JWT 拿 user_id（没有/无效报错、有效继续）
    # 前置校验
    # 1 按 id 查知识库  不存在 404；knowledge.user_id 必须等于当前用户  不是本人 403
    # 2 文件列表不能为空；每个 filename_uuid 在 data/documents 下能找到文件  找不到 404
    # 3 同一 knowledge_base_id + filename_uuid 已入库则跳过（避免重复切两份向量）
    # 操作数据库
    # 1 不吃 /split 预览：按存.py 重新加载、再切一遍（用前端传的 separator / chunk_size / chunk_overlap）；同一批 nodes 写 MySQL 和 Chroma，保证 vector_id 一致
    # 2 MySQL  documents（user_id、filename_uuid、filename_original、char_count、chunk_count、knowledge_base_id）
    #          表无 path，定位文件只用 filename_uuid
    #          documents_chunks（knowledge_base_id、document_id、chunk_index、content、metadata、token_count、vector_id）
    # 3 向量库 语法见存.py（加载→切分→向量化→存储）
    #          集合名用 agentflow_kb_{knowledge_base_id}，每个知识库单独集合，避免数据污染
    #          后续在线检索只查自己的集合 ⭐️
    #          node.metadata 带上 knowledge_base_id、document_id、filename_uuid，方便按文档删向量
    # 4 双写：MySQL 和 Chroma 都成功才算这条文档入库；失败不打 status，直接删掉本条已写入的 documents / documents_chunks / Chroma 向量，也不加计数
    # 5 成功后回写 documents.char_count / chunk_count，以及 knowledge_bases.document_num / str_num
    # 返回数据  成功几个、跳过/失败哪个文件、切了多少块、知识库最新 document_num
    """把文档切分后写进 MySQL + 该知识库专属的 Chroma 集合。"""
    # ===== 前置校验 =====
    api_key = os.getenv("ALIYUN_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="缺少 ALIYUN_API_KEY，无法向量化")

    # 1 按 id 查知识库  不存在 404；不是本人 403
    knowledge = db.query(Knowledge).filter(Knowledge.id == params.knowledge_id).first()
    if knowledge is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if knowledge.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该知识库")

    # 2 文件列表不能为空；每个 filename_uuid 都要能在磁盘上找到
    if not params.files:
        raise HTTPException(status_code=400, detail="文件列表不能为空")
    paths: dict[str, Path] = {}
    for item in params.files:
        path = find_document_file(item.filename_uuid)
        if path is None:
            raise HTTPException(status_code=404, detail=f"文件不存在：{item.filename_uuid}")
        paths[item.filename_uuid] = path

    # ===== 向量库 & embedding（集合按知识库隔离，后续检索只查自己的集合）=====
    collection_name = f"agentflow_kb_{knowledge.id}"
    collection = get_chroma_client().get_or_create_collection(name=collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    Settings.embed_model = DashScopeEmbedding(
        model_name=EMBED_MODEL,
        api_key=api_key,
        embed_batch_size=EMBED_BATCH_SIZE,
    )

    # ===== 逐文件入库 =====
    succeeded, skipped, failed = [], [], []
    total_chunks = 0

    for item in params.files:
        # 3 同一 knowledge_base_id + filename_uuid 已入库则跳过
        exists = (
            db.query(Document.id)
            .filter(
                Document.knowledge_base_id == knowledge.id,
                Document.filename_uuid == item.filename_uuid,
            )
            .first()
        )
        if exists is not None:
            skipped.append(item.filename_uuid)
            continue

        vector_ids: list[str] = []
        try:
            # 1 不吃 /split 预览，按存.py 重新加载 + 再切一遍
            nodes, full_text = build_nodes(
                paths[item.filename_uuid],
                params.separator,
                params.chunk_size,
                params.chunk_overlap,
            )
            if not nodes:
                raise ValueError("切分结果为空")

            # 先落 documents 换自增 id：vector_id 要用它做前缀，两边才能对上
            doc = Document(
                user_id=current_user.id,
                filename_uuid=item.filename_uuid,
                filename_original=item.filename_original or item.filename_uuid,
                char_count=len(full_text),
                chunk_count=len(nodes),
                knowledge_base_id=knowledge.id,
            )
            db.add(doc)
            db.flush()          # 拿 doc.id，还没 commit

            base_meta = {
                "knowledge_base_id": knowledge.id,
                # ⚠️ 存进 Chroma 后 document_id 会被 llama_index 覆写（见下方说明），
                #    所以真正能用的 MySQL 主键另起一个键名
                "mysql_document_id": doc.id,
                "document_id": doc.id,
                "filename_uuid": item.filename_uuid,
            }
            for i, node in enumerate(nodes):
                # 同一批 nodes 写两边：node.id_ 既是 Chroma 的点 ID，也是 MySQL 的 vector_id
                node.id_ = f"{doc.id}#{i}"
                vector_ids.append(node.id_)
                # metadata 带上文档信息，方便以后按文档删向量。
                # ⚠️ 坑：llama_index 的 node_to_metadata_dict() 会**无条件覆写**
                #    metadata["document_id"] = node.ref_doc_id（一个 UUID），
                #    所以 Chroma 里看到的 document_id 不是我们的主键 —— 按文档删向量请用
                #    mysql_document_id 或 filename_uuid 做 where 条件。
                node.metadata = {**node.metadata, **base_meta}
                content = node.get_content()
                db.add(
                    DocumentChunk(
                        knowledge_base_id=knowledge.id,
                        document_id=doc.id,
                        chunk_index=i,
                        content=content,
                        chunk_metadata={
                            "char_start": node.start_char_idx,
                            "char_end": node.end_char_idx,
                        },
                        token_count=len(TOKENIZER(content)),
                        vector_id=node.id_,
                    )
                )

            # 3 向量化 + 存储（存.py 的第 3、4 步）
            VectorStoreIndex(nodes, storage_context=storage_context)
            # 双写都成功才提交
            db.commit()
        except Exception as exc:                # noqa: BLE001
            # 4 失败：MySQL 这边整条回滚（documents / documents_chunks 都还没 commit），
            #    Chroma 那边把这一批 id 删掉 —— 起点可能已经写进去了一部分
            db.rollback()
            if vector_ids:
                try:
                    collection.delete(ids=vector_ids)
                except Exception:               # noqa: BLE001
                    pass
            failed.append({"filename_uuid": item.filename_uuid, "reason": str(exc)[:200]})
            continue

        succeeded.append(
            {
                "document_id": doc.id,
                "filename_uuid": item.filename_uuid,
                "filename_original": doc.filename_original,
                "char_count": doc.char_count,
                "chunk_count": doc.chunk_count,
            }
        )
        total_chunks += doc.chunk_count

    # 5 成功后累加 knowledge_bases 的 document_num / str_num
    #   （documents.char_count / chunk_count 在插入时就写好了，失败已回滚，不用再补）
    if succeeded:
        knowledge.document_num = (knowledge.document_num or 0) + len(succeeded)
        knowledge.str_num = (knowledge.str_num or 0) + sum(x["char_count"] for x in succeeded)
        db.commit()
        db.refresh(knowledge)

    # 返回数据：成功几个、跳过/失败哪个文件、切了多少块、知识库最新 document_num
    return {
        "knowledge_id": knowledge.id,
        "collection": collection_name,
        "success_count": len(succeeded),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "chunk_count": total_chunks,
        "document_num": knowledge.document_num,
        "str_num": knowledge.str_num,
        "success": succeeded,
        "skipped": skipped,
        "failed": failed,
    }


# ---------------------------------------------------------------- 文档列表
@router.get("/list")
def list_documents(
    params: DocumentListQuery = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """文档列表：列出当前用户（某个知识库下）已入库的文档。

    —— 思路 ——

    1 获取参数并过滤
      knowledge_id  知识库 ID（可选：不传就列出我名下全部文档；传了就只看这个库）
      page / limit  分页参数（默认 1 / 10，limit 上限 100，防止一次拉爆）
      keyword       按原始文件名模糊搜索（可选，空则不过滤）
      注：documents 表**没有 status 列**（状态在 documents_chunks.status 上），
          所以不按状态过滤
      入参统一放 app/schemas/document.py 的 DocumentListQuery，用 Depends() 注入
      请求头 Authorization，解析 JWT 拿 user_id（没有 / 过期 / 无效 → 401）
      归属过滤：查询条件里直接带 user_id = 当前用户，别人的文档查不出来
      传了 knowledge_id 时先校验知识库归属：不是本人的 → 404（不区分「不存在」和「不是你的」）

    2 操作数据库
      照 knowledge.py 的 read_knowledges 写法：先拼 query，再按需 filter，最后排序分页
      query = documents 表 filter(user_id = 当前用户)
        + knowledge_base_id 过滤（传了才加）
        + filename_original LIKE %keyword%（传了才加）
      排序：created_at 倒序（新传的排前面）
      分页：offset = (page - 1) * limit、limit(limit)；
            total 必须在加 offset/limit **之前** count，否则永远等于当页条数
      单条返回字段：id、filename_uuid、filename_original、char_count、chunk_count、
                    knowledge_base_id、created_at
        - 不要返回 content 正文（正文在 documents_chunks 里，列表带上会很大）
        - 下载 / 预览地址：/static/documents/<YYMMDD>/<filename_uuid>
          （表里没存 path 和日期，定位文件一律只用 filename_uuid）

    3 返回
      total  总条数（供前端算页数）
      page、limit  回显入参
      items  文档列表（上面那些字段）
    """
    # ===== 1 获取参数并过滤 =====
    # 只查自己的（入参见 app/schemas/document.py 的 DocumentListQuery）
    query = db.query(Document).filter(Document.user_id == current_user.id)

    # 传了 knowledge_id：先校验归属（别人的库一律 404），再按库过滤
    if params.knowledge_id is not None:
        get_own_knowledge(params.knowledge_id, current_user, db)
        query = query.filter(Document.knowledge_base_id == params.knowledge_id)

    # keyword：按原始文件名模糊搜索（schemas 里已把空串转成 None，传了才加）
    if params.keyword:
        query = query.filter(Document.filename_original.like(f"%{params.keyword}%"))

    # ===== 2 操作数据库 =====
    total = query.count()                    # 先 count，再加 offset/limit
    rows = (
        query.order_by(Document.created_at.desc())
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
        .all()
    )

    # ===== 3 返回 =====
    return {
        "total": total,
        "page": params.page,
        "limit": params.limit,
        "items": [
            {
                "id": d.id,
                "filename_uuid": d.filename_uuid,
                "filename_original": d.filename_original,
                "char_count": d.char_count,
                "chunk_count": d.chunk_count,
                "knowledge_base_id": d.knowledge_base_id,
                "created_at": d.created_at,
            }
            for d in rows
        ],
    }

