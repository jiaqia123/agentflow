from pydantic import BaseModel, Field

class BookCreate(BaseModel):
    title: str = Field(min_length=4)
    author: str

class BookUpdate(BaseModel):
    title: str | None = None  # 不传则默认 None，不修改
    author: str | None = None
