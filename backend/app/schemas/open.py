"""开放检索接口（/open）的出参模型。

返回结构 = 原问题 + LLM 合成答案 + 召回片段列表。
"""

from typing import Any

from pydantic import BaseModel, Field


class RetrieveNodeOut(BaseModel):
    """一个召回片段。"""

    node_id: str = Field(..., description="节点 ID，入库时写的是 {document_id}#{chunk_index}")
    text: str = Field(..., description="片段正文")
    score: float | None = Field(None, description="相关度分数（重排后为 rerank 分），可能为 None")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="节点元数据，已滤掉引擎内部字段，可用 mysql_document_id / filename_uuid 对回 MySQL",
    )


class RetrieveOut(BaseModel):
    """检索结果。"""

    query: str = Field(..., description="原问题")
    answer: str = Field(..., description="LLM 合成答案")
    nodes: list[RetrieveNodeOut] = Field(default_factory=list, description="最终召回片段（重排 + 压缩后）")
