from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func

from app.db.mysql import Base


class Knowledge(Base):
    """知识库表，对应数据库 agentflow.knowledge_bases

    注意：**类名/文件名是 knowledge，表名是 knowledge_bases**，两者不一致，
    所以 __tablename__ 必须写死，不能靠 SQLAlchemy 自动推导。
    """

    __tablename__ = "knowledge_bases"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, comment="主键")
    name = Column(String(64), nullable=False, comment="知识库名称")
    # NOT NULL DEFAULT '' —— 不填时存空串，绝不能给 None
    description = Column(String(256), nullable=False, server_default="", comment="知识库描述")
    # 唯一允许为 NULL 的业务列
    icon_url = Column(String(512), nullable=True, comment="图标地址（上传后存 URL 或路径）")
    # 外键 users.id（ON DELETE RESTRICT），索引 idx_knowledge_bases_user_id
    user_id = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="创建者 ID",
    )
    # 交给 MySQL 的 DEFAULT CURRENT_TIMESTAMP / ON UPDATE CURRENT_TIMESTAMP
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    # 统计字段，由系统维护（建文档/应用时再改），接口不开放给前端
    document_num = Column(Integer, nullable=False, server_default="0", comment="文档数")
    str_num = Column(Integer, nullable=False, server_default="0", comment="字符数")
    app_num = Column(Integer, nullable=False, server_default="0", comment="关联应用数")
