"""
agent.py
────────
Agent API 接口

路由:
  - POST /api/agent/chat - Agent 流式对话
  - GET /api/agent/tools - 获取可用工具列表
  - POST /api/agent/upload-and-analyze - 上传文件直接分析
  - POST /api/agent/analyze-dir - 目录批量分析
  - GET /api/agent/download - 下载生成的文书文件
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse, FileResponse

from app.core.agent import get_agent, AgentConfig, tool_registry
from app.core.llm_client import llm_client, LLMConfig
from app.models.schemas import AgentRequest

router = APIRouter(prefix="/api/agent", tags=["Agent"])
logger = logging.getLogger(__name__)


@router.get("/tools")
async def list_tools():
    """获取可用工具列表"""
    return {
        "tools": tool_registry.list_tools()
    }


@router.post("/chat")
async def agent_chat(request: AgentRequest):
    """
    Agent 流式对话接口（SSE）
    
    支持自主决策，调用工具完成复杂任务：
    - 读取文件分析
    - 目录批量处理
    - 知识库查询
    - 网络搜索
    - 生成文书
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="提示词不能为空")
    
    try:
        # 构建 LLM 配置
        llm_override = None
        if request.llm_provider or request.llm_ollama_model or request.llm_remote_model:
            base_cfg = llm_client.get_config()
            llm_override = base_cfg.__class__.__new__(base_cfg.__class__)
            llm_override.__dict__.update(base_cfg.__dict__)
            
            if request.llm_provider:
                llm_override.provider = request.llm_provider
            if request.llm_ollama_model:
                llm_override.ollama_model = request.llm_ollama_model
            if request.llm_remote_base_url:
                llm_override.remote_base_url = request.llm_remote_base_url
            if request.llm_remote_api_key:
                llm_override.remote_api_key = request.llm_remote_api_key
            if request.llm_remote_model:
                llm_override.remote_model = request.llm_remote_model
        
        # Agent 配置
        agent_config = AgentConfig(
            max_iterations=request.max_iterations or 10,
            verbose=True
        )
        
        # 创建 Agent
        agent = get_agent(agent_config)
        
        def generate():
            """生成 SSE 流"""
            try:
                for chunk_type, content in agent.chat(
                    prompt=request.prompt,
                    session_id=request.session_id,
                    llm_config=llm_override
                ):
                    if chunk_type == "done":
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        break
                    
                    # 构建 SSE 数据
                    data = {
                        "type": chunk_type,
                        "content": content
                    }
                    
                    # 特殊处理工具调用
                    if chunk_type == "tool_call":
                        try:
                            tool_data = json.loads(content)
                            data["tool"] = tool_data
                        except:
                            pass
                    
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    
            except Exception as e:
                logger.error(f"Agent 执行失败: {e}")
                error_data = {
                    "type": "error",
                    "content": f"执行错误: {str(e)}"
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        
    except Exception as e:
        logger.error(f"Agent 接口错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-and-analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    question: Optional[str] = "",
    session_id: Optional[str] = None,
):
    """
    上传文件并立即分析（不入库）
    
    流程：
    1. 保存上传文件到临时目录
    2. Agent 读取并分析
    3. 返回分析结果
    4. 清理临时文件
    """
    import tempfile
    import os
    
    if not file:
        raise HTTPException(status_code=400, detail="请上传文件")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="legal_rag_upload_")
    file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"[Agent] 上传文件已保存: {file_path}")
        
        # 构建提示词
        if not question:
            question = f"请分析这份文件《{file.filename}》的内容，识别其中的关键信息、风险点和法律问题。"
        
        prompt = f"""用户上传了一个文件，请使用 read_file 工具读取并分析。

文件路径: {file_path}

用户问题: {question}

请：
1. 先读取文件内容
2. 根据内容回答用户问题
3. 如果是合同或法律文档，指出关键条款和潜在风险"""
        
        # Agent 配置
        agent_config = AgentConfig(max_iterations=5)
        agent = get_agent(agent_config)
        
        def generate():
            """生成 SSE 流"""
            try:
                for chunk_type, content in agent.chat(
                    prompt=prompt,
                    session_id=session_id
                ):
                    if chunk_type == "done":
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        break
                    
                    data = {
                        "type": chunk_type,
                        "content": content
                    }
                    
                    if chunk_type == "tool_call":
                        try:
                            tool_data = json.loads(content)
                            data["tool"] = tool_data
                        except:
                            pass
                    
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    
            except Exception as e:
                logger.error(f"文件分析失败: {e}")
                error_data = {
                    "type": "error",
                    "content": f"分析错误: {str(e)}"
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            finally:
                # 清理临时文件
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.info(f"[Agent] 临时文件已清理: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        
    except Exception as e:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass
        
        logger.error(f"上传分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-dir")
async def analyze_dir(path: str, session_id: Optional[str] = None):
    """
    目录批量分析接口（SSE）
    
    遍历目录中所有文档，让 Agent 分析并生成汇总报告
    """
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="目录路径不能为空")
    
    abs_path = os.path.abspath(path.strip())
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail=f"目录不存在: {path}")
    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail=f"路径不是目录: {path}")
    
    prompt = f"""请对以下目录进行批量法律文档分析：

目录路径: {abs_path}

请按以下步骤操作：
1. 使用 analyze_dir 工具扫描目录，获取所有文件的内容摘要
2. 对各文件进行逐一分析，识别文件类型（合同/起诉状/法律意见书等）
3. 识别每个文档中的关键条款、当事人、日期等重要信息
4. 指出潜在的法律风险或问题
5. 生成完整的批量分析汇总报告

请确保报告清晰、专业，对每个文件都有详细的分析结论。"""
    
    agent_config = AgentConfig(max_iterations=8)
    agent = get_agent(agent_config)
    
    def generate():
        try:
            for chunk_type, content in agent.chat(
                prompt=prompt,
                session_id=session_id
            ):
                if chunk_type == "done":
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    break
                
                data = {"type": chunk_type, "content": content}
                if chunk_type == "tool_call":
                    try:
                        data["tool"] = json.loads(content)
                    except:
                        pass
                
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            logger.error(f"目录分析失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/download")
async def download_file(file_path: str = Query(..., description="要下载的文件绝对路径")):
    """
    下载 Agent 生成的文书文件
    
    安全限制：只允许下载工作目录和知识库目录下的文件
    """
    from app.config import settings
    
    abs_path = os.path.abspath(file_path)
    
    # 安全检查
    allowed_dirs = [
        os.getcwd(),
        settings.legal_docs_path or "",
        os.path.join(os.getcwd(), "output"),
        os.path.join(os.getcwd(), "generated"),
    ]
    
    is_allowed = any(
        abs_path.startswith(os.path.abspath(d))
        for d in allowed_dirs if d
    )
    
    if not is_allowed:
        raise HTTPException(status_code=403, detail="无权访问该文件路径")
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=400, detail="路径不是文件")
    
    filename = os.path.basename(abs_path)
    
    # 根据扩展名设置 Content-Type
    ext = os.path.splitext(filename)[1].lower()
    content_type_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pdf": "application/pdf",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
    }
    media_type = content_type_map.get(ext, "application/octet-stream")
    
    return FileResponse(
        path=abs_path,
        filename=filename,
        media_type=media_type,
    )



