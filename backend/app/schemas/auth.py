from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    """注册入参：用户名、密码、邮箱（可选）"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, description="密码明文，入库前哈希")
    # 邮箱可选；前端传空串 "" 时归一化为 None，走“未填邮箱”分支
    email: EmailStr | None = Field(None, description="邮箱，可不传")

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        # bcrypt 只处理前 72 字节，超长直接拒绝，避免静默丢字符
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长（UTF-8 编码后不能超过 72 字节）")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def blank_email_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class UserLogin(BaseModel):
    """登录入参：用户名、密码"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, description="密码明文")


class UserOut(BaseModel):
    """对外返回的用户信息 —— 绝不包含 hashed_password"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    avatar: str
    is_active: int
    created_at: datetime
