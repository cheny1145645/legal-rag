"""
联网检索模块 v2.1:

当知识库召回置信度不足时，自动触发网络检索补充上下文。

检索策略（按质量优先级从高到低）：
  1. Tavily           —— AI优化搜索，质量最高（需API Key）
  2. Jina Reader      —— LLM优化内容抓取，免费开源
  3. OpenLaw          —— 法条精准
  4. 北大法宝         —— 补充法规
  5. 法律专业网站     —— 法信、无讼、律商网
  6. Playwright 深层抓取
  7. 必应搜索兜底

触发条件（任一满足）：
  1. enable_web_search_override=True（前端强制开启）
  2. 知识库检索最高相似度 < WEB_SEARCH_THRESHOLD
  3. 知识库返回结果数量 < WEB_SEARCH_MIN_DOCS
"""
import logging
import re
import time
from typing import List, Tuple, Optional
from urllib.parse import quote_plus, urljoin

from langchain.schema import Document

logger = logging.getLogger(__name__)

# 触发阈值（相似度分数低于此值则触发）
WEB_SEARCH_THRESHOLD = 0.5
# 知识库结果数量低于此值也触发
WEB_SEARCH_MIN_DOCS = 2
# 网络检索返回最大文档数
WEB_MAX_RESULTS = 4
# 请求超时（秒）
REQUEST_TIMEOUT = 10
# Playwright 详情页最大抓取字符数（防止超长页面撑爆 context）
PLAYWRIGHT_MAX_CONTENT = 3000
# Playwright 每次最多进入几个详情页
PLAYWRIGHT_MAX_DETAIL_PAGES = 3

# ── 主题过滤 ──────────────────────────────────────────────────────────────────
_NOISE_KEYWORDS = (
    "红毯", "造型", "女朋友", "男朋友", "明星", "网红", "颜值", "发型",
    "时尚", "穿搭", "博主", "直播", "粉丝", "综艺", "选秀", "追星",
    "NBA", "球员", "赛季", "上场", "得分王", "冠军赛", "转会",
    "点击阅读", "限时优惠", "折扣", "购买链接", "立即抢购", "优惠券",
    "张图", "评点击", "阅读全文",
    "八卦", "爆料", "偷拍", "狗仔", "私生活",
    "核磁", "MRI", "手术", "病历", "症状", "诊断", "治疗方案",
    "病句", "语法", "句式", "汉语", "词法", "语言学",
    "食谱", "烹饪", "旅游", "美食", "景点",
)

_LEGAL_KEYWORDS = (
    "法律", "法规", "条款", "合同", "诉讼", "仲裁", "判决", "裁定",
    "司法", "检察", "律师", "辩护", "起诉", "被告", "原告", "庭审",
    "法院", "法典", "刑法", "民法", "行政法", "宪法", "著作权", "专利",
    "商标", "合规", "违法", "犯罪", "惩处", "罚款", "禁止", "规定",
    "条例", "办法", "实施细则", "司法解释", "最高人民法院",
    "劳动合同", "劳动法", "工伤", "赔偿", "补偿", "经济补偿", "违约",
    "解除", "终止", "续签", "用人单位", "劳动者", "社保",
    "婚姻法", "离婚", "抚养权", "财产分割", "继承",
    "量刑", "逮捕", "拘留", "羁押", "取保候审", "缓刑", "假释",
    "权利义务", "债权", "债务", "担保", "抵押", "质押", "诉讼时效",
    "行政处罚", "行政许可", "行政复议", "国家赔偿",
    # 新增劳动法律相关关键词
    "不续签", "续签合同", "劳动合同到期", "离职", "辞退", "裁员",
    "加班费", "加班工资", "年终奖", "带薪年假", "婚假", "产假",
    "社保缴费", "五险一金", "工伤认定", "工伤赔偿", "伤残等级",
    "劳动争议", "劳动仲裁", "劳动合同法", "劳务派遣", "外包",
    "最低工资", "工资", "薪酬", "奖金", "补贴", "加班",
    "工作时间", "休息日", "节假日", "年休假", "病假", "事假",
    "解除劳动合同", "违法解除", "经济性裁员", "协商解除",
    "双倍工资", "赔偿金", "抚恤金", "供养亲属",
)


