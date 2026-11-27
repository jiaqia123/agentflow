from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.mysql import Base, engine
from app.router.auth import router as auth_router
from app.router.books import router as books_router
from app.router.upload import router as upload_router
from app.router.knowledge import router as knowledge_router
from app.router.document import router as document_router
from app.router.open import router as open_router


# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(books_router)
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(knowledge_router)
app.include_router(document_router)
app.include_router(open_router)

# 静态资源：把 backend/data 挂到 /static，
# 上传的图片/文档才能通过 /static/uploads/... 和 /static/documents/... 访问
# 注意 StaticFiles 在挂载那一刻就检查目录是否存在，所以先 mkdir 兜底
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=DATA_DIR), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
