import os
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
# 1. 加载文档
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent
documents = SimpleDirectoryReader(input_files=[ROOT_DIR / "data" / "documents" / "测试文档.md"]).load_data()
# 2. 切分
nodes = SentenceSplitter(
    chunk_size=512,
    chunk_overlap=50,
).get_nodes_from_documents(documents)
# 3. 向量化
api_key = os.getenv("ALIYUN_API_KEY")
Settings.embed_model = DashScopeEmbedding(
    model_name="text-embedding-v3",
    api_key=api_key,
    embed_batch_size=10,  # text-embedding-v3 单批最多 10
)
# 4. 存储
chroma_client = chromadb.PersistentClient(path=ROOT_DIR / "data" / "chroma_db")
chroma_collection = chroma_client.get_or_create_collection(name="agentflow")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)


index = VectorStoreIndex(nodes, storage_context=storage_context)

