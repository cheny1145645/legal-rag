"""
LCCP: 法律推理链置信度传播（Legal Chain Confidence Propagation）

功能：
1. 引导LLM按"事实认定→法律关系→条文适用→结论"四步推理
2. 计算每步推理的置信度
3. 通过链式乘积计算最终答案可信度

公式：Conf(C) = ∏ p_i^(λ^(4-i))
其中 λ 是衰减因子，控制后续步骤对总置信度的影响权重
"""

import logging
import re
from typing import List, Tuple, Optional, Dict

from langchain.schema import Document

logger = logging.getLogger(__name__)

# ── LCCP 系统提示词 ───────────────────────────────────────────────────
LCCP_SYSTEM_PROMPT = """你是一名中国法律推理专家。请按以下四步结构分析法律问题，每一步都必须明确输出：

【第一步：事实认定】
简要描述案件的核心事实（谁、在什么时候、做了什么）

【第二步：法律关系】
分析涉及的法律关系（如劳动关系、侵权关系、合同关系等）

【第三步：条文适用】
找出最可能适用的法律条文，给出具体条款编号（如《劳动合同法》第47条）

【第四步：结论】
给出最终的法律意见和行动建议

注意：如果某一步无法确定，照实写"不确定"，这不会扣分。
只输出这四步内容，每步用一行"【第一步】"这样的标记开头。"""


class LCCPConfidence:
    """
    法律推理链置信度计算器
    
    属性：
    - _decay_factor: 衰减因子 λ ∈ (0,1)，默认0.7
    _conf_threshold: 置信度阈值，低于此值给出警告
    """
    
    def __init__(self, decay_factor: float = 0.7, conf_threshold: float = 0.5):
        self._decay_factor = decay_factor
        self._conf_threshold = conf_threshold
    
    def _extract_confidences(self, reasoning: str) -> Dict[int, float]:
        """
        从LLM的推理文本中提取各步的置信度
        
        Returns:
            {step: confidence} 字典，confidence ∈ (0,1)
        """
        # 简单规则：检测"不确定"关键词
        step_patterns = [
            r"【第一步[：：\s]*(.*?)(?=【第二步|$)",
            r"【第二步[：：\s]*(.*?)(?=【第三步|$)",
            r"【第三步[：：\s]*(.*?)(?=【第四步|$)",
            r"【第四步[：：\s]*(.*?)$",
        ]
        
        confidences = {}
        for i, pattern in enumerate(step_patterns, 1):
            match = re.search(pattern, reasoning, re.DOTALL)
            if match:
                content = match.group(1).strip()
                # 有"不确定"则低置信度
                if "不确定" in content or "无法确定" in content:
                    confidences[i] = 0.3
                # 有具体法条编号则高置信度
                elif re.search(r"第\d+条", content):
                    confidences[i] = 0.9
                else:
                    confidences[i] = 0.7
            else:
                confidences[i] = 0.5  # 默认
        
        return confidences
    
    def compute_confidence(self, reasoning: str) -> Tuple[float, Dict]:
        """
        计算最终置信度
        
        公式：Conf = ∏ p_i^(λ^(4-i))
        
        Args:
            reasoning: LLM的推理过程文本
        
        Returns:
            (final_confidence, step_confidences)
        """
        step_conf = self._extract_confidences(reasoning)
        
        # 计算链式置信度
        final_conf = 1.0
        for i, p_i in step_conf.items():
            decay = self._decay_factor ** (4 - i)
            final_conf *= (p_i ** decay)
        
        logger.info(
            f"[LCCP] 置信度: {final_conf:.3f}, "
            f"各步: {step_conf}, "
            f"推理长度: {len(reasoning)}"
        )
        
        return final_conf, step_conf
    
    def get_confidence_label(self, confidence: float) -> str:
        """将数值置信度转换为标签"""
        if confidence >= 0.7:
            return "高"
        elif confidence >= 0.4:
            return "中"
        else:
            return "低"
    
    def evaluate_answer(
        self,
        answer: str,
        context_docs: List[Tuple[Document, float]],
    ) -> Dict:
        """
        评估答案的可信度
        
        检查答案中引用的条文是否在检索结果中有依据
        
        Returns:
            {
                "confidence": float,
                "label": str,
                "citation_check": { "found": int, "missing": int },
                "warnings": [str],
            }
        """
        # 提取答案中引用的条文编号（支持《》或无书名号）
        cited_articles = re.findall(r"(?:[《》]?)(.+?第\d+条)", answer)
        
        # 检查是否在检索结果中
        found_count = 0
        missing_count = 0
        context_text = "\n".join(doc.page_content for doc, _ in context_docs)
        
        for article in cited_articles:
            if article in context_text or article.replace("《", "").replace("》", "") in context_text:
                found_count += 1
            else:
                missing_count += 1
        
        warnings = []
        if missing_count > 0:
            warnings.append(f"答案引用了{missing_count}个条文但在检索结果中未找到依据")
        
        # 综合置信度
        citation_score = found_count / max(len(cited_articles), 1) if cited_articles else 1.0
        
        return {
            "confidence": citation_score,
            "label": self.get_confidence_label(citation_score),
            "citation_check": {
                "found": found_count,
                "missing": missing_count,
            },
            "warnings": warnings,
        }


# 全局单例
lccp_confidence = LCCPConfidence()