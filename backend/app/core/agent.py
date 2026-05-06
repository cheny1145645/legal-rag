"""
agent.py
───────
Agent 自主决策模块

功能：
  - 工具注册与调用
  - Agent 循环（观察-思考-行动）
  - SSE 流式输出

工具集：
  - read_file: 读取文件内容
  - list_dir: 列出目录文件
  - search_kb: 查询知识库
  - web_search: 网络搜索
  - write_file: 生成并保存文件
"""

import json
import os
import logging
from dataclasses import dataclass, field
from typing import Generator, Optional, Callable, Any
from pathlib import Path
import re
import shutil

from app.core.llm_client import llm_client, LLMConfig
from app.config import settings
from app.core.retriever import hybrid_retriever

logger = logging.getLogger(__name__)


# ── 工具定义 ──────────────────────────────────────────────────────────────
@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable  # 同步处理函数


@dataclass
class ToolCall:
    """工具调用记录"""
    name: str
    arguments: dict
    result: Any = None
    error: Optional[str] = None


# ── 工具实现 ──────────────────────────────────────────────────────────────
def _read_file_handler(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    if not path:
        return "错误：文件路径不能为空"
    
    # 安全检查：黑名单模式，阻止读取系统敏感目录（允许读取所有普通用户路径）
    abs_path = os.path.abspath(path)
    
    # 禁止读取的系统目录
    blocked_dirs = [
        "C:\\Windows",
        "C:\\Windows\\System32",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        os.path.expandvars("%APPDATA%"),
        os.path.expandvars("%LOCALAPPDATA%"),
        os.path.expandvars("%WINDIR%"),
    ]
    
    for blocked in blocked_dirs:
        if blocked and abs_path.lower().startswith(blocked.lower()):
            return f"错误：禁止读取系统保护目录: {blocked}"
    
    if not os.path.exists(abs_path):
        return f"错误：文件不存在: {path}"
    
    # 读取文件
    ext = os.path.splitext(abs_path)[1].lower()
    
    # 限制读取的文件大小（5MB）
    if os.path.getsize(abs_path) > 5 * 1024 * 1024:
        return f"错误：文件过大，超过5MB: {path}"
    
    # 支持的文件类型
    text_extensions = {".txt", ".md", ".json", ".xml", ".csv", ".log", ".py", ".js", ".html", ".css"}
    doc_extensions = {".doc", ".docx", ".pdf"}
    
    if ext in text_extensions:
        try:
            with open(abs_path, "r", encoding=encoding) as f:
                content = f.read()
            return f"文件内容 ({path}):\n```\n{content[:10000]}\n```"
        except UnicodeDecodeError:
            # 尝试其他编码
            for enc in ["gbk", "gb2312", "latin1"]:
                try:
                    with open(abs_path, "r", encoding=enc) as f:
                        content = f.read()
                    return f"文件内容 ({path}):\n```\n{content[:10000]}\n```"
                except:
                    continue
            return f"错误：无法读取文件编码: {path}"
    elif ext == ".docx":
        try:
            import docx as _docx
            doc = _docx.Document(abs_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n".join(paragraphs)
            return f"文件内容 ({path})（Word文档）:\n```\n{content[:10000]}\n```"
        except ImportError:
            return "错误：需要安装 python-docx 才能读取 Word 文档（pip install python-docx）"
        except Exception as e:
            return f"错误：读取 Word 文档失败: {e}"
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(abs_path)
            pages_text = []
            for i, page in enumerate(reader.pages[:20]):  # 最多读20页
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(f"[第{i+1}页]\n{text.strip()}")
            if pages_text:
                content = "\n\n".join(pages_text)
                return f"文件内容 ({path})（PDF文档，共{len(reader.pages)}页）:\n```\n{content[:10000]}\n```"
            else:
                return f"PDF文件 {path} 未提取到文本内容（可能是图片扫描版）"
        except ImportError:
            return "错误：需要安装 pypdf 才能读取 PDF 文档（pip install pypdf）"
        except Exception as e:
            return f"错误：读取 PDF 文档失败: {e}"
    elif ext == ".doc":
        return f"提示：旧版 .doc 格式暂不支持自动读取，请将文件另存为 .docx 后再试"
    else:
        return f"不支持的文件类型: {ext}"


def _list_dir_handler(path: str, pattern: str = "*") -> str:
    """列出目录文件"""
    if not path:
        path = "."
    
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        return f"错误：目录不存在: {path}"
    
    if not os.path.isdir(abs_path):
        return f"错误：路径不是目录: {path}"
    
    try:
        files = []
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            is_dir = os.path.isdir(item_path)
            size = "-" if is_dir else os.path.getsize(item_path)
            files.append({
                "name": item,
                "type": "dir" if is_dir else "file",
                "size": size
            })
        
        if not files:
            return f"目录为空: {path}"
        
        # 按类型排序（目录在前）
        files.sort(key=lambda x: (x["type"] != "dir", x["name"]))
        
        result = f"目录内容 ({path}):\n"
        for f in files:
            if f["type"] == "dir":
                result += f"  📁 {f['name']}/\n"
            else:
                size_str = f"{f['size']/1024:.1f}KB" if f["size"] != "-" else "-"
                result += f"  📄 {f['name']} ({size_str})\n"
        
        return result
    except PermissionError:
        return f"错误：无权限访问目录: {path}"
    except Exception as e:
        return f"错误：{str(e)}"


def _write_file_handler(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入文件内容"""
    if not path:
        return "错误：文件路径不能为空"
    
    abs_path = os.path.abspath(path)
    
    # 安全检查：禁止写系统关键目录
    forbidden_prefixes = [
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), ""),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32"),
        "/etc", "/sys", "/proc", "/bin", "/usr/bin",
    ]
    for fp in forbidden_prefixes:
        if abs_path.startswith(fp):
            return f"错误：禁止写入系统目录: {fp}"
    
    # 检查目录是否存在
    parent_dir = os.path.dirname(abs_path)
    if not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except Exception as e:
            return f"错误：无法创建目录: {e}"
    
    # 写入文件
    try:
        with open(abs_path, "w", encoding=encoding) as f:
            f.write(content)
        return f"文件已保存: {abs_path}"
    except Exception as e:
        return f"错误：写入失败: {e}"


def _analyze_dir_handler(path: str, file_types: str = ".txt,.md,.doc,.docx,.pdf", max_files: int = 20) -> str:
    """批量分析目录中的所有文档，生成汇总报告"""
    if not path:
        return "错误：目录路径不能为空"
    
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return f"错误：目录不存在: {path}"
    if not os.path.isdir(abs_path):
        return f"错误：路径不是目录: {path}"
    
    # 解析允许的文件类型
    allowed_exts = {e.strip().lower() for e in file_types.split(",") if e.strip()}
    
    # 递归收集文件
    found_files = []
    try:
        for root, dirs, files in os.walk(abs_path):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in allowed_exts:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, abs_path)
                    size = os.path.getsize(full)
                    found_files.append({"path": full, "rel": rel, "size": size, "ext": ext})
    except Exception as e:
        return f"错误：遍历目录失败: {e}"
    
    if not found_files:
        return f"目录 {path} 中未找到匹配类型 ({file_types}) 的文件"
    
    # 按大小排序，优先处理小文件
    found_files.sort(key=lambda x: x["size"])
    total = len(found_files)
    
    result_lines = [
        f"## 目录批量分析 - {path}",
        f"共找到 {total} 个文件（类型：{file_types}），显示前 {min(total, max_files)} 个：\n",
    ]
    
    # 读取每个文件的摘要
    processed = 0
    for fi in found_files[:max_files]:
        processed += 1
        ext = fi["ext"]
        size_kb = fi["size"] / 1024
        
        result_lines.append(f"### [{processed}/{min(total, max_files)}] {fi['rel']} ({size_kb:.1f}KB)")
        
        if ext in {".txt", ".md", ".csv", ".log", ".py", ".js", ".html"}:
            try:
                # 优先 utf-8，失败时尝试 gbk
                content = None
                for enc in ["utf-8", "gbk", "gb2312"]:
                    try:
                        with open(fi["path"], "r", encoding=enc) as f:
                            content = f.read(3000)  # 前3000字符
                        break
                    except UnicodeDecodeError:
                        continue
                if content:
                    preview = content.replace('\n\n\n', '\n\n')[:800]
                    result_lines.append(f"**预览：**\n```\n{preview}\n```")
                else:
                    result_lines.append("*无法读取（编码问题）*")
            except Exception as e:
                result_lines.append(f"*读取失败: {e}*")
        elif ext in {".doc", ".docx"}:
            try:
                import docx as _docx
                doc = _docx.Document(fi["path"])
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:800]
                result_lines.append(f"**Word文档预览：**\n```\n{text}\n```")
            except ImportError:
                result_lines.append("*需要安装 python-docx 才能读取 Word 文档*")
            except Exception as e:
                result_lines.append(f"*读取失败: {e}*")
        elif ext == ".pdf":
            result_lines.append(f"*PDF文件，大小 {size_kb:.1f}KB（需专用工具解析）*")
        else:
            result_lines.append(f"*文件类型 {ext}*")
        
        result_lines.append("")  # 空行分隔
    
    if total > max_files:
        result_lines.append(f"\n> 注意：目录中还有 {total - max_files} 个文件未展示，可增大 max_files 参数查看更多。")
    
    result_lines.append(f"\n---\n**汇总**：共 {total} 个文件，已展示 {processed} 个")
    
    return "\n".join(result_lines)


def _generate_legal_doc_handler(
    doc_type: str,
    output_path: str,
    content: str,
    title: str = "",
    parties: str = "",
    date: str = "",
    format: str = "docx"
) -> str:
    """生成法律文书（Word/TXT格式）
    
    参数:
        doc_type: 文书类型，如 "合同", "起诉状", "答辩状", "法律意见书", "协议书"
        output_path: 输出文件路径（含文件名，如 /path/to/output.docx）
        content: 文书正文内容（Markdown格式）
        title: 文书标题，不填则自动生成
        parties: 当事人信息（如 "甲方：xxx，乙方：yyy"）
        date: 日期（如 "2025年3月25日"），不填则使用今天
        format: 输出格式，"docx" 或 "txt"
    """
    import datetime
    
    if not content:
        return "错误：文书内容不能为空"
    if not output_path:
        return "错误：输出路径不能为空"
    
    # 自动补全日期
    if not date:
        date = datetime.date.today().strftime("%Y年%m月%d日")
    
    # 自动生成标题
    if not title:
        title = doc_type or "法律文书"
    
    # 确保目录存在
    abs_path = os.path.abspath(output_path)
    parent = os.path.dirname(abs_path)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as e:
            return f"错误：无法创建目录: {e}"
    
    # 强制 txt 格式（避免依赖 python-docx）
    # 如果请求 docx 但库不可用，降级到 txt
    actual_format = format.lower()
    
    if actual_format == "docx":
        try:
            import docx as _docx
            from docx.shared import Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            doc = _docx.Document()
            
            # 页面设置
            section = doc.sections[0]
            section.page_width = Cm(21)
            section.page_height = Cm(29.7)
            section.left_margin = Cm(3.18)
            section.right_margin = Cm(3.18)
            section.top_margin = Cm(2.54)
            section.bottom_margin = Cm(2.54)
            
            # 标题
            title_para = doc.add_paragraph()
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title_para.add_run(title)
            run.bold = True
            run.font.size = Pt(18)
            run.font.name = "黑体"
            
            # 当事人信息
            if parties:
                doc.add_paragraph()
                for line in parties.split("，"):
                    if line.strip():
                        p = doc.add_paragraph(line.strip())
                        p.paragraph_format.left_indent = Cm(0)
                        for run in p.runs:
                            run.font.size = Pt(12)
                            run.font.name = "仿宋"
            
            doc.add_paragraph()
            
            # 正文内容
            for line in content.split("\n"):
                line = line.rstrip()
                if line.startswith("## ") or line.startswith("# "):
                    heading_text = line.lstrip("#").strip()
                    p = doc.add_paragraph()
                    run = p.add_run(heading_text)
                    run.bold = True
                    run.font.size = Pt(14)
                    run.font.name = "黑体"
                elif line.startswith("### "):
                    heading_text = line[4:].strip()
                    p = doc.add_paragraph()
                    run = p.add_run(heading_text)
                    run.bold = True
                    run.font.size = Pt(13)
                    run.font.name = "仿宋"
                elif line.startswith("- ") or line.startswith("* "):
                    p = doc.add_paragraph(style="List Bullet")
                    p.add_run(line[2:]).font.size = Pt(12)
                elif line.startswith("**") and line.endswith("**"):
                    p = doc.add_paragraph()
                    run = p.add_run(line.strip("*"))
                    run.bold = True
                    run.font.size = Pt(12)
                    run.font.name = "仿宋"
                elif line:
                    p = doc.add_paragraph(line)
                    for run in p.runs:
                        run.font.size = Pt(12)
                        run.font.name = "仿宋"
                else:
                    doc.add_paragraph()
            
            # 日期
            doc.add_paragraph()
            date_para = doc.add_paragraph(f"                    {date}")
            for run in date_para.runs:
                run.font.size = Pt(12)
                run.font.name = "仿宋"
            
            # 确保扩展名正确
            if not abs_path.lower().endswith(".docx"):
                abs_path = abs_path + ".docx"
            
            doc.save(abs_path)
            return f"✅ Word文书已生成: {abs_path}（{os.path.getsize(abs_path) // 1024}KB）"
            
        except ImportError:
            # 降级到 txt
            actual_format = "txt"
            if not abs_path.lower().endswith(".txt"):
                abs_path = os.path.splitext(abs_path)[0] + ".txt"
        except Exception as e:
            return f"错误：生成Word文档失败: {e}"
    
    if actual_format == "txt":
        try:
            lines = [
                "=" * 60,
                f"  {title}",
                "=" * 60,
                "",
            ]
            if parties:
                lines.append(parties)
                lines.append("")
            lines.append(content)
            lines.append("")
            lines.append(f"日期：{date}")
            lines.append("=" * 60)
            
            if not abs_path.lower().endswith(".txt"):
                abs_path = abs_path + ".txt"
            
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            return f"✅ 文书已生成（TXT格式）: {abs_path}"
            
        except Exception as e:
            return f"错误：生成文书失败: {e}"
    
    return f"错误：不支持的格式 {format}，请使用 docx 或 txt"


def _search_kb_handler(query: str, top_k: int = 5) -> str:
    """知识库检索处理函数"""
    try:
        from app.core.vector_store import vector_store_manager
        
        # 执行向量检索
        docs = vector_store_manager.similarity_search_with_score(query, k=top_k)
        
        if not docs:
            return "知识库中没有找到相关内容"
        
        results = []
        for doc, score in docs[:top_k]:
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content[:500]  # 截取内容
            results.append(f"【{source}】(相似度: {score:.3f})\n{content}...\n")
        
        return "知识库检索结果:\n\n" + "\n---\n\n".join(results)
    
    except Exception as e:
        return f"知识库检索失败: {e}"


def _web_search_handler(query: str, max_results: int = 3) -> str:
    """网络搜索处理函数"""
    try:
        from app.core.web_searcher import web_searcher
        
        # 执行网络搜索（web_searcher.search 只接受 query，不接受 k 参数）
        docs = web_searcher.search(query)
        
        if not docs:
            return "网络搜索没有找到相关内容"
        
        results = []
        for doc in docs[:max_results]:
            url = doc.metadata.get("url", "")
            content = doc.page_content[:500]
            source = doc.metadata.get("source", "网络来源")
            results.append(f"【{source}】{url}\n{content}...\n")
        
        return "网络搜索结果:\n\n" + "\n---\n\n".join(results)
    
    except Exception as e:
        return f"网络搜索失败: {e}"


# ── 工具注册表 ──────────────────────────────────────────────────────────────
class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        
        # read_file
        self.register(Tool(
            name="read_file",
            description="读取指定文件的内容，用于分析文档、合同、报告等",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "encoding": {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"}
                },
                "required": ["path"]
            },
            handler=_read_file_handler
        ))
        
        # list_dir
        self.register(Tool(
            name="list_dir",
            description="列出指定目录下的所有文件和子目录，用于了解目录结构或批量处理文件",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认为当前目录", "default": "."},
                    "pattern": {"type": "string", "description": "文件过滤模式，如 *.txt", "default": "*"}
                }
            },
            handler=_list_dir_handler
        ))
        
        # write_file
        self.register(Tool(
            name="write_file",
            description="创建或更新文件，写入指定内容。用于生成法律文书、报告、合同草稿等",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                    "encoding": {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"}
                },
                "required": ["path", "content"]
            },
            handler=_write_file_handler
        ))
        
        # search_kb - 知识库检索
        self.register(Tool(
            name="search_kb",
            description="检索法律知识库，查询相关的法律条文、案例和解释",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询内容"},
                    "top_k": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
                },
                "required": ["query"]
            },
            handler=_search_kb_handler
        ))
        
        # web_search - 网络搜索
        self.register(Tool(
            name="web_search",
            description="通过网络搜索获取最新的法律信息、司法解释、案例等",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最大结果数，默认3", "default": 3}
                },
                "required": ["query"]
            },
            handler=_web_search_handler
        ))
        
        # analyze_dir - 目录批量分析
        self.register(Tool(
            name="analyze_dir",
            description="批量扫描目录中的所有文档，逐一读取并输出内容摘要汇总报告。适合分析整个文件夹的合同、法律文书、资料等",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要分析的目录路径"},
                    "file_types": {"type": "string", "description": "文件类型过滤（逗号分隔），默认 .txt,.md,.doc,.docx,.pdf", "default": ".txt,.md,.doc,.docx,.pdf"},
                    "max_files": {"type": "integer", "description": "最多处理的文件数量，默认20", "default": 20}
                },
                "required": ["path"]
            },
            handler=_analyze_dir_handler
        ))
        
        # generate_legal_doc - 法律文书生成
        self.register(Tool(
            name="generate_legal_doc",
            description="生成正式的法律文书，支持合同、起诉状、答辩状、法律意见书、协议书等类型，输出为Word(.docx)或纯文本格式",
            parameters={
                "type": "object",
                "properties": {
                    "doc_type": {"type": "string", "description": "文书类型，如：合同、起诉状、答辩状、法律意见书、协议书、委托书"},
                    "output_path": {"type": "string", "description": "输出文件路径，含文件名（如 D:/output/合同.docx）"},
                    "content": {"type": "string", "description": "文书正文内容，支持Markdown格式"},
                    "title": {"type": "string", "description": "文书标题，不填则用doc_type自动生成", "default": ""},
                    "parties": {"type": "string", "description": "当事人信息（如 甲方：xxx，乙方：yyy）", "default": ""},
                    "date": {"type": "string", "description": "日期，不填则使用今天的日期", "default": ""},
                    "format": {"type": "string", "description": "输出格式：docx（Word文档）或 txt（纯文本），默认docx", "default": "docx"}
                },
                "required": ["doc_type", "output_path", "content"]
            },
            handler=_generate_legal_doc_handler
        ))
    
    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"[Agent] 注册工具: {tool.name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> list[dict]:
        """列出所有工具"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters
            }
            for t in self._tools.values()
        ]
    
    def get_tool_schemas(self) -> list[dict]:
        """获取 OpenAI 格式的工具 schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in self._tools.values()
        ]


# 全局工具注册表
tool_registry = ToolRegistry()


# ── Agent 核心 ──────────────────────────────────────────────────────────────
@dataclass
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 10  # 最大迭代次数
    max_tokens_per_iteration: int = 4096  # 每次迭代的最大 token
    verbose: bool = False  # 是否输出执行过程


class Agent:
    """Agent 自主决策引擎"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.tools = tool_registry
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        tool_schemas = json.dumps(self.tools.list_tools(), ensure_ascii=False, indent=2)
        
        return f"""你是一个智能法律助手，具备自主决策能力。你通过"思考→调用工具→观察结果→再思考"的循环来完成用户的任务。

## 可用工具
{tool_schemas}

## 工具使用规则（严格遵守）

### 调用格式
每次调用工具时，必须严格使用下面的格式，不能省略任何括号或标记：
```
[[TOOL_CALL]]
{{"name": "工具名称", "arguments": {{"参数1": "值1", "参数2": "值2"}}}}
[[/TOOL_CALL]]
```

### 多工具顺序调用
- 一次回复中可以调用多个工具，每个工具占一个独立的 [[TOOL_CALL]] 块
- 例如：先调用 search_kb 检索知识，再调用 generate_legal_doc 生成文书
- **必须等收到工具结果后，再决定下一步**

### 禁止提前放弃
- **严禁**在没有调用任何工具的情况下直接说"我无法完成"或"我没有能力"
- 如果用户要求生成/写入文件，**必须**调用 write_file 或 generate_legal_doc 工具
- 如果需要查询法律知识，**必须**先调用 search_kb 或 web_search 工具
- 工具执行失败时，要分析错误原因并尝试修正参数后重试，或换用其他工具

### 任务完成标准
- 如果任务要求"保存文件"，必须确认工具返回了成功信息（如"文件已保存"）才算完成
- 最终回答时，直接输出结果和说明，**不要包含任何 [[TOOL_CALL]] 标记**

## 典型工作流程

**生成并保存法律文书：**
1. 调用 search_kb 查询相关法律条款（可选）
2. 调用 generate_legal_doc 生成正式 Word 文书并保存到指定路径
3. 向用户确认文件已生成，并说明文件路径

**分析上传文档：**
1. 调用 read_file 读取文件内容（支持 .txt/.md/.docx/.pdf）
2. 分析文档内容，给出法律意见

**查询法律问题：**
1. 调用 search_kb 检索知识库
2. 如知识库结果不足，调用 web_search 补充
3. 综合结果给出专业回答"""
    
    def _parse_tool_calls(self, text: str) -> list[dict]:
        """解析文本中的工具调用"""
        tool_calls = []
        
        # 先提取 [[TOOL_CALL]] ... [[/TOOL_CALL]] 块内的原始文本
        block_pattern = r'\[\[TOOL_CALL\]\](.*?)\[\[/TOOL_CALL\]\]'
        blocks = re.findall(block_pattern, text, re.DOTALL)
        
        for block in blocks:
            block = block.strip()
            # 从块中提取 JSON（找到第一个 { 到最后一个 } 之间的内容）
            start = block.find('{')
            end = block.rfind('}')
            if start == -1 or end == -1:
                continue
            json_str = block[start:end + 1]
            try:
                tool_call = json.loads(json_str)
                if "name" in tool_call and "arguments" in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                logger.warning(f"[Agent] 工具调用 JSON 解析失败: {e}\n原文: {json_str[:200]}")
                continue
        
        return tool_calls
    
    def _execute_tool(self, name: str, arguments: dict) -> tuple[str, Optional[str]]:
        """执行工具调用"""
        tool = self.tools.get(name)
        if not tool:
            return "", f"错误：未知工具 {name}"
        
        try:
            result = tool.handler(**arguments)
            return str(result), None
        except Exception as e:
            logger.error(f"[Agent] 工具执行失败: {name}, {e}")
            return "", f"执行错误: {e}"
    
    def chat(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        llm_config: Optional[LLMConfig] = None,
    ) -> Generator[tuple, None, None]:
        """
        流式 Agent 对话
        
        yield 格式:
        - ("thinking", content) - 思考过程
        - ("tool_call", json) - 工具调用
        - ("tool_result", content) - 工具结果
        - ("text", content) - 最终回答
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        
        iterations = 0
        max_iterations = self.config.max_iterations
        
        while iterations < max_iterations:
            iterations += 1
            
            # 调用 LLM
            llm = llm_client
            config = llm_config or llm_client.get_config()
            
            # 构建当前轮次的 prompt（包含完整历史，避免多轮工具结果丢失）
            # messages[0] = system, messages[1:] = 历史对话
            # 将 messages[1:] 拼接为单段文本传给 chat 接口
            if len(messages) > 2:
                # 多轮：把历史消息（不含 system）拼成一段话
                history_parts = []
                for msg in messages[1:]:
                    role_label = "用户" if msg["role"] == "user" else "助手"
                    history_parts.append(f"[{role_label}]: {msg['content']}")
                current_prompt = "\n\n".join(history_parts)
                current_prompt += "\n\n[助手]: 请继续完成任务。"
            else:
                current_prompt = messages[-1]["content"]
            
            # 构建消息
            if config.provider == "remote":
                # 远程 API 使用 messages 格式
                yield ("thinking", f"[迭代 {iterations}] 思考中...\n")
                
                try:
                    # 流式调用
                    full_response = ""
                    for chunk, chunk_type in llm.chat_stream(
                        prompt=current_prompt,
                        system=messages[0]["content"],
                        config_override=config
                    ):
                        if chunk_type == "text":
                            full_response += chunk
                        elif chunk_type == "thinking":
                            yield ("thinking", chunk)
                    
                    if not full_response:
                        yield ("text", "[错误] 模型返回为空")
                        break
                        
                except Exception as e:
                    yield ("text", f"[错误] 调用失败: {e}")
                    break
            else:
                # Ollama 本地调用
                yield ("thinking", f"[迭代 {iterations}] 思考中...\n")
                
                try:
                    content, thinking = llm.chat(
                        prompt=current_prompt,
                        system=messages[0]["content"],
                        config_override=config
                    )
                    if thinking:
                        yield ("thinking", thinking)
                    full_response = content
                except Exception as e:
                    yield ("text", f"[错误] 调用失败: {e}")
                    break
            
            # 解析工具调用
            tool_calls = self._parse_tool_calls(full_response)
            
            if not tool_calls:
                # 没有工具调用，清理残留的 TOOL_CALL 标记后返回结果
                clean_response = re.sub(
                    r'\[\[TOOL_CALL\]\].*?\[\[/TOOL_CALL\]\]',
                    '',
                    full_response,
                    flags=re.DOTALL
                ).strip()
                # 如果清理后为空，使用原始响应（避免空输出）
                yield ("text", clean_response if clean_response else full_response)
                break
            
            # 执行工具调用
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments", {})
                
                yield ("tool_call", json.dumps(tc, ensure_ascii=False))
                
                result, error = self._execute_tool(tool_name, tool_args)
                
                if error:
                    yield ("tool_result", error)
                    messages.append({"role": "user", "content": f"工具执行失败: {error}"})
                else:
                    yield ("tool_result", result)
                    # 将工具结果加入上下文
                    messages.append({
                        "role": "user", 
                        "content": f"工具 {tool_name} 返回结果:\n{result}"
                    })
            
            # 检查是否需要继续（根据上下文长度）
            if iterations >= max_iterations:
                yield ("text", f"\n[提示] 达到最大迭代次数 ({max_iterations})，如果任务未完成请重新提问。")
                break
        
        yield ("done", "")


# ── 便捷函数 ──────────────────────────────────────────────────────────────
def get_agent(config: Optional[AgentConfig] = None) -> Agent:
    """获取 Agent 实例"""
    return Agent(config)
