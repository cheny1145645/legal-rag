"""
法律知识图谱模块

功能：
1. 构建阶段：解析法律条文之间的引用关系，构建有向图
   - 节点：法律条文（以 "文件名::条文编号" 作为唯一 ID）
   - 边：引用关系（"本条参见第XX条"、"依据第XX条"等）
2. 检索阶段：给定已检索到的条文节点，扩展其 1-2 跳邻居节点，
   补充向量检索可能遗漏的相关条文

依赖：仅使用标准库 + langchain.schema.Document，无需额外安装图数据库
内部使用邻接表实现轻量有向图。
"""

import re
import json
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

from langchain.schema import Document

logger = logging.getLogger(__name__)

# ── 引用关系正则 ─────────────────────────────────────────────────────────────
# 匹配"依据第X条"、"参照第X条"、"见第X条"、"第X条规定"、"第X条第X款"等常见引用模式
_REF_PATTERN = re.compile(
    r"(?:依据|参照|根据|依照|见|适用|按照|参见)?\s*"
    r"(第[一二三四五六七八九十百千\d]+条)"
    r"(?:[第一二三四五六七八九十\d款项]*)?",
    re.UNICODE,
)

# 提取条文编号（用于节点 ID）
_ARTICLE_PATTERN = re.compile(r"第[一二三四五六七八九十百千\d]+条")


def _make_node_id(source: str, article_ref: str) -> str:
    """构造节点 ID：'文件名::第X条'"""
    return f"{source}::{article_ref}"


