import logging
import os
import random
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.config import settings
from app.core.document_processor import DocumentLoader
from app.core.vector_store import vector_store_manager
from app.core.retriever import hybrid_retriever
from app.core.knowledge_graph import legal_kg
from app.models.schemas import IngestResponse, AuditRequest, AuditResponse, AuditSourceResult

router = APIRouter(prefix="/api/ingest", tags=["文档入库"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=IngestResponse)
async def upload_and_ingest(file: UploadFile = File(...)):
    """上传法律文档并入库（同步更新 BM25 索引和知识图谱）"""
    allowed_types = {".pdf", ".docx", ".doc", ".txt"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_types:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")

    # 保存上传文件
    save_path = Path(settings.legal_docs_path) / file.filename
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    loader = DocumentLoader()
    try:
        chunks = loader.load_file(str(save_path))
        doc_count = vector_store_manager.add_documents(chunks)

        # 重建 BM25 索引
        all_docs = _get_all_docs_from_vectorstore()
        hybrid_retriever.build_bm25_index(all_docs)

        # 增量更新知识图谱
        if settings.enable_knowledge_graph:
            legal_kg.add_documents(chunks)
            logger.info(f"[KG] 增量更新后: {legal_kg.stats()}")

        return IngestResponse(
            success=True,
            message=f"文档 {file.filename} 成功入库，生成 {len(chunks)} 个文本块",
            doc_count=doc_count,
        )
    except Exception as e:
        logger.error(f"文档入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-directory", response_model=IngestResponse)
async def ingest_directory(force: bool = False):
    """
    加载法律文档目录到向量库（全量重建 BM25 索引和知识图谱）

    参数：
    - force: True=强制重新入库，False=已有数据则跳过

    安全策略：
    - 文档逐个加载，单文件失败不影响整体
    - 向量化分批写入（每批 10 条），避免大批量 OOM
    - 已有数据检测：非强制模式下，向量库有数据则直接跳过入库
    - 暂时禁用知识图谱构建（显存紧张，等向量入库稳定后再开启）
    """
    import gc
    docs_path = settings.legal_docs_path
    if not os.path.exists(docs_path):
        raise HTTPException(status_code=404, detail=f"目录不存在: {docs_path}")

    # ── 智能检测：已有数据则跳过（除非强制）──────────────────────────────────
    existing_count = vector_store_manager.get_doc_count()
    if existing_count > 0 and not force:
        logger.info(f"[入库] 向量库已有 {existing_count} 条数据，跳过入库（非强制模式）")
        return IngestResponse(
            success=True,
            message=f"知识库已就绪，共 {existing_count} 个文本块",
            doc_count=existing_count,
        )

    # ── Step 1: 扫描目录，获取文件列表 ────────────────────────────────────────
    supported = {".pdf", ".docx", ".doc", ".txt"}
    from pathlib import Path as _Path
    files = [f for f in _Path(docs_path).rglob("*") if f.suffix.lower() in supported]
    if not files:
        return IngestResponse(success=False, message="目录中未找到可用文档", doc_count=0)

    logger.info(f"[入库] 发现 {len(files)} 个文档，开始逐文件安全入库...")

    total_chunks = 0
    failed_files = []
    FILE_CHUNK_BATCH = 3   # 每积累 3 个文件的 chunk 就写入一次向量库，避免显存累积

    pending_chunks = []
    loader = DocumentLoader()  # 修复：在此处定义 loader

    for idx, file in enumerate(files, 1):
        try:
            chunks = loader.load_file(str(file))
            if not chunks:
                continue
            pending_chunks.extend(chunks)
            total_chunks += len(chunks)

            # 每积累 FILE_CHUNK_BATCH 个文件或到末尾，写入一次
            if idx % FILE_CHUNK_BATCH == 0 or idx == len(files):
                if pending_chunks:
                    logger.info(f"[入库] 进度 {idx}/{len(files)}，当前批次 {len(pending_chunks)} chunks，写入向量库...")
                    try:
                        vector_store_manager.add_documents(pending_chunks)
                    except Exception as ve:
                        logger.error(f"[入库] 向量化批次失败（跳过本批）: {ve}")
                        # 批次失败则清空待写列表，避免累积
                    finally:
                        pending_chunks.clear()
                        gc.collect()  # 主动释放内存

        except Exception as e:
            logger.error(f"[入库] 文件加载失败: {file.name} — {e}")
            failed_files.append(file.name)
            continue

    # ── Step 2: 重建 BM25 索引（从向量库读取全量文档）─────────────────────────
    logger.info("[入库] 重建 BM25 索引...")
    try:
        all_docs = _get_all_docs_from_vectorstore()
        hybrid_retriever.build_bm25_index(all_docs)
        logger.info(f"[入库] BM25 索引重建完成，共 {len(all_docs)} 条")
    except Exception as e:
        logger.warning(f"[入库] BM25 索引重建失败（不影响向量检索）: {e}")

    # ── Step 3: 构建知识图谱 ──────────────────────────────────────────────────
    if settings.enable_knowledge_graph and all_docs:
        logger.info("[入库] 构建知识图谱...")
        try:
            KG_BATCH = 200
            for i in range(0, len(all_docs), KG_BATCH):
                batch = all_docs[i: i + KG_BATCH]
                if i == 0:
                    legal_kg.build(batch)
                else:
                    legal_kg.add_documents(batch)
            logger.info(f"[KG] 全量构建后: {legal_kg.stats()}")
        except Exception as e:
            logger.warning(f"[入库] 知识图谱构建失败（不影响检索）: {e}")

    doc_count = vector_store_manager.get_doc_count()
    fail_msg = f"，{len(failed_files)} 个文件加载失败: {', '.join(failed_files[:5])}" if failed_files else ""
    return IngestResponse(
        success=True,
        message=f"目录加载完成，共入库 {total_chunks} 个文本块{fail_msg}",
        doc_count=doc_count,
    )


@router.post("/force-reload", response_model=IngestResponse)
async def force_reload_directory():
    """
    强制重新加载文档目录（覆盖已有数据）

    用途：当文档更新后需要重新构建知识库时使用
    """
    return await ingest_directory(force=True)


@router.delete("/clear", response_model=IngestResponse)
async def clear_vectorstore():
    """清空向量数据库（同步清空 BM25 索引和知识图谱）"""
    vector_store_manager.clear_collection()
    hybrid_retriever._bm25 = None
    hybrid_retriever._bm25_docs = []

    if settings.enable_knowledge_graph:
        legal_kg.clear()

    return IngestResponse(success=True, message="向量库已清空", doc_count=0)


class DeleteSourceRequest(BaseModel):
    source_name: str


@router.delete("/source", response_model=IngestResponse)
async def delete_source(body: DeleteSourceRequest):
    """
    按来源名删除所有相关 chunk，并同步重建 BM25 索引。
    source_name 为前端展示的来源名（与 /api/stats/sources 返回的 key 一致）。
    """
    source_name = body.source_name.strip()
    if not source_name:
        raise HTTPException(status_code=400, detail="source_name 不能为空")

    deleted = vector_store_manager.delete_by_source(source_name)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"未找到来源 '{source_name}' 的条目")

    # 重建 BM25 索引
    all_docs = _get_all_docs_from_vectorstore()
    hybrid_retriever.build_bm25_index(all_docs)

    doc_count = vector_store_manager.get_doc_count()
    return IngestResponse(
        success=True,
        message=f"已删除来源 '{source_name}' 的 {deleted} 个文本块",
        doc_count=doc_count,
    )


def _get_all_docs_from_vectorstore():
    """从向量库中获取所有文档（用于重建 BM25 索引）"""
    from langchain.schema import Document
    try:
        col = vector_store_manager._get_client().get_or_create_collection(
            vector_store_manager.COLLECTION_NAME
        )
        data = col.get(include=["documents", "metadatas"])
        docs = []
        for content, meta in zip(data["documents"], data["metadatas"]):
            docs.append(Document(page_content=content, metadata=meta or {}))
        return docs
    except Exception:
        return []


# ── 批量审核接口 ──────────────────────────────────────────────────────────────

# 规则引擎：命中即判 fail
_AUDIT_NOISE_KEYWORDS = (
    "病句", "语法", "句式", "汉语", "语言学", "词法",
    "核磁", "MRI", "手术", "病历", "症状", "诊断", "治疗",
    "明星", "八卦", "网红", "颜值", "综艺", "选秀", "娱乐",
    "食谱", "烹饪", "旅游", "美食", "景点",
    "NBA", "球员", "赛季", "冠军赛",
    "购买链接", "立即抢购", "优惠券", "限时优惠",
)

# 命中即判 pass（白名单，优先级低于黑名单）
_AUDIT_LEGAL_KEYWORDS = (
    "法律", "法规", "条款", "合同", "诉讼", "仲裁", "判决", "裁定",
    "司法", "检察", "律师", "辩护", "起诉", "被告", "原告", "庭审",
    "法院", "法典", "刑法", "民法", "行政法", "宪法", "著作权", "专利",
    "商标", "合规", "违法", "犯罪", "惩处", "罚款", "禁止", "条例",
    "办法", "实施细则", "司法解释", "最高人民法院",
    "劳动合同", "劳动法", "工伤", "赔偿", "补偿", "经济补偿", "违约",
    "解除", "终止", "续签", "用人单位", "劳动者",
    "婚姻法", "离婚", "抚养权", "财产分割", "继承",
    "量刑", "逮捕", "拘留", "羁押", "取保候审", "缓刑", "假释",
    "权利义务", "债权", "债务", "担保", "抵押", "质押", "诉讼时效",
    "行政处罚", "行政许可", "行政复议", "国家赔偿",
)


def _audit_source_by_rules(source_name: str, samples: list[str]) -> tuple[str, str]:
    """
    规则引擎审核（替代 LLM，毫秒级）。
    合并 source_name + 样本文本，用关键词黑/白名单判断。
    返回 (verdict, reason)：'pass' | 'fail' | 'uncertain'
    """
    combined = source_name + " " + " ".join(samples)

    # 黑名单优先
    for kw in _AUDIT_NOISE_KEYWORDS:
        if kw in combined:
            return "fail", f"包含非法律内容关键词「{kw}」"

    # 白名单放行
    for kw in _AUDIT_LEGAL_KEYWORDS:
        if kw in combined:
            return "pass", f"包含法律关键词「{kw}」"

    return "uncertain", "未能确认是否为法律内容"


@router.post("/audit", response_model=AuditResponse)
async def audit_knowledge_base(body: AuditRequest):
    """
    批量审核知识库内容质量。
    - web_only=True：只审核联网自动入库的内容（web_auto_ingest=True）
    - web_only=False：审核全部内容（包括手动上传的文档）
    - auto_delete=True：审核后自动删除 FAIL 的来源
    - auto_delete=False：只返回报告，由用户手动决定是否删除
    """
    import re

    # ── Step 1: 拉出全量 metadata ─────────────────────────────────────────────
    try:
        col = vector_store_manager._get_client().get_or_create_collection(
            vector_store_manager.COLLECTION_NAME
        )
        result = col.get(include=["metadatas", "documents"])
        metadatas = result.get("metadatas") or []
        documents = result.get("documents") or []
        ids = result.get("ids") or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取向量库失败: {e}")

    if not ids:
        return AuditResponse(
            total_sources=0, audited=0, passed=0, failed=0, uncertain=0,
            results=[], message="知识库为空，无需审核"
        )

    # ── Step 2: 按来源分组（复用 vector_store 的清洗逻辑）────────────────────
    def clean(text: str) -> str:
        import unicodedata
        text = unicodedata.normalize("NFKC", text or "")
        return re.sub(r'\s+', ' ', text).strip()

    source_groups: dict[str, dict] = {}   # display_name -> {chunks, ids, is_web, raw_sources}
    for doc_id, meta, content in zip(ids, metadatas, documents):
        meta = meta or {}
        raw_src = meta.get("source", "") or ""
        is_web = raw_src.startswith("网络检索") or bool(meta.get("from_web")) or bool(meta.get("web_auto_ingest"))

        if is_web:
            title = re.sub(r'^网络检索\s*[-–]\s*', '', raw_src)
            display = clean(title) or "未知网页"
        else:
            display = clean(raw_src) or "未知来源"

        if body.web_only and not is_web:
            continue   # 只审联网内容时，跳过本地文档

        if display not in source_groups:
            source_groups[display] = {"chunks": [], "ids": [], "is_web": is_web, "raw_sources": set()}
        source_groups[display]["chunks"].append(content or "")
        source_groups[display]["raw_sources"].add(raw_src)  # 保存原始 source 值

    if not source_groups:
        return AuditResponse(
            total_sources=len(ids), audited=0, passed=0, failed=0, uncertain=0,
            results=[],
            message="没有找到需要审核的内容（联网来源为空）" if body.web_only else "知识库无内容"
        )

    # ── Step 3: 逐来源审核 ───────────────────────────────────────────────────
    audit_results: list[AuditSourceResult] = []
    pass_count = fail_count = uncertain_count = 0

    for source_name, group in source_groups.items():
        chunks = group["chunks"]
        raw_sources_list = list(group["raw_sources"])
        # 随机抽样
        samples = random.sample(chunks, min(body.sample_size, len(chunks)))

        verdict, reason = _audit_source_by_rules(source_name, samples)

        if verdict == "pass":
            pass_count += 1
        elif verdict == "fail":
            fail_count += 1
        else:
            uncertain_count += 1

        audit_results.append(AuditSourceResult(
            source_name=source_name,
            chunk_count=len(chunks),
            verdict=verdict,
            reason=reason,
            samples=[s[:200] for s in samples],
            raw_sources=raw_sources_list,
        ))
        logger.info(f"[审核] {source_name} → {verdict}: {reason}")

    # ── Step 4: auto_delete ──────────────────────────────────────────────────
    deleted_sources: list[str] = []
    if body.auto_delete:
        for r in audit_results:
            if r.verdict == "fail":
                # 优先用原始 source 精确删除，避免 display 名称不匹配
                deleted_any = False
                for raw_src in r.raw_sources:
                    try:
                        cnt = vector_store_manager.delete_by_raw_source(raw_src)
                        if cnt > 0:
                            deleted_any = True
                            logger.info(f"[审核自动删除] raw_src='{raw_src}'，共 {cnt} 条")
                    except AttributeError:
                        # 兼容旧版，回退到 display name 删除
                        cnt = vector_store_manager.delete_by_source(r.source_name)
                        if cnt > 0:
                            deleted_any = True
                if deleted_any:
                    deleted_sources.append(r.source_name)

        if deleted_sources:
            all_docs = _get_all_docs_from_vectorstore()
            hybrid_retriever.build_bm25_index(all_docs)

    total_audited = len(audit_results)
    summary = (
        f"审核完成：{total_audited} 个来源，"
        f"通过 {pass_count} · 不通过 {fail_count} · 不确定 {uncertain_count}"
    )
    if deleted_sources:
        summary += f"，已自动删除 {len(deleted_sources)} 个来源"

    return AuditResponse(
        total_sources=len(source_groups),
        audited=total_audited,
        passed=pass_count,
        failed=fail_count,
        uncertain=uncertain_count,
        results=audit_results,
        deleted_sources=deleted_sources,
        message=summary,
    )
