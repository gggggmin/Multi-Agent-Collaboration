"""向量检索器 — 基于 ChromaDB 的语义检索"""
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError as ChromaNotFoundError
from typing import List, Dict, Optional
from .document_parser import Chunk
from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME, RETRIEVAL_TOP_K


class EmbeddingEngine:
    """嵌入引擎 — 优先使用 sentence-transformers，否则用 TF-IDF 降级"""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._encoder = None
        self._use_tfidf = False
        self._vectorizer = None
        self._tfidf_fitted = False

    def _init_encoder(self):
        if self._encoder is not None or self._use_tfidf:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.model_name)
            print(f"[Embedding] 已加载语义模型: {self.model_name}")
        except Exception as e:
            print(f"[Embedding] 语义模型加载失败 ({e})，使用 TF-IDF 降级方案")
            self._use_tfidf = True
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vectorizer = TfidfVectorizer(max_features=512)

    def encode(self, texts: list, **kwargs) -> list:
        self._init_encoder()
        if self._use_tfidf:
            return self._encode_tfidf(texts)
        import numpy as np
        result = self._encoder.encode(texts, show_progress_bar=False)
        if isinstance(result, np.ndarray):
            return result.tolist()
        return list(result)

    def _encode_tfidf(self, texts: list) -> list:
        if not self._vectorizer:
            return [[0.0]] * len(texts)
        try:
            if not self._tfidf_fitted:
                matrix = self._vectorizer.fit_transform(texts)
                self._tfidf_fitted = True
            else:
                matrix = self._vectorizer.transform(texts)
        except ValueError:
            feature_count = len(getattr(self._vectorizer, "vocabulary_", {})) or 1
            return [[0.0] * feature_count for _ in texts]
        return matrix.toarray().tolist()


class Retriever:
    def __init__(self, collection_name: str = CHROMA_COLLECTION_NAME):
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self.encoder = EmbeddingEngine()
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            try:
                self._collection = self.client.get_collection(self.collection_name)
            except ValueError:
                self._collection = self.client.create_collection(self.collection_name)
        return self._collection

    def build_index(self, chunks: List[Chunk]) -> None:
        """将切片写入向量数据库"""
        # 清空重建
        try:
            self.client.delete_collection(self.collection_name)
        except (ValueError, ChromaNotFoundError):
            pass
        self._collection = self.client.create_collection(self.collection_name)

        texts = [c.content for c in chunks]
        ids = [f"{c.module}_{i}" for i, c in enumerate(chunks)]
        metadatas = [c.to_dict() for c in chunks]

        embeddings = self.encoder.encode(texts)

        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )
        print(f"[RAG] 索引构建完成: {len(chunks)} 个切片")

    def retrieve(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> List[Dict]:
        """语义检索"""
        query_embedding = self.encoder.encode([query])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        retrieved = []
        for i in range(len(results["ids"][0])):
            retrieved.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })

        return retrieved

    def retrieve_by_module(self, module: str, top_k: int = 5) -> List[Dict]:
        """按模块名"""
        results = self.collection.get(
            where={"module": module},
        )
        items = []
        for i in range(len(results["ids"])):
            items.append({
                "id": results["ids"][i],
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            })
        # limit
        return items[:top_k]
