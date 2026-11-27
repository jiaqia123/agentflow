from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel, Field
from pathlib import Path as FilePath

app = FastAPI()

class BookCreate(BaseModel):
    # title: str
    # author: str
    # title: str | None = None
    # author: str | None = None
    title: str = Field(..., min_length=1, max_length=50, description="书名")
    author: str = Field(..., min_length=1, max_length=20, description="作者")

# 访问地址示例  http://127.0.0.1:8000/book1/123/python
@app.get("/book1/{book_id}/{title}")
def book1(
    book_id: int = Path(..., ge=1, le=1000, description="书籍的ID，范围1-1000"),
    title: str = Path(..., min_length=1, max_length=50, description="书名"),
):
    return {"book_id": book_id, "title": title}

# 访问地址示例  http://127.0.0.1:8000/book2?author=python&skip=0&limit=10
@app.get("/book2")
def book2(
    author: str | None = Query(None, min_length=1, max_length=20, description="作者名"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(10, ge=1, le=50, description="返回的最大记录数"),
):
    return {"author": author, "skip": skip, "limit": limit}

# 请求体示例  {"keyword": "三体"}
@app.post("/book3")
def book3(keyword: str = Body(..., embed=True, description="搜索关键词")):
    return {"keyword": keyword}

# 请求体示例  {"title": "三体", "author": "刘慈欣"}
@app.post("/book4")
def book4(book: BookCreate):
    return book

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run("02_获取过滤参数:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run(f"{FilePath(__file__).stem}:app", host="0.0.0.0", port=8000, reload=True)
