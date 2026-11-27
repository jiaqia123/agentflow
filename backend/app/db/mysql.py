import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ljqiang123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "agentflow")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # 取连接前先探测，避免用到已断开的连接
    pool_recycle=3600,  # 1 小时回收，避免 MySQL 空闲超时
    echo=os.getenv("SQL_ECHO", "0") == "1",  # SQL_ECHO=1 时打印 SQL
)

# 创建 SessionLocal 类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建 Base 类
class Base(DeclarativeBase):
    pass

# 创建 get_db 函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
