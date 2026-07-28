"""语义切片器 — 将需求文档按功能语义进行切片（对比：固定长度切片）"""
from typing import List, Dict
from .document_parser import DocumentParser, Chunk


class SemanticChunker:
    """语义切片器，包装 DocumentParser 输出并提供切片统计"""

    def __init__(self, parser: DocumentParser):
        self.parser = parser

    def create_chunks(self, directory: str) -> List[Chunk]:
        return self.parser.parse_all(directory)

    def chunk_stats(self, chunks: List[Chunk]) -> Dict:
        """统计切片信息"""
        types = {}
        modules = {}
        for c in chunks:
            types[c.chunk_type] = types.get(c.chunk_type, 0) + 1
            modules[c.module] = modules.get(c.module, 0) + 1

        avg_len = sum(len(c.content) for c in chunks) / max(len(chunks), 1)

        return {
            "total_chunks": len(chunks),
            "by_type": types,
            "by_module": modules,
            "avg_chunk_length": round(avg_len, 1),
        }

    @staticmethod
    def fixed_length_chunks(text: str, chunk_size: int = 200) -> List[str]:
        """固定长度切片（用于消融实验对比）"""
        words = list(text)
        return [''.join(words[i:i + chunk_size])
                for i in range(0, len(words), chunk_size)]