class LegalKnowledgeGraph:
    """
    法律知识图谱

    数据结构：
    - _nodes: {node_id -> Document}  存储节点对应的文档块
    - _out_edges: {node_id -> set(node_id)}  有向出边（A 引用了 B）
    - _in_edges:  {node_id -> set(node_id)}  有向入边（B 被 A 引用）
    - _article_index: {(source, article_ref) -> node_id}  快速查找
    """

    def __init__(self):
        self._nodes: Dict[str, Document] = {}
        self._out_edges: Dict[str, Set[str]] = defaultdict(set)
        self._in_edges: Dict[str, Set[str]] = defaultdict(set)
        # source -> {article_ref -> node_id}
        self._article_index: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._built = False

    # ── 构建图 ────────────────────────────────────────────────────────────────
    def build(self, documents: List[Document]):
        """
        从文档块列表构建知识图谱。
        每个 Document 需包含 metadata['source'] 和 metadata['article_ref']。
        """
        self._nodes.clear()
        self._out_edges.clear()
        self._in_edges.clear()
        self._article_index.clear()

        # Pass 1: 注册所有节点
        for doc in documents:
            source = doc.metadata.get("source", "unknown")
            article_ref = doc.metadata.get("article_ref", "")
            if not article_ref:
                continue
            node_id = _make_node_id(source, article_ref)
            self._nodes[node_id] = doc
            self._article_index[source][article_ref] = node_id

        # Pass 2: 解析引用关系，建立有向边
        edge_count = 0
        for node_id, doc in self._nodes.items():
            source = doc.metadata.get("source", "unknown")
            refs_in_text = _REF_PATTERN.findall(doc.page_content)

            for ref_article in refs_in_text:
                ref_article = ref_article.strip()
                # 跳过自引用
                if ref_article == doc.metadata.get("article_ref", ""):
                    continue
                # 优先在同一文件内查找被引用的节点
                target_id = self._article_index[source].get(ref_article)
                if target_id and target_id != node_id:
                    self._out_edges[node_id].add(target_id)
                    self._in_edges[target_id].add(node_id)
                    edge_count += 1

        self._built = True
        logger.info(
            f"[KG] 知识图谱构建完成: {len(self._nodes)} 节点, {edge_count} 条引用边"
        )

    # ── 增量添加文档（入库时调用） ────────────────────────────────────────────
    def add_documents(self, documents: List[Document]):
        """增量添加文档到图谱（无需全量重建）"""
        new_nodes = []
        for doc in documents:
            source = doc.metadata.get("source", "unknown")
            article_ref = doc.metadata.get("article_ref", "")
            if not article_ref:
                continue
            node_id = _make_node_id(source, article_ref)
            if node_id not in self._nodes:
                self._nodes[node_id] = doc
                self._article_index[source][article_ref] = node_id
                new_nodes.append(node_id)

        # 为新节点解析引用关系
        for node_id in new_nodes:
            doc = self._nodes[node_id]
            source = doc.metadata.get("source", "unknown")
            refs_in_text = _REF_PATTERN.findall(doc.page_content)
            for ref_article in refs_in_text:
                ref_article = ref_article.strip()
                if ref_article == doc.metadata.get("article_ref", ""):
                    continue
                target_id = self._article_index[source].get(ref_article)
                if target_id and target_id != node_id:
                    self._out_edges[node_id].add(target_id)
                    self._in_edges[target_id].add(node_id)

        if new_nodes:
            logger.info(f"[KG] 增量添加 {len(new_nodes)} 个节点")

    # ── 图扩展检索 ────────────────────────────────────────────────────────────
    def expand_neighbors(
        self,
        seed_docs: List[Tuple[Document, float]],
        max_hops: int = 2,
        max_expand: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        从种子节点出发，BFS 扩展邻居节点（双向：出边 + 入边）。

        Args:
            seed_docs: 向量检索已返回的文档列表 [(doc, score), ...]
            max_hops:  最大扩展跳数（默认2跳）
            max_expand: 最多补充几个邻居节点（默认5个）

        Returns:
            补充的邻居节点列表 [(doc, score), ...]，score 随跳数衰减
        """
        if not self._built or not self._nodes:
            return []

        # 种子节点 ID 集合
        seed_ids: Set[str] = set()
        for doc, _ in seed_docs:
            source = doc.metadata.get("source", "unknown")
            article_ref = doc.metadata.get("article_ref", "")
            if article_ref:
                nid = _make_node_id(source, article_ref)
                if nid in self._nodes:
                    seed_ids.add(nid)

        if not seed_ids:
            return []

        # BFS
        visited = set(seed_ids)
        queue = deque([(nid, 0, 1.0) for nid in seed_ids])  # (node_id, hops, score)
        neighbors: List[Tuple[Document, float]] = []

        while queue and len(neighbors) < max_expand:
            node_id, hops, score = queue.popleft()
            if hops >= max_hops:
                continue

            # 双向扩展：出边（本条引用的）+ 入边（引用本条的）
            adjacent = self._out_edges[node_id] | self._in_edges[node_id]
            for neighbor_id in adjacent:
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                neighbor_doc = self._nodes.get(neighbor_id)
                if neighbor_doc:
                    # 跳数越远，分数衰减越大（1跳*0.6，2跳*0.36）
                    decay = 0.6 ** (hops + 1)
                    neighbors.append((neighbor_doc, decay))
                    queue.append((neighbor_id, hops + 1, decay))
                    if len(neighbors) >= max_expand:
                        break

        logger.info(f"[KG] 图扩展: 从 {len(seed_ids)} 个种子节点扩展出 {len(neighbors)} 个邻居")
        return neighbors

    # ── 查询条文节点 ──────────────────────────────────────────────────────────
    def get_node(self, source: str, article_ref: str) -> Optional[Document]:
        nid = self._article_index.get(source, {}).get(article_ref)
        return self._nodes.get(nid) if nid else None

    def get_neighbors_of(self, source: str, article_ref: str) -> List[str]:
        """返回指定节点的所有邻居节点 ID（双向）"""
        nid = _make_node_id(source, article_ref)
        return list(self._out_edges[nid] | self._in_edges[nid])

    def get_nodes(self) -> List[Dict]:
        """
        返回所有节点列表，供前端知识图谱可视化使用。
        格式：[{"id": str, "source": str, "article_ref": str, "label": str}, ...]
        """
        result = []
        for node_id, doc in self._nodes.items():
            result.append({
                "id": node_id,
                "source": doc.metadata.get("source", "unknown"),
                "article_ref": doc.metadata.get("article_ref", ""),
                "label": doc.metadata.get("article_ref", node_id.split("::")[-1]),
            })
        return result

    def get_links(self) -> List[Dict]:
        """
        返回所有有向边列表，供前端知识图谱可视化使用。
        格式：[{"source": str, "target": str}, ...]
        """
        result = []
        for src_id, targets in self._out_edges.items():
            for tgt_id in targets:
                result.append({"source": src_id, "target": tgt_id})
        return result

    # ── 统计 ──────────────────────────────────────────────────────────────────
    def stats(self) -> Dict:
        edge_count = sum(len(v) for v in self._out_edges.values())
        return {
            "node_count": len(self._nodes),
            "edge_count": edge_count,
            "built": self._built,
        }

    # ── 持久化 / 加载 ─────────────────────────────────────────────────────────
    def save(self, path: str):
        """将图结构序列化为 JSON（节点内容不重复存储，只存元数据和边）"""
        data = {
            "nodes": {
                nid: {
                    "source": doc.metadata.get("source", ""),
                    "article_ref": doc.metadata.get("article_ref", ""),
                    "content_preview": doc.page_content[:200],
                }
                for nid, doc in self._nodes.items()
            },
            "out_edges": {k: list(v) for k, v in self._out_edges.items()},
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[KG] 图结构已保存到 {path}")

    def clear(self):
        """清空图谱"""
        self._nodes.clear()
        self._out_edges.clear()
        self._in_edges.clear()
        self._article_index.clear()
        self._built = False
        logger.info("[KG] 知识图谱已清空")

    # ── GLVR: PageRank 计算 ──────────────────────────────────────────────────────────
    def compute_pagerank(self, damping: float = 0.85, max_iter: int = 100, tol: float = 1e-6) -> dict:
        """计算法律条文的 PageRank 权威度分数"""
        if not self._built or not self._nodes:
            # 只在第一次调用时打印，避免每次检索都刷一条 WARNING
            if not getattr(self, "_pagerank_warned", False):
                logger.info("[GLVR] 知识图谱尚未构建，PageRank 不可用（可在「知识库」页面入库后自动构建）")
                self._pagerank_warned = True
            return {}
        
        nodes = list(self._nodes.keys())
        n = len(nodes)
        if n == 0:
            return {}
        
        outdeg = {nid: len(self._out_edges.get(nid, set())) for nid in nodes}
        pr = {nid: 1.0 / n for nid in nodes}
        
        for iteration in range(max_iter):
            new_pr = {}
            diff = 0.0
            
            for node_id in nodes:
                in_nodes = self._in_edges.get(node_id, set())
                back_contrib = 0.0
                for src in in_nodes:
                    if outdeg.get(src, 0) > 0:
                        back_contrib += pr[src] / outdeg[src]
                new_pr[node_id] = (1 - damping) / n + damping * back_contrib
            
            diff = sum(abs(new_pr[nid] - pr[nid]) for nid in nodes)
            pr = new_pr
            
            if diff < tol:
                logger.info(f"[GLVR] PageRank收敛于第{iteration+1}次迭代")
                break
        else:
            logger.warning(f"[GLVR] PageRank达到{max_iter}次迭代")
        
        logger.info(f"[GLVR] 计算完成，分数范围:[{min(pr.values()):.4f},{max(pr.values()):.4f}]")
        return pr

    def get_authority_score(self, source: str, article_ref: str, pagerank_cache: dict = None) -> float:
        """获取指定条文的权威度分数"""
        node_id = _make_node_id(source, article_ref)
        
        if pagerank_cache and node_id in pagerank_cache:
            return pagerank_cache[node_id]
        
        in_count = len(self._in_edges.get(node_id, set()))
        out_count = len(self._out_edges.get(node_id, set()))
        
        if in_count + out_count == 0:
            return 0.5
        
        authority = in_count / (in_count + out_count + 1)
        return 0.5 + 0.5 * authority


# 全局单例
legal_kg = LegalKnowledgeGraph()
