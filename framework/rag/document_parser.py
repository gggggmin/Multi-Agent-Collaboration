"""需求文档解析器 — 解析 Markdown 格式的需求文档"""
import re
from pathlib import Path
from typing import List, Dict


class Chunk:
    """语义切片：一个完整的业务功能描述"""
    def __init__(self, module: str, func_name: str, content: str,
                 chunk_type: str, file_source: str):
        self.module = module          # 所属模块，如 login/search/cart/checkout
        self.func_name = func_name    # 功能名称
        self.content = content        # 完整文本内容
        self.chunk_type = chunk_type  # 正向/逆向/边界值
        self.file_source = file_source  # 来源文件

    def to_dict(self) -> Dict:
        return {
            "module": self.module,
            "func_name": self.func_name,
            "content": self.content,
            "chunk_type": self.chunk_type,
            "file_source": self.file_source,
        }


class DocumentParser:
    """解析需求文档，提取语义切片"""

    def parse_markdown(self, file_path: str) -> List[Chunk]:
        """解析单篇 Markdown 需求文档，按功能模块切片"""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        module = self._detect_module(path.stem)
        chunks: List[Chunk] = []

        # 按 "## 功能" 分割
        sections = re.split(r'(?=^##\s+功能\d+[:：])', text, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section or section.startswith("# "):
                continue

            # 提取功能名称
            func_match = re.match(r'^##\s+功能\d+[:：]\s*(.*)', section)
            func_name = func_match.group(1).strip() if func_match else "未知功能"

            # 提取类型标签
            type_match = re.search(r'\*\*类型\*\*[:：]\s*(.*)', section)
            chunk_type = type_match.group(1).strip() if type_match else "未分类"

            chunks.append(Chunk(
                module=module,
                func_name=func_name,
                content=section.strip(),
                chunk_type=chunk_type,
                file_source=path.name,
            ))

        return chunks

    def parse_all(self, directory: str) -> List[Chunk]:
        """解析目录下所有 .md 需求文档"""
        all_chunks = []
        for md_file in sorted(Path(directory).glob("*.md")):
            all_chunks.extend(self.parse_markdown(str(md_file)))
        return all_chunks

    def _detect_module(self, stem: str) -> str:
        mapping = {
            "login": "login",
            "search": "search",
            "cart": "cart",
            "checkout": "checkout",
        }
        for key, value in mapping.items():
            if key in stem.lower():
                return value
        return stem
