"""文档模型，对应数据库 agentflow.documents 与 agentflow.documents_chunks。

表已存在（不是 create_all 建的），字段严格照 SHOW CREATE TABLE 抄，
两个表名都是复数，__tablename__ 写死。
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.mysql import Base


class Document(Base):
    """documents —— 文档表。"""

    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    # 库里是 int unsigned（不是 bigint），且没建外键
    user_id = Column(Integer, nullable=False, server_default="0", comment="用户编号")
    filename_uuid = Column(
        String(255), nullable=False, comment="磁盘保存名（uuid+后缀，用来定位文件）"
    )
    filename_original = Column(
        String(255), nullable=False, comment="用户上传时的原始文件名（用于展示）"
    )
    char_count = Column(Integer, nullable=False, server_default="0", comment="字符数")
    chunk_count = Column(Integer, nullable=False, server_default="0", comment="知识条数")
    knowledge_base_id = Column(
        BigInteger,
        ForeignKey("knowledge_bases.id"),
        nullable=False,
        index=True,
        comment="知识库ID",
    )
    # 时间列交给 MySQL 的 DEFAULT CURRENT_TIMESTAMP
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建于")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新于",
    )


class DocumentChunk(Base):
    """documents_chunks —— 文档分块表。"""

    __tablename__ = "documents_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uk_document_chunk_index"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_base_id = Column(BigInteger, nullable=False, comment="所属知识库")
    document_id = Column(BigInteger, nullable=False, index=True, comment="所属文档")
    chunk_index = Column(Integer, nullable=False, comment="文档内序号，从 0 开始")
    content = Column(Text, nullable=False, comment="分块正文")
    # 坑：属性名不能叫 metadata —— Base.metadata 已被 SQLAlchemy 占用，会直接报
    # InvalidRequestError。只能改属性名，用 Column("metadata", ...) 映射到真实列名。
    chunk_metadata = Column("metadata", JSON, nullable=True, comment="扩展：起止偏移等")
    token_count = Column(Integer, nullable=False, server_default="0", comment="token 数")
    vector_id = Column(String(64), nullable=True, comment="向量库点 ID")
    status = Column(
        SmallInteger, nullable=False, server_default="1", comment="0待向量化 1已入库 2失败"
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