def _is_legal_relevant(text: str) -> bool:
    for kw in _NOISE_KEYWORDS:
        if kw in text:
            logger.debug(f"[主题过滤] 噪音词命中 '{kw}'，丢弃: {text[:60]}")
            return False
    for kw in _LEGAL_KEYWORDS:
        if kw in text:
            return True
    legal_structure_patterns = (
        r"第[一二三四五六七八九十百千]+条",
        r"根据.*法",
        r"依照.*规定",
        r"违反.*条款",
    )
    for pattern in legal_structure_patterns:
        if re.search(pattern, text):
            if len(text) > 50:
                return True
    logger.debug(f"[主题过滤] 无法律特征，丢弃: {text[:60]}")
    return False


def _get_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


# ── OpenLaw 检索 ──────────────────────────────────────────────────────────────

def _search_openlaw(query: str, max_results: int = 3) -> List[Document]:
    try:
        import requests
        from bs4 import BeautifulSoup

        url = f"https://openlaw.cn/search/laws?kw={quote_plus(query)}"
        # allow_redirects=False：OpenLaw 未登录时会 302 跳转到 /login，
        # 不跟随重定向，检测到重定向直接跳过，避免抓到登录页然后解析空结果
        resp = requests.get(url, headers=_get_headers(), timeout=REQUEST_TIMEOUT, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            logger.debug(f"[OpenLaw] 被重定向到 {resp.headers.get('Location', '?')}（需登录），跳过")
            return []
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []

        items = (
            soup.select(".law-search-item")
            or soup.select(".result-item")
            or soup.select("div[class*='law-item']")
            or soup.select("div[class*='search-item']")
            or soup.select("div[class*='result']")
            or soup.select("li")
        )

        for item in items[:max_results]:
            title_el = item.select_one("a, h3, h4, .title, [class*='title']")
            snippet_el = item.select_one("p, .summary, .content, .abstract, [class*='content']")
            link_el = item.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else "OpenLaw法条"
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = urljoin("https://openlaw.cn", href)

            if snippet and len(snippet) > 20:
                doc = Document(
                    page_content=snippet,
                    metadata={
                        "source": f"OpenLaw - {title}",
                        "url": href,
                        "from_web": True,
                        "web_source": "openlaw",
                    },
                )
                docs.append(doc)

        if docs:
            logger.info(f"[OpenLaw] 检索到 {len(docs)} 条结果: {query[:30]}")
        else:
            logger.info(f"[OpenLaw] 未检索到有效结果: {query[:30]}")
        return docs

    except Exception as e:
        logger.warning(f"[OpenLaw] 检索失败: {e}")
        return []


# ── 北大法宝检索 ──────────────────────────────────────────────────────────────

def _search_pkulaw(query: str, max_results: int = 2) -> List[Document]:
    try:
        import requests
        from bs4 import BeautifulSoup

        url = f"https://www.pkulaw.com/law?keyword={quote_plus(query)}"
        resp = requests.get(url, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []

        items = (
            soup.select(".list-result li")
            or soup.select(".result-list .item")
            or soup.select("ul.law-list li")
        )

        for item in items[:max_results]:
            title_el = item.select_one("a, .title")
            snippet_el = item.select_one(".abstract, .summary, p")
            link_el = item.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else "北大法宝"
            snippet = snippet_el.get_text(strip=True) if snippet_el else title
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = urljoin("https://www.pkulaw.com", href)

            if snippet and len(snippet) > 10:
                doc = Document(
                    page_content=snippet,
                    metadata={
                        "source": f"北大法宝 - {title}",
                        "url": href,
                        "from_web": True,
                        "web_source": "pkulaw",
                    },
                )
                docs.append(doc)

        if docs:
            logger.info(f"[北大法宝] 检索到 {len(docs)} 条结果: {query[:30]}")
        return docs

    except Exception as e:
        logger.warning(f"[北大法宝] 检索失败: {e}")
        return []


# ── Playwright 深层抓取（从必应结果详情页提取正文）──────────────────────────────

def _playwright_search_and_fetch(query: str, max_results: int = 3) -> List[Document]:
    """
    Playwright 深层抓取：
    1. 先用必应搜索获取法律相关结果链接
    2. 用 Playwright 打开每个链接，提取页面正文内容
    3. 过滤广告和噪音，返回干净的正文
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[Playwright] 未安装 Playwright，跳过深层抓取")
        return []

    docs = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # 1. 先用必应搜索获取链接
            legal_query = f"{query} 法律法规"
            bing_url = f"https://www.bing.com/search?q={quote_plus(legal_query)}&setlang=zh-CN&cc=CN"

            try:
                page = context.new_page()
                page.goto(bing_url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                # 提取搜索结果链接
                results = page.query_selector_all("#b_results li.b_algo a")
                if not results:
                    results = page.query_selector_all("li[class*='algo'] a")

                links = []
                for a in results[:max_results * 2]:  # 取更多候选
                    href = a.get_attribute("href")
                    if href and href.startswith("http") and "microsoft.com" not in href:
                        # 过滤广告
                        if any(x in href.lower() for x in ["ad.", "click.", "track."]):
                            continue
                        links.append(href)
                links = list(set(links))[:max_results]  # 去重

                logger.info(f"[Playwright] 必应搜索获取到 {len(links)} 个候选链接")
                page.close()

            except Exception as e:
                logger.warning(f"[Playwright] 必应搜索阶段失败: {e}")
                browser.close()
                return []

            # 2. 逐个打开详情页，提取正文
            for url in links:
                try:
                    page = context.new_page()
                    page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)

                    # 提取页面标题
                    title = page.title()[:100] if page.title() else "无标题"

                    # 提取正文内容（尝试多种选择器，过滤广告）
                    content = ""

                    # 移除广告和噪音元素
                    ad_selectors = [".ad", ".ads", ".advertisement", "[class*='ad']", "[id*='ad']", 
                                   ".sidebar", ".footer", ".header", "script", "style", "nav", "header"]
                    for sel in ad_selectors:
                        try:
                            for el in page.query_selector_all(sel):
                                el.evaluate("el => el.remove()")
                        except:
                            pass

                    # 提取正文（优先法律内容区域）
                    content_selectors = [
                        ".article-content", ".article-body", ".content", ".main-content",
                        ".law-content", ".text", "article", "main", "[class*='content']",
                        ".b_context", "#b_context"
                    ]

                    for sel in content_selectors:
                        el = page.query_selector(sel)
                        if el:
                            content = el.inner_text()
                            if len(content) > 200:  # 内容足够长
                                break

                    # 如果没找到，提取 body 全文
                    if not content or len(content) < 200:
                        body = page.query_selector("body")
                        if body:
                            content = body.inner_text()
                            # 进一步清理噪音
                            noise_patterns = ["登录", "注册", "扫码", "下载", "APP", "微信", "公众号"]
                            for noise in noise_patterns:
                                content = content.replace(noise, "")

                    # 清理内容
                    content = "\n".join([line.strip() for line in content.split("\n") if line.strip()])
                    content = re.sub(r"\s+", " ", content).strip()

                    if content and len(content) > 150:  # 内容够长才保留
                        # 主题过滤
                        if _is_legal_relevant(content):
                            doc = Document(
                                page_content=content[:PLAYWRIGHT_MAX_CONTENT],  # 限制长度
                                metadata={
                                    "source": f"深层抓取 - {title[:40]}",
                                    "url": url,
                                    "from_web": True,
                                    "web_source": "playwright",
                                },
                            )
                            docs.append(doc)
                            logger.info(f"[Playwright] 成功抓取: {title[:40]} ({len(content)} 字符)")

                    page.close()

                except Exception as e:
                    logger.debug(f"[Playwright] 抓取失败: {url[:50]} - {e}")
                    try:
                        page.close()
                    except:
                        pass
                    continue

            context.close()
            browser.close()

    except Exception as e:
        logger.warning(f"[Playwright] 深层抓取出错: {e}")

    logger.info(f"[Playwright] 深层抓取完成，获取 {len(docs)} 条文档")
    return docs


# ── 必应搜索（改进版，更精准的法律内容过滤）──────────────────────────────────

def _search_bing(query: str, max_results: int = 5) -> List[Document]:
    """
    爬取必应搜索结果，搜索词自动附加"法律法规"。
    改进点：
    1. 增加结果数量（5条），过滤前保留更多候选
    2. 更宽松的主题过滤（必应结果质量较高）
    3. 优先保留来自法律专业域名的结果
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        legal_query = f"{query} 法律法规"
        url = f"https://www.bing.com/search?q={quote_plus(legal_query)}&setlang=zh-CN&cc=CN"

        resp = requests.get(url, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []

        # 必应搜索结果结构
        results = soup.select("#b_results li.b_algo")
        if not results:
            results = soup.select(".b_algo") or soup.select("li[class*='algo']")

        # 法律相关域名白名单（这些域名的内容优先保留）
        legal_domains = [
            # 政府网站
            ".gov.cn", "gov.cn", ".gov",
            # 司法机关
            "court.gov.cn", "moj.gov.cn", "npc.gov.cn", " Supreme People's Court",
            # 法律专业网站
            "openlaw.cn", "pkulaw.com",  # 北大法宝
            "66law.cn", "lawyer365.com", "china.findlaw.cn",  # 找法网、华律网
            "lawtime.cn", "lawyee.com", "jufaanli.com",  # 法律快车、法律引擎、聚法
            "faxin.cn", "itslaw.com", "lexisnexis.cn",  # 法信、无讼、律商网
            # 企业信息/裁判文书
            "tianyancha.com", "qichacha.com",
            "wenshu.court.gov.cn", "splcgk.court.gov.cn",
            "chinacourt.org", "ggzy.gov.cn",
            # 知识产权
            "cnipa.gov.cn", "sipo.gov.cn", "ipraction.cn",
            # 其他法律相关
            "lawnet.cn", "lawking.com.cn", "chinalawinfo.com",
            "lawease.com", "bmla.org.cn", "lawbridge.org",
            "mla.gov.cn",  # 市场监管
        ]

        for item in results[:max_results * 2]:  # 取更多候选，过滤后保留 max_results
            title_el = item.select_one("h2 a, h3 a, .b_title a")
            snippet_el = item.select_one(".b_caption p, .b_descript, p")
            link_el = item.select_one("a[href]")

            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            href = link_el["href"]

            # 过滤非 http 链接
            if not href.startswith("http"):
                continue

            # 过滤广告链接（百度、必应广告及各种追踪链接）
            if any(x in href.lower() for x in ["ad.", "click.", "track.", "microsoft.com/ads", 
                "baidu.com/s?wd=ad", "baidu.com/click", "doubleclick", "googlesyndication"]):
                continue

            # 优先保留法律域名
            is_legal_domain = any(d in href for d in legal_domains)

            # 主题过滤：法律域名直接放行，其他域名检查关键词
            if is_legal_domain:
                pass_content = True
            else:
                pass_content = _is_legal_relevant(title + " " + snippet)

            if snippet and len(snippet) > 30 and pass_content:
                doc = Document(
                    page_content=snippet,
                    metadata={
                        "source": f"必应搜索 - {title}",
                        "url": href,
                        "from_web": True,
                        "web_source": "bing",
                        "is_legal_domain": is_legal_domain,
                    },
                )
                docs.append(doc)

        # 按是否法律域名排序，优先放法律域名的内容
        docs.sort(key=lambda d: d.metadata.get("is_legal_domain", False), reverse=True)

        if docs:
            logger.info(f"[必应] 检索到 {len(docs)} 条结果（法律域名: {sum(d.metadata.get('is_legal_domain') for d in docs)}）: {query[:30]}")
        else:
            logger.info(f"[必应] 未检索到有效结果: {query[:30]}")
        return docs[:max_results]

    except Exception as e:
        logger.warning(f"[必应] 检索失败: {e}")
        return []


# ── Jina Reader 抓取（LLM优化）────────────────────────────────────────────────────

_JINA_TIMEOUT = 8  # Jina Reader 单次请求超时（秒），国内网络常超时，缩短避免卡顿
_jina_reachable: Optional[bool] = None  # None=未探测，True=可达，False=不可达


def _check_jina_reachable() -> bool:
    """
    探测 r.jina.ai 是否可达（只做一次 HEAD 探测，结果全局缓存）。
    超时 5 秒视为不可达，后续所有 Jina 请求直接跳过，避免多次 20s 等待。
    """
    global _jina_reachable
    if _jina_reachable is not None:
        return _jina_reachable
    try:
        import requests
        requests.head("https://r.jina.ai/", timeout=5)
        _jina_reachable = True
        logger.debug("[Jina Reader] 连通性探测: 可达")
    except Exception as e:
        _jina_reachable = False
        logger.info(f"[Jina Reader] 连通性探测失败，本次会话跳过 Jina（{e}）")
    return _jina_reachable


def _jina_fetch_content(url: str) -> str:
    """
    使用 Jina Reader 直接抓取任意 URL，返回清洗后的正文。
    Jina Reader 专为 LLM 优化，自动清理广告、导航栏、噪音内容。
    """
    # 先做连通性探测，不可达直接返回
    if not _check_jina_reachable():
        return ""
    
    try:
        import requests
        
        if url.startswith("http"):
            jina_url = f"https://r.jina.ai/{url}"
        else:
            jina_url = f"https://r.jina.ai/http://{url}"
        
        resp = requests.get(jina_url, headers=_get_headers(), timeout=_JINA_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        
        content = resp.text.strip()
        
        if content and len(content) > 100:
            if "Error" in content[:200] or "Not Found" in content[:200] or "blocked" in content.lower()[:200]:
                logger.debug(f"[Jina Reader] 抓取被拒绝: {url[:50]}")
                return ""
            return content
        return ""
        
    except Exception as e:
        # 如果本次超时，标记 Jina 不可达，避免后续重试
        err_str = str(e)
        if "timeout" in err_str.lower() or "timed out" in err_str.lower():
            global _jina_reachable
            _jina_reachable = False
            logger.info(f"[Jina Reader] 超时，本次会话不再尝试 Jina: {url[:50]}")
        else:
            logger.debug(f"[Jina Reader] 抓取失败: {url[:50]} - {e}")
        return ""


def _search_jina(query: str, max_results: int = 3) -> List[Document]:
    """
    Jina Reader 方案：
    1. 用必应搜索获取候选链接
    2. 用 Jina Reader 逐个抓取正文内容
    3. 返回清洗后的高质量正文
    """
    docs = []
    
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # 1. 必应搜索获取链接
        legal_query = f"{query} 法律法规"
        bing_url = f"https://www.bing.com/search?q={quote_plus(legal_query)}&setlang=zh-CN&cc=CN"
        resp = requests.get(bing_url, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("#b_results li.b_algo")
        if not results:
            results = soup.select(".b_algo")
        
        links = []
        for item in results[:max_results * 3]:
            link_el = item.select_one("h2 a, h3 a")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if href.startswith("http") and "microsoft.com" not in href:
                if not any(x in href.lower() for x in ["ad.", "click.", "track."]):
                    links.append(href)
        
        logger.info(f"[Jina Reader] 获取 {len(links)} 个候选链接")
        
        # 2. Jina Reader 抓取正文
        for url in links[:max_results]:
            content = _jina_fetch_content(url)
            
            if content and len(content) > 200:
                # 主题过滤
                if _is_legal_relevant(content):
                    # 提取标题（从 URL 或内容第一行）
                    title = url.split("/")[-1][:50] or "Jina Reader 内容"
                    
                    doc = Document(
                        page_content=content[:PLAYWRIGHT_MAX_CONTENT],
                        metadata={
                            "source": f"Jina Reader - {title[:40]}",
                            "url": url,
                            "from_web": True,
                            "web_source": "jina_reader",
                        },
                    )
                    docs.append(doc)
                    logger.info(f"[Jina Reader] 成功抓取: {title[:40]} ({len(content)} 字符)")
        
    except Exception as e:
        logger.warning(f"[Jina Reader] 检索失败: {e}")
    
    if docs:
        logger.info(f"[Jina Reader] 检索到 {len(docs)} 条结果: {query[:30]}")
    else:
        logger.info(f"[Jina Reader] 未检索到有效结果: {query[:30]}")
    
    return docs


# ── Crawl4AI 抓取（开源网页爬虫）───────────────────────────────────────────────

def _crawl4ai_fetch_content(url: str) -> str:
    """
    轻量级网页正文抓取：使用 requests + html.parser（Python 内置）提取正文。
    优先抓取 <article>/<main>/<div class=content> 等主要内容区域。

    如需更强的 JS 渲染支持，可改用自部署 Crawl4AI 服务：
      docker run -p 8000:8000 codemanjai/crawl4ai:latest
      然后替换下方实现为: requests.post("http://localhost:8000/api/v1/markup", ...)
    """
    try:
        import requests
        from html.parser import HTMLParser

        class _TextExtractor(HTMLParser):
            """从 HTML 提取纯文本，跳过 script/style/nav/footer 标签"""
            _SKIP = {"script", "style", "nav", "footer", "head", "noscript"}

            def __init__(self):
                super().__init__()
                self._skip_depth = 0
                self.texts: list = []

            def handle_starttag(self, tag, attrs):
                if tag in self._SKIP:
                    self._skip_depth += 1

            def handle_endtag(self, tag):
                if tag in self._SKIP and self._skip_depth > 0:
                    self._skip_depth -= 1

            def handle_data(self, data):
                if self._skip_depth == 0:
                    text = data.strip()
                    if len(text) > 10:
                        self.texts.append(text)

        headers = _get_headers()
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        resp.encoding = resp.apparent_encoding or "utf-8"
        html_text = resp.text

        parser = _TextExtractor()
        parser.feed(html_text)
        content = "\n".join(parser.texts)
        # 截取前 3000 字，避免噪音太多
        return content[:3000].strip()

    except Exception as e:
        logger.debug(f"[Crawl4AI] 抓取失败: {url[:50]} - {e}")
        return ""


def _search_crawl4ai(query: str, max_results: int = 2) -> List[Document]:
    """
    轻量级通用抓取方案：
    1. 先用必应搜索获取候选 URL
    2. 对每个 URL 用 _crawl4ai_fetch_content 提取正文
    3. 过滤并返回有效内容
    """
    docs: List[Document] = []
    try:
        import requests

        # 必应搜索获取 URL 列表
        search_url = "https://cn.bing.com/search"
        params = {"q": query + " 法律", "count": max_results * 2}
        headers = _get_headers()
        resp = requests.get(search_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200:
            return []

        # 从结果页提取 URL（简单正则）
        import re
        urls = re.findall(r'<a href="(https?://[^"]+)"', resp.text)
        # 过滤掉必应自身链接
        urls = [u for u in urls if "bing.com" not in u and "microsoft.com" not in u][:max_results * 2]

        fetched = 0
        for url in urls:
            if fetched >= max_results:
                break
            content = _crawl4ai_fetch_content(url)
            if not content or len(content) < 100:
                continue
            if not _is_legal_relevant(content):
                continue
            doc = Document(
                page_content=content,
                metadata={
                    "source": f"网络检索 - {url[:60]}",
                    "url": url,
                    "from_web": True,
                    "web_source": "crawl4ai",
                },
            )
            docs.append(doc)
            fetched += 1
            logger.info(f"[Crawl4AI] 成功抓取: {url[:60]} ({len(content)} 字符)")

    except Exception as e:
        logger.warning(f"[Crawl4AI] 搜索失败: {e}")

    if docs:
        logger.info(f"[Crawl4AI] 检索到 {len(docs)} 条结果: {query[:30]}")
    return docs


# ── Tavily 搜索（AI优化搜索）──────────────────────────────────────────────────

def _search_tavily(query: str, max_results: int = 3) -> List[Document]:
    """
    Tavily 搜索方案：
    Tavily 是专为 LLM 设计的 AI 搜索，会审查多个来源，返回最相关的内容。
    质量最高但需要 API Key（免费额度有限）。
    
    申请免费 API：https://tavily.com/
    """
    import os
    
    docs = []
    
    try:
        import requests
        
        # 从环境变量获取 Tavily API Key
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        
        if not tavily_api_key:
            logger.info(f"[Tavily] 未配置 API Key，跳过（可从 https://tavily.com/ 申请免费额度）")
            return []
        
        # Tavily Search API
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": tavily_api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }
        
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT * 2)
        resp.raise_for_status()
        
        results = resp.json().get("results", [])
        
        for item in results:
            content = item.get("content", "") or item.get("answer", "")
            title = item.get("title", "Tavily 内容")
            url_link = item.get("url", "")
            
            if content and len(content) > 50:
                if _is_legal_relevant(content):
                    doc = Document(
                        page_content=content[:PLAYWRIGHT_MAX_CONTENT],
                        metadata={
                            "source": f"Tavily - {title[:40]}",
                            "url": url_link,
                            "from_web": True,
                            "web_source": "tavily",
                        },
                    )
                    docs.append(doc)
        
        if docs:
            logger.info(f"[Tavily] 检索到 {len(docs)} 条结果: {query[:30]}")
        else:
            logger.info(f"[Tavily] 未检索到有效结果: {query[:30]}")
        
    except Exception as e:
        logger.warning(f"[Tavily] 检索失败: {e}")
    
    return docs


# ── 法律专业网站直接检索 ────────────────────────────────────────────────────────

def _search_legal_sites(query: str, max_results: int = 2) -> List[Document]:
    """
    直接检索法律专业网站（法信、律商网、无讼等），绕过搜索引擎直接获取高质量内容
    """
    docs = []
    
    # 法律专业网站搜索接口
    legal_sites = [
        {
            "name": "法信",
            "url": "https://www.faxin.cn/search?key={query}",
            "pattern": ".result-list li, .article-item, .law-item",
            "title_sel": "a, .title",
            "content_sel": ".abstract, p",
        },
        {
            "name": "无讼",
            "url": "https://www.itslaw.com/search?searchType=judgement&searchWord={query}",
            "pattern": ".result-item, .case-item",
            "title_sel": "a, .title",
            "content_sel": ".summary, p",
        },
        {
            "name": "律商网",
            "url": "https://www.lexisnexis.cn/search?term={query}",
            "pattern": ".search-result li, .result-item",
            "title_sel": "a, h3",
            "content_sel": ".snippet, p",
        },
    ]
    
    try:
        import requests
        from bs4 import BeautifulSoup
        
        for site in legal_sites:
            try:
                url = site["url"].format(query=quote_plus(query))
                resp = requests.get(url, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                
                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select(site["pattern"])[:max_results]
                
                for item in items:
                    title_el = item.select_one(site["title_sel"])
                    content_el = item.select_one(site["content_sel"])
                    
                    title = title_el.get_text(strip=True) if title_el else site["name"]
                    content = content_el.get_text(strip=True) if content_el else ""
                    
                    if content and len(content) > 30:
                        doc = Document(
                            page_content=content,
                            metadata={
                                "source": f"{site['name']} - {title[:40]}",
                                "url": url,
                                "from_web": True,
                                "web_source": f"legal_site_{site['name']}",
                            },
                        )
                        docs.append(doc)
                        
                logger.info(f"[{site['name']}] 检索到 {len(items)} 条结果")
                
            except Exception as e:
                logger.debug(f"[{site['name']}] 检索失败: {e}")
                continue
                
    except Exception as e:
        logger.warning(f"[法律专业网站] 检索失败: {e}")
    
    return docs


# ── 联网检索主入口 ────────────────────────────────────────────────────────────

class WebSearcher:
    """
    联网检索调度器 v2

    优先级：OpenLaw → 北大法宝 → Playwright 深层抓取 → 必应兜底
    每个来源独立失败不影响其他来源。
    """

    def should_trigger(
        self,
        kb_results: List[Tuple[Document, float]],
        force_enable: bool = False,
    ) -> Tuple[bool, str]:
        if force_enable:
            return True, "用户手动开启联网检索"

        if not kb_results:
            return True, "知识库无检索结果"

        max_score = max(score for _, score in kb_results)
        if max_score < WEB_SEARCH_THRESHOLD:
            return True, f"知识库最高相似度 {max_score:.2f} < 阈值 {WEB_SEARCH_THRESHOLD}"

        if len(kb_results) < WEB_SEARCH_MIN_DOCS:
            return True, f"知识库结果数量 {len(kb_results)} < 最低要求 {WEB_SEARCH_MIN_DOCS}"

        return False, ""

    def search(self, query: str) -> List[Document]:
        """
        执行联网检索，返回去重后的文档列表。
        顺序（按质量优先级）：
          1. Tavily（AI优化搜索，质量最高，需API Key）
          2. Jina Reader（LLM优化抓取，免费开源）
          3. OpenLaw（法条精准）
          4. 北大法宝（补充法规）
          5. 法律专业网站（法信、无讼、律商网）
          6. Crawl4AI 通用抓取（requests+内置html.parser，无需额外依赖）
          7. Playwright 深层抓取（从详情页提取正文）
          8. 必应兜底（广撒网）
        每个来源独立失败不影响其他来源。
        """
        docs: List[Document] = []

        # 1. Tavily（AI优化搜索，质量最高）
        tavily_docs = _search_tavily(query, max_results=3)
        docs.extend(tavily_docs)

        # 2. Jina Reader（LLM优化抓取，免费开源）
        if len(docs) < 2:
            jina_docs = _search_jina(query, max_results=3)
            docs.extend(jina_docs)

        # 3. OpenLaw（法条精准）
        if len(docs) < 2:
            openlaw_docs = _search_openlaw(query, max_results=3)
            docs.extend(openlaw_docs)

        # 4. 北大法宝（补充）
        if len(docs) < 2:
            pkulaw_docs = _search_pkulaw(query, max_results=2)
            docs.extend(pkulaw_docs)

        # 5. 法律专业网站（法信、无讼、律商网）
        if len(docs) < 2:
            legal_docs = _search_legal_sites(query, max_results=2)
            docs.extend(legal_docs)

        # 6. Crawl4AI 通用抓取（requests+内置解析，无外部依赖）
        if len(docs) < 2:
            crawl4ai_docs = _search_crawl4ai(query, max_results=2)
            docs.extend(crawl4ai_docs)

        # 7. Playwright 深层抓取（从详情页提取正文，信息密度较高）
        if len(docs) < 2:
            playwright_docs = _playwright_search_and_fetch(query, max_results=3)
            docs.extend(playwright_docs)

        # 8. 必应兜底（广撒网）
        if len(docs) < 2:
            bing_docs = _search_bing(query, max_results=3)
            docs.extend(bing_docs)

        # 去重（以内容前80字为key）
        seen = set()
        unique_docs = []
        for doc in docs:
            key = doc.page_content[:80]
            if key not in seen and len(doc.page_content.strip()) > 15:
                seen.add(key)
                unique_docs.append(doc)

        # 主题过滤：丢弃与法律无关的噪音内容
        legal_docs = [doc for doc in unique_docs if _is_legal_relevant(doc.page_content)]
        filtered_count = len(unique_docs) - len(legal_docs)
        if filtered_count:
            logger.info(f"[主题过滤] 丢弃 {filtered_count} 条非法律内容（query: {query[:40]}）")

        # Playwright 详情页内容优先排在前面（信息密度更高）
        playwright_first = [d for d in legal_docs if d.metadata.get("web_source") == "playwright"]
        others = [d for d in legal_docs if d.metadata.get("web_source") != "playwright"]
        sorted_docs = playwright_first + others

        logger.info(f"联网检索合计返回 {len(sorted_docs)} 条文档（query: {query[:40]}）")
        return sorted_docs[:WEB_MAX_RESULTS]


# 全局单例
web_searcher = WebSearcher()
