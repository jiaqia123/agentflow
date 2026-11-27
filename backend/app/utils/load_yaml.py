import yaml
from dataclasses import dataclass
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent.parent


@dataclass
class RetrievalConfig:
    top_k: int
    fusion_mode: str
    num_queries: int    


@dataclass
class BeforeRefineConfig:
    enable_hyde: bool


@dataclass
class AfterRefineConfig:
    enable_rerank: bool
    rerank_top_n: int
    enable_compression: bool


@dataclass
class Settings:
    retrieval: RetrievalConfig
    before_refine: BeforeRefineConfig
    after_refine: AfterRefineConfig

    # cls 是 类方法（@classmethod）的第一个参数，代表当前被调用的类本身，不是某个实例。
    @classmethod
    def from_yaml(cls, path: str = "settings.yaml") -> "Settings":
        with open(ROOT_PATH / "app" / path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            # data = {
            #     "retrieval": {
            #         "top_k": 5,
            #         "fusion_mode": "reciprocal_rerank",
            #         "num_queries": 3
            #     },
            #     "before_refine": { ... },
            #     "after_refine": { ... },
            # }
        return cls(
            # RetrievalConfig(top_k=5, fusion_mode="reciprocal_rerank", num_queries=3)
            retrieval=RetrievalConfig(**data["retrieval"]), # 把这段字典展开成关键字参数
            before_refine=BeforeRefineConfig(**data["before_refine"]),
            after_refine=AfterRefineConfig(**data["after_refine"]),
        )


settings = Settings.from_yaml()
print(settings.retrieval.top_k)          # 5
print(settings.before_refine.enable_hyde)  # False