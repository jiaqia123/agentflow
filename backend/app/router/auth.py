from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.mysql import get_db
from app.models.auth import User
from app.schemas.auth import UserLogin, UserOut, UserRegister
from app.utils.security import hash_password, verify_password
import jwt

JWT_SECRET_KEY = "oia1SGV6K7YaAHuhl9F8oqs6Y0iGYUI0I3IXi45Ix4f7fmwhZzcygdVVWHD0qqfb"
JWT_ALGORITHM = "HS256"

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def read_login(user_in: UserLogin, db: Session = Depends(get_db)):
    # return "hello login"
    # 获取过滤参数  用户名、密码
    username = user_in.username
    password = user_in.password

    # 操作数据库
    # 1 按用户名查是否已存在  不存在报错、存在继续
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        # 与「密码错误」返回一致，避免账号枚举
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 2 密码明文与数据库中密码哈希对比，正确则返回用户信息，错误则报错
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 3 判断用户是否冻结   冻结则报错、正常则继续
    if user.is_active != 1:
        raise HTTPException(status_code=403, detail="账号已被冻结，请联系管理员")

    # 返回数据
    return {
        "token": jwt.encode({"user_id": str(user.id)}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM),
        "username": user.username,
        "email": user.email,
        'avatar': user.avatar,
        'is_active': user.is_active,
        'created_at': user.created_at
    }


@router.post("/register", status_code=201)
def read_register(user_in: UserRegister, db: Session = Depends(get_db)):
    # return "hello register"
    # 获取过滤参数 用户名、密码、邮箱（可选）
    username = user_in.username
    password = user_in.password
    email = user_in.email  # 未传或为空串时为 None

    # 操作数据库
    # 1 按用户名查是否已存在
    exists = db.query(User.id).filter(User.username == username).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 2 若传了非空邮箱，再查是否已存在
    if email:
        email_exists = db.query(User.id).filter(User.email == email).first()
        if email_exists is not None:
            raise HTTPException(status_code=409, detail="邮箱已被注册")

    # 3 明文密码做哈希，写入 hashed_password，禁止存明文
    db_user = User(
        username=username,
        email=email or "",  # 不填邮箱存空串，配合 nullif(email,'') 唯一索引
        hashed_password=hash_password(password),
        # is_active / avatar / created_at / updated_at 交给数据库默认值
    )

    # 4 入库
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 返回数据（UserOut 已排除 hashed_password）
    return {
        "token": jwt.encode({"user_id": str(db_user.id)}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM),
        "username": db_user.username,
        "email": db_user.email,
        'avatar': db_user.avatar,
        'is_active': db_user.is_active,
        'created_at': db_user.created_at
    }
