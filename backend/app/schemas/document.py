"""文档接口的入参模型。

注意：**documents 表里没有 status 列**（状态在 documents_chunks.status 上），
所以列表接口不提供「按文档状态过滤」这个参数。
"""

from pydantic import BaseModel, Field, field_validator


class DocumentListQuery(BaseModel):
    """文档列表查询入参（GET 的查询参数，路由里用 ``Depends()`` 注入）。"""

    # 不传就列出我名下全部文档；传了只看这个库（归属在路由里校验）
    knowledge_id: int | None = Field(None, gt=0, description="知识库 ID，不传则列出名下全部文档")
    page: int = Field(1, ge=1, description="页码，从 1 开始")
    # 上限 100：防止前端一次把整库文档拉爆
    limit: int = Field(10, ge=1, le=100, description="每页条数，上限 100")
    keyword: str | None = Field(None, max_length=255, description="按原始文件名模糊搜索")

    @field_validator("keyword")
    @classmethod
    def blank_to_none(cls, v):
        # 前端经常传 keyword=（空串），当没传处理，
        # 否则会拼出 LIKE '%%' —— 结果一样，但白白扫一遍表
        if v is None:
            return None
        v = v.strip()
        return v or None


class StoreFile(BaseModel):
    """待入库的一个文件（/store 里 files 数组的一项）。"""

    filename_uuid: str = Field(..., description="磁盘唯一名（上传接口返回的 new_filename）")
    filename_original: str = Field("", description="展示用原始文件名")


class StoreIn(BaseModel):
    """入库入参（POST /document/store 的请求体）。"""

    knowledge_id: int = Field(..., description="知识库 ID")
    files: list[StoreFile] = Field(..., description="文件列表")
    separator: str = Field("\n", description="分段标识符")
    chunk_size: int = Field(512, gt=0, description="分段最大长度")
    chunk_overlap: int = Field(50, ge=0, description="分段重叠度")
