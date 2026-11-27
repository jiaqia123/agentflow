from pydantic import BaseModel, Field, field_validator


class KnowledgeCreate(BaseModel):
    """新建知识库入参（user_id 不在入参里，从 token 取）"""

    name: str = Field(..., min_length=1, max_length=64, description="知识库名称")
    # 库里是 NOT NULL DEFAULT ''，所以默认值给 ""，不要给 None
    description: str = Field("", max_length=256, description="描述，可不传")
    icon_url: str | None = Field(None, max_length=512, description="图标地址，可不传")


class KnowledgeUpdate(BaseModel):
    """修改入参：三个字段都可选，只改「请求里真正传了」的字段"""

    name: str | None = Field(None, min_length=1, max_length=64, description="知识库名称")
    description: str | None = Field(None, max_length=256, description="描述")
    icon_url: str | None = Field(None, max_length=512, description="图标地址，传 null 表示清空")

    @field_validator("name", "description")
    @classmethod
    def not_null(cls, v):
        # 这两列数据库是 NOT NULL，显式传 null 直接 422 拦掉，
        # 不然会把 None 写进库、报一个看不懂的 IntegrityError。
        if v is None:
            raise ValueError("不能为 null；不想修改这个字段就不要传它")
        return v
