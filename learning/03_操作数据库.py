from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import engine, get_db
from models import Base, Book

from pathlib import Path as FilePath

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI()


# ====== Pydantic 模型  后期单独放到 schemas目录下 ======

class BookCreate(BaseModel):
    title: str = Field(min_length=4)
    author: str


class BookUpdate(BaseModel):
    title: str | None = None  # 不传则默认 None，不修改
    author: str | None = None


# ====== API 路由 ======

# 增
@app.post("/books", status_code=201)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    db_book = Book(**book_in.model_dump())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


# 查所有
@app.get("/books")
def read_books(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    skip = (page - 1) * limit
    books = db.query(Book).offset(skip).limit(limit).all()
    return books


# 查单个
@app.get("/books/{book_id}")
def read_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return book


# 改
@app.post("/books/{book_id}/update")
def update_book(book_id: int, book_update: BookUpdate, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if book_update.title is not None:
        book.title = book_update.title
    if book_update.author is not None:
        book.author = book_update.author

    db.commit()
    db.refresh(book)
    return book


# 删
@app.post("/books/{book_id}/delete")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    db.delete(book)
    db.commit()
    return {"message": "删除成功"}


if __name__ == "__main__":
    import uvicorn

    # uvicorn.run("02_获取过滤参数:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run(f"{FilePath(__file__).stem}:app", host="0.0.0.0", port=8000, reload=True)
