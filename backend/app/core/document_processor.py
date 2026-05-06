import os
import re
import logging
from pathlib import Path
from typing import List, Optional

from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)


class LegalTextSplitter:
    """
    法律文本专项分割器
    
    创新点：针对法律条文结构（章、节、条、款、项）进行智能切割，
    保留条文编号和层级关系，避免普通按字符切割破坏法条完整性。
    """

    # 法律条文分隔符优先级（从高到低）
    LEGAL_SEPARATORS = [
        r"\n第[一二三四五六七八九十百千]+章",   # 章
        r"\n第[一二三四五六七八九十百千]+节",   # 节
        r"\n第[一二三四五六七八九十百千\d]+条",  # 条
        r"\n\d+\.",                              # 数字列表
        r"\n[（(][一二三四五六七八九十]+[）)]",  # 括号编号
        "\n\n",
        "\n",
        "。",
        "；",
    ]

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            separators=self.LEGAL_SEPARATORS,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            is_separator_regex=True,
            keep_separator=True,
        )

    def split_documents(self, documents: List[Document]) -> List[Document]:
        chunks = self._splitter.split_documents(documents)
        # 为每个chunk注入法条元数据
        enriched = []
        for chunk in chunks:
            chunk.metadata["article_ref"] = self._extract_article_ref(chunk.page_content)
            enriched.append(chunk)
        logger.info(f"文档切割完成，共 {len(chunks)} 个chunk")
        return enriched

    def _extract_article_ref(self, text: str) -> str:
        """提取chunk中第一个出现的法条编号"""
        match = re.search(r"第[一二三四五六七八九十百千\d]+条", text)
        return match.group(0) if match else ""


class DocumentLoader:
    """法律文档加载器，支持PDF、Word、TXT格式"""

    def __init__(self):
        self.splitter = LegalTextSplitter()

    def load_file(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        suffix = path.suffix.lower()

        logger.info(f"加载文档: {path.name}")

        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suffix in (".docx", ".doc"):
            loader = Docx2txtLoader(str(path))
        elif suffix == ".txt":
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

        docs = loader.load()
        # 注入来源元数据
        for doc in docs:
            doc.metadata["source"] = path.name
            doc.metadata["file_type"] = suffix

        chunks = self.splitter.split_documents(docs)
        return chunks

    def load_directory(self, dir_path: str) -> List[Document]:
        """加载目录下所有法律文档"""
        dir_path = Path(dir_path)
        all_chunks = []
        supported = {".pdf", ".docx", ".doc", ".txt"}

        files = [f for f in dir_path.rglob("*") if f.suffix.lower() in supported]
        if not files:
            logger.warning(f"目录 {dir_path} 下未找到支持的文档")
            return []

        for file in files:
            try:
                chunks = self.load_file(str(file))
                all_chunks.extend(chunks)
                logger.info(f"  {file.name} -> {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"加载 {file.name} 失败: {e}")

        logger.info(f"共加载 {len(all_chunks)} 个文本块")
        return all_chunks
