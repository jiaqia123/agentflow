"""公共上传接口（本地磁盘存储，不使用对象存储）。

目录规则：backend/data/uploads/<年>/<月>/<日>/<uuid>/<原始文件名>

设计要点：
1. 文件名原样保留，一个字都不改（不追加时间戳、不加随机前缀）；
2. 用「年/月/日/uuid」分层，保证同一天同名文件不会互相覆盖；
3. ``save_upload_file`` 是公共函数，别的 router 可以直接 import 复用；
4. 只做「存盘 + 返回路径/URL」，不碰数据库 —— 建记录是业务层的事。
"""

from datetime import datetime
from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/upload", tags=["upload"])

# ---------------------------------------------------------------- 路径常量
# __file__ = backend/app/router/upload.py
# parents[0]=router  parents[1]=app  parents[2]=backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"           # backend/data
UPLOAD_ROOT = DATA_DIR / "uploads"        # backend/data/uploads

# 静态资源前缀：把 DATA_DIR 挂到 main.py 的 "/static" 上，
# 上传后的图片就能通过 /static/uploads/2026/10/06/<uuid>/xxx.png 直接访问
STATIC_PREFIX = "/static"

# 允许的图片后缀（统一转小写比较）
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

CHUNK_SIZE = 1024 * 1024          # 边读边写，每块 1MB，避免大文件一次性进内存
MAX_SIZE = 10 * 1024 * 1024       # 单文件上限 10MB


# ---------------------------------------------------------------- 公共函数
def safe_filename(raw_name: str | None) -> str:
    """从客户端传来的文件名里只取最后一段，挡掉 ``../../etc/passwd`` 这类路径穿越。

    ``UploadFile.filename`` 是**客户端自己填的**、完全不可信：
    直接拼进 ``Path(...) / filename`` 的话，一个 ``../../`` 就能写到项目外去。
    """
    # 先统一分隔符（Windows 客户端会传反斜杠），再取最后一段
    name = (raw_name or "").replace("\\", "/").split("/")[-1]
    # 去掉首尾空白和不合法字符（NUL 会让 open() 直接报错）
    name = name.strip().replace("\x00", "")
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效")
    return name


def check_image(image: UploadFile, filename: str) -> str:
    """校验是不是图片，返回小写后缀。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式「{suffix or '无后缀'}」，"
                   f"仅支持：{', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Content-Type 不是图片类型：{content_type or '空'}",
        )
    return suffix


def build_dir(root: Path = UPLOAD_ROOT) -> Path:
    """生成「年/月/日/uuid」目录并创建，返回目录 Path。"""
    now = datetime.now()
    folder = root / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_upload_file(
    image: UploadFile,
    root: Path = UPLOAD_ROOT,
    max_size: int = MAX_SIZE,
) -> dict:
    """把上传的图片存到本地磁盘，返回描述信息。

    :param image: FastAPI 的 UploadFile
    :param root: 上传根目录，默认 backend/data/uploads
    :param max_size: 单文件大小上限（字节）
    :return: {filename, size, path, url, dir}
    """
    filename = safe_filename(image.filename)
    check_image(image, filename)

    folder = build_dir(root)
    dest = folder / filename

    written = 0
    try:
        # 某些客户端/中间件会把指针留在末尾，先归零再读
        image.file.seek(0)
        with dest.open("wb") as f:
            while True:
                chunk = image.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件过大，上限 {max_size // 1024 // 1024}MB",
                    )
                f.write(chunk)
    except HTTPException:
        shutil.rmtree(folder, ignore_errors=True)   # 别留空目录
        raise
    except Exception as exc:                        # noqa: BLE001
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"保存失败：{exc}") from exc

    if written == 0:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(status_code=400, detail="上传内容为空")

    # 相对 data 目录的路径，例如 uploads/2026/10/06/<uuid>/我的图.png
    rel = dest.relative_to(DATA_DIR)
    return {
        "filename": filename,                                    # 原始文件名，未改名
        "size": written,                                         # 字节数
        "path": str(dest),                                       # 磁盘绝对路径
        "url": f"{STATIC_PREFIX}/{rel.as_posix()}",              # 浏览器可访问的地址
        "dir": str(folder),
    }


# ---------------------------------------------------------------- 接口
@router.post("/image", summary="上传图片")
def create_image(image: UploadFile = File(...)):
    """公共图片上传接口。

    ``multipart/form-data`` 提交，字段名固定为 ``image``：

    .. code-block:: bash

        curl -X POST http://127.0.0.1:8000/upload/image -F "image=@/path/a.png"
    """
    return save_upload_file(image)
