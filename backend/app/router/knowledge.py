"""知识库接口。

路由前缀是 /knowledge，对应的数据库表却是 **knowledge_bases**（表名和路由名不一致）。

所有接口都需要登录：从请求头 ``Authorization: Bearer <token>`` 里解出用户 ID，
再按 ``user_id`` 过滤数据 —— 每个人只能看到、也只能操作自己的知识库。

    Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
                            ↑ 就是 /auth/login 返回的那个 token（注意 Bearer 后面有个空格）
"""

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.mysql import get_db
from app.models.auth import User
from app.models.knowledge import Knowledge
# 密钥和算法沿用 auth.py 里那一份，保证「签发」和「校验」用的是同一把
from app.router.auth import JWT_ALGORITHM, JWT_SECRET_KEY
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# auto_error=False：请求头缺失时不要 FastAPI 默认的 403，改成我们自己抛 401，提示更清楚
bearer_scheme = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------ 公共依赖
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 ``Authorization: Bearer <token>`` 解析出当前登录用户。

    其他 router 也要鉴权的话，可以复用这个函数：``Depends(get_current_user)``。
    """
    # 1 请求头里必须带凭证
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="未登录：请求头缺少 Authorization: Bearer <token>",
        )

    # 2 验签 + 解出用户 ID
    #   payload 的 key 必须和 auth.py 登录时写入的一致 —— 那边写的是 user_id
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        user_id = int(payload["user_id"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        # KeyError：payload 里没有 user_id；ValueError：user_id 不是数字
        raise HTTPException(status_code=401, detail="身份凭证无效，请重新登录")

    # 3 按 ID 查库：用户必须还在，且没被冻结
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在，请重新登录")
    if user.is_active != 1:
        raise HTTPException(status_code=403, detail="账号已被冻结，请联系管理员")
    return user


def get_own_knowledge(knowledge_id: int, user: User, db: Session) -> Knowledge:
    """取「当前用户自己的」知识库。

    查询条件里直接带上 ``user_id``，别人的知识库查不出来一律 404 ——
    不区分「不存在」和「不是你的」，免得暴露别人数据的 ID 是否存在。
    """
    knowledge = (
        db.query(Knowledge)
        .filter(Knowledge.id == knowledge_id, Knowledge.user_id == user.id)
        .first()
    )
    if knowledge is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return knowledge


# ------------------------------------------------------------------ 接口
@router.post("", status_code=201)
def create_knowledge(
    knowledge_in: KnowledgeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建知识库。"""
    # 1 同一用户下不允许重名（业务规则，库里没有建唯一索引）
    exists = (
        db.query(Knowledge.id)
        .filter(
            Knowledge.user_id == current_user.id,
            Knowledge.name == knowledge_in.name,
        )
        .first()
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="同名知识库已存在")

    # 2 入库。user_id 只认 token 里的，不接受前端传，防止替别人建库
    db_knowledge = Knowledge(**knowledge_in.model_dump(), user_id=current_user.id)
    db.add(db_knowledge)
    db.commit()
    db.refresh(db_knowledge)

    # 3 返回数据
    return db_knowledge


@router.get("")
def read_knowledges(
    page: int = 1,
    limit: int = 10,
    keyword: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页列出当前用户的知识库，keyword 可按名称模糊搜索。"""
    # 1 只查自己的
    query = db.query(Knowledge).filter(Knowledge.user_id == current_user.id)

    # 2 可选：按名称模糊搜索
    if keyword:
        query = query.filter(Knowledge.name.like(f"%{keyword}%"))

    # 3 分页 + 按创建时间倒序（走 idx_knowledge_bases_created_at）
    skip = (page - 1) * limit
    return query.order_by(Knowledge.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{knowledge_id}")
def read_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查看某个知识库详情。"""
    return get_own_knowledge(knowledge_id, current_user, db)


@router.post("/{knowledge_id}/update")
def update_knowledge(
    knowledge_id: int,
    knowledge_in: KnowledgeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改知识库的名称/描述/图标。

    document_num、str_num、app_num 是统计字段，由系统维护，不开放修改。
    """
    knowledge = get_own_knowledge(knowledge_id, current_user, db)

    # exclude_unset=True：只取「请求里真正出现过的字段」，
    # 没传的字段保持原值；想清空图标就显式传 "icon_url": null
    for field, value in knowledge_in.model_dump(exclude_unset=True).items():
        setattr(knowledge, field, value)

    db.commit()
    db.refresh(knowledge)
    return knowledge


@router.post("/{knowledge_id}/delete")
def delete_knowledge(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除知识库。"""
    knowledge = get_own_knowledge(knowledge_id, current_user, db)

    # 外键是 ON DELETE RESTRICT：下面还挂着文档/应用时删不掉，给个能看懂的提示
    try:
        db.delete(knowledge)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="该知识库下还有文档或应用关联，请先清理后再删除",
        )

    return {"message": "删除成功"}
