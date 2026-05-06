"""
文档质量评估器 - 评估文档质量、相关性、权威性
"""
import re
import json
import logging
from typing import Dict, Any, Optional
from .pending_pool import PendingDocument

logger = logging.getLogger(__name__)


class DocumentEvaluator:
    """文档质量评估器"""
    
    def __init__(self, llm_client):
        """
        初始化评估器
        
        Args:
            llm_client: LLM客户端
        """
        self.llm_client = llm_client
        
        # 权威性评分表
        self.authority_scores = {
            'gov.cn': 1.0,  # 政府网站
            'court.gov.cn': 0.95,  # 法院官网
            'moj.gov.cn': 0.9,  # 司法部官网
            'npc.gov.cn': 0.9,  # 全国人大官网
            'wenshu.court.gov.cn': 0.95,  # 裁判文书网
            'pkulaw.com': 0.8,  # 北大法宝
            'chinacourt.org': 0.8,  # 中国法院网
            'people.com.cn': 0.75,  # 人民网
            'xinhuanet.com': 0.75,  # 新华网
            'cctv.com': 0.7,  # 央视网
            'thepaper.cn': 0.65,  # 澎湃新闻
            'caixin.com': 0.65,  # 财新网
            'default': 0.5  # 默认评分
        }
        
        # 评估权重
        self.weights = {
            'quality': 0.4,  # 内容质量权重
            'relevance': 0.4,  # 相关性权重
            'authority': 0.2  # 权威性权重
        }
        
        # 评分阈值
        self.thresholds = {
            'high': 0.8,  # 高质量阈值
            'medium': 0.6  # 中等质量阈值
        }
        
        logger.info("文档质量评估器初始化完成")
    
    def evaluate(self, doc: PendingDocument, query: str, answer: str) -> Dict[str, Any]:
        """
        评估文档质量
        
        Args:
            doc: 待评估文档
            query: 用户查询
            answer: 返回给用户的答案
            
        Returns:
            评估结果字典：
            {
                'quality_score': float,  # 0-1 质量评分
                'should_keep': bool,  # 是否应该入库
                'reason': str,  # 决策原因
                'categories': List[str],  # 文档类别
                'assessments': {  # 各维度详细评分
                    'quality': dict,
                    'relevance': dict,
                    'authority': dict
                }
            }
        """
        try:
            logger.info(f"开始评估文档 {doc.id}")
            
            # 1. 内容质量评估
            quality_assessment = self._assess_quality(doc.content)
            
            # 2. 相关性评估
            relevance_assessment = self._assess_relevance(doc.content, query, answer)
            
            # 3. 权威性评估
            authority_assessment = self._assess_authority(doc.source_url)
            
            # 4. 综合评分
            quality_score = self._calculate_final_score(
                quality_assessment,
                relevance_assessment,
                authority_assessment
            )
            
            # 5. 决策
            should_keep, reason = self._make_decision(quality_score, {
                'quality': quality_assessment,
                'relevance': relevance_assessment,
                'authority': authority_assessment
            })
            
            result = {
                'quality_score': quality_score,
                'should_keep': should_keep,
                'reason': reason,
                'categories': relevance_assessment.get('categories', []),
                'assessments': {
                    'quality': quality_assessment,
                    'relevance': relevance_assessment,
                    'authority': authority_assessment
                }
            }
            
            logger.info(f"文档 {doc.id} 评估完成: 质量评分={quality_score:.2f}, 决策={'保留' if should_keep else '丢弃'}")
            return result
            
        except Exception as e:
            logger.error(f"评估文档 {doc.id} 失败: {e}")
            # 返回默认评估结果
            return {
                'quality_score': 0.5,
                'should_keep': False,
                'reason': f"评估失败: {str(e)}",
                'categories': [],
                'assessments': {
                    'quality': {'score': 5.0, 'error': str(e)},
                    'relevance': {'score': 5.0, 'error': str(e)},
                    'authority': {'score': 0.5}
                }
            }
    
    def _assess_quality(self, content: str) -> Dict[str, Any]:
        """
        评估内容质量
        
        Args:
            content: 文档内容
            
        Returns:
            质量评估结果
        """
        # 截断内容，避免太长
        content_preview = content[:1500] if len(content) > 1500 else content
        
        prompt = f"""请评估以下法律内容的质量（0-10分）：

内容：
{content_preview}

评估维度：
1. 内容完整性（是否有完整的信息）
2. 逻辑清晰度（是否有条理）
3. 实用性（是否对用户有帮助）
4. 准确性（是否有明显错误）
5. 专业性（是否专业、权威）

请以 JSON 格式返回：
{{
    "score": 7.5,
    "completeness": 8,
    "clarity": 7,
    "usefulness": 8,
    "accuracy": 7,
    "professionalism": 8,
    "strengths": ["内容完整", "条理清晰"],
    "weaknesses": ["部分描述不够详细"]
}}

注意：只返回JSON，不要有其他文字。"""
        
        try:
            response, _ = self.llm_client.chat(
                prompt=prompt,
                system="你是一个专业的法律文档质量评估助手。请对以下法律内容进行质量评估，只返回JSON格式的评分结果。"
            )
            
            result = self._parse_json_response(response)
            
            # 验证评分范围
            if 'score' not in result or not (0 <= result['score'] <= 10):
                result['score'] = 5.0
            
            logger.debug(f"质量评估完成: score={result['score']}")
            return result
            
        except Exception as e:
            logger.warning(f"质量评估失败: {e}，使用默认值")
            return {
                'score': 5.0,
                'completeness': 5,
                'clarity': 5,
                'usefulness': 5,
                'accuracy': 5,
                'professionalism': 5,
                'strengths': [],
                'weaknesses': ['评估失败']
            }
    
    def _assess_relevance(self, content: str, query: str, answer: str) -> Dict[str, Any]:
        """
        评估相关性
        
        Args:
            content: 文档内容
            query: 用户查询
            answer: AI答案
            
        Returns:
            相关性评估结果
        """
        # 截断内容
        content_preview = content[:1500] if len(content) > 1500 else content
        answer_preview = answer[:500] if len(answer) > 500 else answer
        
        prompt = f"""用户查询：{query}
AI答案：{answer_preview}
候选文档：{content_preview}

评估候选文档与查询/答案的相关性：
1. 是否直接回答了用户问题？
2. 是否补充了答案中的重要信息？
3. 是否提供了不同的视角？
4. 属于哪个法律领域？（如：劳动合同、工资报酬、工伤认定、合同法、侵权法、刑法等）
5. 属于什么类型？（如：法律条文、案例判例、专业解读、政策文件）

请以 JSON 格式返回：
{{
    "score": 8.5,
    "direct_answer": true,
    "complements_answer": true,
    "provides_new_perspective": false,
    "legal_domain": "劳动合同",
    "document_type": "法律条文",
    "categories": ["法律条文", "合同解除"]
}}

注意：只返回JSON，不要有其他文字。"""
        
        try:
            response, _ = self.llm_client.chat(
                prompt=prompt,
                system="你是一个专业的法律文档相关性评估助手。请评估以下法律内容与用户问题的相关性，只返回JSON格式的评分结果。"
            )
            
            result = self._parse_json_response(response)
            
            # 验证评分范围
            if 'score' not in result or not (0 <= result['score'] <= 10):
                result['score'] = 5.0
            
            logger.debug(f"相关性评估完成: score={result['score']}")
            return result
            
        except Exception as e:
            logger.warning(f"相关性评估失败: {e}，使用默认值")
            return {
                'score': 5.0,
                'direct_answer': False,
                'complements_answer': False,
                'provides_new_perspective': False,
                'legal_domain': '未知',
                'document_type': '未知',
                'categories': []
            }
    
    def _assess_authority(self, source_url: str) -> Dict[str, Any]:
        """
        评估来源权威性
        
        Args:
            source_url: 来源URL
            
        Returns:
            权威性评估结果
        """
        # 基于URL的权威性评分
        score = self.authority_scores.get('default', 0.5)
        domain = 'unknown'
        
        for d, s in self.authority_scores.items():
            if d in source_url:
                score = s
                domain = d
                break
        
        logger.debug(f"权威性评估完成: url={source_url}, domain={domain}, score={score}")
        
        return {
            'score': score,
            'domain': domain,
            'url': source_url
        }
    
    def _calculate_final_score(self, quality: Dict, relevance: Dict, authority: Dict) -> float:
        """
        计算最终评分
        
        Args:
            quality: 质量评估结果
            relevance: 相关性评估结果
            authority: 权威性评估结果
            
        Returns:
            最终评分（0-1）
        """
        # 获取各维度评分（归一化到0-1）
        quality_score = min(quality.get('score', 0) / 10, 1.0)
        relevance_score = min(relevance.get('score', 0) / 10, 1.0)
        authority_score = min(authority.get('score', 0), 1.0)
        
        # 加权计算
        final_score = (
            self.weights['quality'] * quality_score +
            self.weights['relevance'] * relevance_score +
            self.weights['authority'] * authority_score
        )
        
        # 确保不超过1.0
        final_score = min(final_score, 1.0)
        
        logger.debug(f"综合评分: quality={quality_score:.2f}, relevance={relevance_score:.2f}, authority={authority_score:.2f}, final={final_score:.2f}")
        return final_score
    
    def _make_decision(self, quality_score: float, assessments: Dict) -> tuple:
        """
        做出决策
        
        Args:
            quality_score: 综合质量评分
            assessments: 各维度评估结果
            
        Returns:
            (should_keep, reason) 是否应该入库，决策原因
        """
        try:
            if quality_score >= self.thresholds['high']:
                # 高质量，必须入库
                reasons = ["质量优秀"]
                if assessments['quality'].get('strengths'):
                    reasons.append(f"优势：{', '.join(assessments['quality']['strengths'][:2])}")
                if assessments['relevance'].get('direct_answer'):
                    reasons.append("直接回答用户问题")
                return True, "，".join(reasons)
            
            elif quality_score >= self.thresholds['medium']:
                # 中等质量，检查是否有明显优势
                if assessments['relevance'].get('direct_answer'):
                    return True, "质量良好，直接回答了用户问题"
                elif assessments['relevance'].get('complements_answer'):
                    return True, "质量良好，补充了答案信息"
                elif assessments['quality'].get('score', 0) >= 7:
                    return True, f"内容质量较高（{assessments['quality']['score']}/10），建议保留"
                else:
                    weaknesses = assessments['quality'].get('weaknesses', ['内容质量一般'])
                    return False, f"质量一般，{weaknesses[0] if weaknesses else '相关性不强'}，暂不入库"
            
            else:
                # 低质量
                weaknesses = assessments['quality'].get('weaknesses', ['内容质量不足'])
                return False, f"质量较低（评分：{quality_score:.2f}），{weaknesses[0] if weaknesses else '内容质量不足'}，不建议入库"
        
        except Exception as e:
            logger.error(f"决策失败: {e}")
            return False, f"决策失败: {str(e)}"
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析JSON响应
        
        Args:
            response: LLM响应
            
        Returns:
            解析后的字典
        """
        # 尝试直接解析
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        # 尝试提取JSON部分
        json_match = re.search(r'\{[^{}]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 尝试提取多层级JSON
        json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 返回默认值
        logger.warning(f"无法解析JSON响应: {response[:100]}")
        return {'score': 5.0}


def get_document_evaluator():
    """
    获取文档评估器单例
    
    Returns:
        文档评估器实例
    """
    from app.core.llm_client import llm_client
    return DocumentEvaluator(llm_client)
