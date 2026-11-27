from sqlalchemy import BigInteger, Column, DateTime, SmallInteger, String, func

from app.db.mysql import Base


class User(Base):
    """用户表，对应数据库 agentflow.users"""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, comment="主键")
    # 唯一索引 uk_users_username
    username = Column(String(64), nullable=False, unique=True, index=True, comment="用户名")
    # 唯一索引 uk_users_email ((nullif(email,''))) —— 空串不参与去重，允许多个用户不填邮箱
    email = Column(String(128), nullable=False, server_default="", comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希，禁止存明文")
    # tinyint unsigned：1 正常 0 冻结
    is_active = Column(SmallInteger, nullable=False, server_default="1", comment="是否冻结 1正常 0冻结")
    avatar = Column(String(512), nullable=False, server_default="", comment="头像URL")
    # 交给 MySQL 的 DEFAULT CURRENT_TIMESTAMP / ON UPDATE CURRENT_TIMESTAMP
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
