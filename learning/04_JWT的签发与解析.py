"""
JWT 的签发（俗称加密）与解析（俗称解密）—— 最小可跑示例

运行：python 04_JWT的签发与解析.py
依赖：PyJWT（AI_study 环境已装 2.15.1）

一句话理解 JWT
    token = base64(头部) . base64(载荷) . 签名
    前两段只是"明文编码"，谁都能拆开看；第三段是对前两段的签名，只保证"没被改过"。
    所以 JWT 本质是【防篡改】，不是【保密】—— 载荷里绝不能放密码。
"""

from datetime import datetime, timedelta, timezone

import jwt
# 注意：InvalidSubjectError 只在 jwt.exceptions 里，jwt 顶层没导出（PyJWT 2.15 实测）
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidSignatureError,
    InvalidSubjectError,
)

# ============================================================
# 0. 密钥：签发和解签用的是同一把钥匙（对称算法 HS256）
#    学习阶段写死在代码里；生产环境要放 .env，绝不能提交到仓库
# ============================================================
SECRET_KEY = "demo-secret-key-for-learning-only-32bytes!"  # HMAC 密钥建议 >= 32 字节
ALGORITHM = "HS256"


# ============================================================
# 1. 签发（"加密"）：把数据打包 + 签名，生成 token 字符串
# ============================================================
def create_token(user_id: int, expire_minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),                                # 用户ID。注意：sub 必须是字符串
        "iat": now,                                         # 签发时间
        "exp": now + timedelta(minutes=expire_minutes),     # 过期时间
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ============================================================
# 2. 解析（"解密"）：验签 + 检查过期，再取回数据
# ============================================================
def parse_token(token: str):
    """解析成功返回 (user_id, payload)；失败返回 (None, 失败原因)"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"]), payload
    except ExpiredSignatureError:
        return None, "token 已过期"
    except InvalidSignatureError:
        return None, "签名不对（被篡改，或用错了密钥）"
    except InvalidSubjectError:
        return None, "sub 不是字符串（新版 PyJWT 会拒绝）"
    except jwt.PyJWTError as e:
        return None, f"token 格式无效：{e}"


# ============================================================
# 3. 拆开看：证明"前两段根本没加密"
# ============================================================
def peek(token: str):
    """不解签、不验签，直接把 token 里的内容读出来 —— 任何人都能做到"""
    import base64, json

    def _decode(seg: str):
        seg += "=" * (-len(seg) % 4)                        # 补回 base64 的等号
        return json.loads(base64.urlsafe_b64decode(seg))

    header_seg, payload_seg, _ = token.split(".")
    return _decode(header_seg), _decode(payload_seg)


def tamper_signature(token: str) -> str:
    """只改签名段中间的一个字符（末尾字符有 base64 对齐限制，不能乱改）"""
    head, payload_seg, sig = token.split(".")
    i = len(sig) // 2
    sig = sig[:i] + ("A" if sig[i] != "A" else "B") + sig[i + 1:]
    return f"{head}.{payload_seg}.{sig}"


if __name__ == "__main__":
    line = "-" * 68

    # ---------------- 签发 ----------------
    print("【1】签发 token（把 user_id=7 打包进去）")
    token = create_token(7)
    print("token =", token)
    print("长度  =", len(token), "字符")

    # ---------------- 解析 ----------------
    print(f"\n{line}\n【2】解析 token，取回原始数据")
    user_id, payload = parse_token(token)
    print("解析出的 user_id =", user_id)
    print("完整载荷         =", payload)

    # ---------------- 拆开看 ----------------
    print(f"\n{line}\n【3】不验签也能看到的明文（所以 JWT 不是加密！）")
    head, body = peek(token)
    print("① 头部 (header) :", head)
    print("② 载荷 (payload):", body)
    print("③ 签名 (signature): 只有这一段读不懂，它由密钥和①②共同算出")
    # 把时间戳翻译成人看得懂的
    fmt = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n   iat = {body['iat']} -> {fmt(body['iat'])}  （签发时间）")
    print(f"   exp = {body['exp']} -> {fmt(body['exp'])}  （过期时间）")

    # ---------------- 五种失败情况 ----------------
    print(f"\n{line}\n【4】哪些情况会解析失败")
    cases = [
        ("篡改签名段的一个字符", tamper_signature(token)),
        ("用另一把密钥签发",     jwt.encode({"sub": "7"}, "完全不同的密钥xxxxxx" * 2, algorithm=ALGORITHM)),
        ("已过期的 token",       create_token(7, expire_minutes=-1)),
        ("随手编的乱串",         "abc.def.ghi"),
        ("sub 传了 int 而不是字符串", jwt.encode({"sub": 7}, SECRET_KEY, algorithm=ALGORITHM)),
    ]
    for name, t in cases:
        uid, why = parse_token(t)
        print(f"  {name:28s} -> user_id={uid}   原因：{why}")

    # ---------------- 收尾 ----------------
    print(f"\n{line}\n【记住三件事】")
    print("1. 签发 jwt.encode(payload, 密钥, algorithm=算法)；解析 jwt.decode(token, 密钥, algorithms=[算法])")
    print("2. 载荷是明文，只放不敏感的东西（用户ID、过期时间），别放密码、手机号")
    print("3. 密钥泄露 = 谁都能伪造 token；必须放 .env，且不要提交到代码仓库")