@router.get("/tools")
async def list_tools():
    """获取可用工具列表"""
    return {
        "tools": tool_registry.list_tools()
    }


@router.post("/chat")
async def agent_chat(request: AgentRequest):
    """
    Agent 流式对话接口（SSE）
    
    支持自主决策，调用工具完成复杂任务：
    - 读取文件分析
    - 目录批量处理
    - 知识库查询
    - 网络搜索
    - 生成文书
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="提示词不能为空")
    
    try:
        # 构建 LLM 配置
        llm_override = None
        if request.llm_provider or request.llm_ollama_model or request.llm_remote_model:
            base_cfg = llm_client.get_config()
            llm_override = base_cfg.__class__.__new__(base_cfg.__class__)
            llm_override.__dict__.update(base_cfg.__dict__)
            
            if request.llm_provider:
                llm_override.provider = request.llm_provider
            if request.llm_ollama_model:
                llm_override.ollama_model = request.llm_ollama_model
            if request.llm_remote_base_url:
                llm_override.remote_base_url = request.llm_remote_base_url
            if request.llm_remote_api_key:
                llm_override.remote_api_key = request.llm_remote_api_key
            if request.llm_remote_model:
                llm_override.remote_model = request.llm_remote_model
        
        # Agent 配置
        agent_config = AgentConfig(
            max_iterations=request.max_iterations or 10,
            verbose=True
        )
        
        # 创建 Agent
        agent = get_agent(agent_config)
        
        def generate():
            """生成 SSE 流"""
            try:
                for chunk_type, content in agent.chat(
                    prompt=request.prompt,
                    session_id=request.session_id,
                    llm_config=llm_override
                ):
                    if chunk_type == "done":
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        break
                    
                    # 构建 SSE 数据
                    data = {
                        "type": chunk_type,
                        "content": content
                    }
                    
                    # 特殊处理工具调用
                    if chunk_type == "tool_call":
                        try:
                            tool_data = json.loads(content)
                            data["tool"] = tool_data
                        except:
                            pass
                    
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    
            except Exception as e:
                logger.error(f"Agent 执行失败: {e}")
                error_data = {
                    "type": "error",
                    "content": f"执行错误: {str(e)}"
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        
    except Exception as e:
        logger.error(f"Agent 接口错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-and-analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    question: Optional[str] = "",
    session_id: Optional[str] = None,
):
    """
    上传文件并立即分析（不入库）
    
    流程：
    1. 保存上传文件到临时目录
    2. Agent 读取并分析
    3. 返回分析结果
    4. 清理临时文件
    """
    import tempfile
    import os
    
    if not file:
        raise HTTPException(status_code=400, detail="请上传文件")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="legal_rag_upload_")
    file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"[Agent] 上传文件已保存: {file_path}")
        
        # 构建提示词
        if not question:
            question = f"请分析这份文件《{file.filename}》的内容，识别其中的关键信息、风险点和法律问题。"
        
        prompt = f"""用户上传了一个文件，请使用 read_file 工具读取并分析。

文件路径: {file_path}

用户问题: {question}

请：
1. 先读取文件内容
2. 根据内容回答用户问题
3. 如果是合同或法律文档，指出关键条款和潜在风险"""
        
        # Agent 配置
        agent_config = AgentConfig(max_iterations=5)
        agent = get_agent(agent_config)
        
        def generate():
            """生成 SSE 流"""
            try:
                for chunk_type, content in agent.chat(
                    prompt=prompt,
                    session_id=session_id
                ):
                    if chunk_type == "done":
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        break
                    
                    data = {
                        "type": chunk_type,
                        "content": content
                    }
                    
                    if chunk_type == "tool_call":
                        try:
                            tool_data = json.loads(content)
                            data["tool"] = tool_data
                        except:
                            pass
                    
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    
            except Exception as e:
                logger.error(f"文件分析失败: {e}")
                error_data = {
                    "type": "error",
                    "content": f"分析错误: {str(e)}"
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            finally:
                # 清理临时文件
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.info(f"[Agent] 临时文件已清理: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        
    except Exception as e:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass
        
        logger.error(f"上传分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
