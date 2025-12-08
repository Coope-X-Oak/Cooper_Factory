"""
字幕获取服务：高健壮性、多策略、自动重试
重构版：统一 HTTP 逻辑，支持多候选字幕遍历
"""

import asyncio
import httpx
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# 导入依赖
from .cookie_manager import cookie_manager

# 尝试导入日志管理器
try:
    from main import log_print
except ImportError:
    def log_print(message: str, level: str = "info", end: str = "\n"):
        print(message, end=end)

# ============ 数据结构 ============

@dataclass
class SubtitleResult:
    """字幕获取结果"""
    content: str
    strategy: str
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class SubtitleCandidate:
    """字幕候选源"""
    url: str
    ai_type: int  # 0: 人工, 1: AI
    lang: str
    lang_doc: str
    priority: int # 分数越高优先级越高

# ============ 错误定义 ============

class SubtitleError(Exception):
    pass

class NetworkError(SubtitleError):
    pass

class ApiError(SubtitleError):
    pass

# ============ HTTP客户端 ============

class HttpClient:
    """简化的HTTP客户端管理"""
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/"
    }

    @staticmethod
    def get_async_client(use_cookies=False):
        """获取异步客户端"""
        headers = HttpClient.HEADERS.copy()
        if use_cookies and cookie_manager.is_enabled():
            if cookie_header := cookie_manager.get_cookie_header():
                headers['Cookie'] = cookie_header

        return httpx.AsyncClient(
            headers=headers,
            timeout=15.0,
            follow_redirects=True,
            verify=False
        )

# ============ 策略基类 ============

class SubtitleStrategy:
    """字幕获取策略基类"""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority

    async def fetch(self, bvid: str) -> SubtitleResult:
        raise NotImplementedError

    def _is_valid_result(self, content: str) -> bool:
        """核心校验逻辑"""
        if not content: return False
        if content.strip().startswith("(") or content.strip().startswith("⚠️"): return False
        if len(content.strip()) < 50: return False  # 放宽限制，有些短视频字幕很少
        lines = [l for l in content.split('\n') if l.strip()]
        if len(lines) < 2: return False 
        
        # 必须包含时间戳
        if not re.search(r'\[\d{1,2}:\d{2}\]', content):
            return False
        return True

# ============ 统一 HTTP 策略 ============

class HttpSubtitleStrategy(SubtitleStrategy):
    """
    通用 HTTP 字幕获取策略
    实现了：Info -> CID -> Multi-Candidates -> Retry Loop 的完整流程
    """
    def __init__(self, name: str, priority: int, use_cookies: bool):
        super().__init__(name, priority)
        self.use_cookies = use_cookies

    async def fetch(self, bvid: str) -> SubtitleResult:
        try:
            log_print(f"🔄 [{self.name}] 开始获取流程: {bvid}", "info")
            
            # 1. 获取基本信息 & CID
            cid, title = await self._get_cid_and_title(bvid)
            if not cid:
                return SubtitleResult("", self.name, False, "无法获取CID")
            
            log_print(f"ℹ️ [{self.name}] Video: {title} (CID={cid})", "info")

            # 2. 获取所有可用字幕列表
            candidates = await self._get_candidates(bvid, cid)
            if not candidates:
                log_print(f"⚠️ [{self.name}] 未发现任何字幕源 (Response Data Checked)", "warning")
                return SubtitleResult("", self.name, False, "未发现任何字幕源")

            log_print(f"ℹ️ [{self.name}] 发现 {len(candidates)} 个字幕源，开始尝试...", "info")
            for c in candidates:
                log_print(f"   - {c.lang_doc} (AI={c.ai_type}) URL={c.url}", "info")

            # 3. 遍历尝试下载
            errors = []
            for idx, candidate in enumerate(candidates):
                log_print(f"   Trying [{idx+1}/{len(candidates)}] {candidate.lang_doc} ({'AI' if candidate.ai_type else 'Manual'})...", "info")
                
                try:
                    content = await self._download_subtitle(candidate.url, bvid)
                    if self._is_valid_result(content):
                        log_print(f"✅ [{self.name}] 成功获取字幕 ({candidate.lang_doc})", "info")
                        return SubtitleResult(
                            content, 
                            self.name, 
                            True, 
                            metadata={
                                'lang': candidate.lang, 
                                'is_ai': bool(candidate.ai_type)
                            }
                        )
                    else:
                        errors.append(f"{candidate.lang_doc}: 内容校验失败")
                except Exception as e:
                    errors.append(f"{candidate.lang_doc}: 下载异常 {str(e)}")
            
            # 所有候选都失败
            return SubtitleResult("", self.name, False, f"所有候选均失败: {'; '.join(errors)}")

        except Exception as e:
            return SubtitleResult("", self.name, False, f"流程异常: {str(e)}")

    async def _get_cid_and_title(self, bvid: str):
        """获取视频主要 CID 和 标题 (带重试)"""
        async with HttpClient.get_async_client(self.use_cookies) as client:
            for attempt in range(3):
                try:
                    # Log cookie status
                    has_cookie = 'Cookie' in client.headers
                    if attempt > 0:
                        log_print(f"🔄 [{self.name}] Retrying info fetch ({attempt+1}/3)...", "info")
                    else:
                        log_print(f"🔍 [{self.name}] Requesting View (Cookie={has_cookie})", "info")
                    
                    # 先获取 info 拿到 aid
                    view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
                    resp = await client.get(view_url)
                    
                    if resp.status_code != 200:
                        await asyncio.sleep(1)
                        continue
                        
                    data = resp.json()
                    if data['code'] != 0:
                        await asyncio.sleep(1)
                        continue
                    
                    # Srict Check: Ensure the returned BVID matches the requested one
                    resp_bvid = data['data'].get('bvid')
                    if resp_bvid != bvid:
                        log_print(f"⚠️ [{self.name}] BVID Mismatch! Req={bvid}, Got={resp_bvid}. Possible anti-bot redirect.", "warning")
                        await asyncio.sleep(1.5) # Wait a bit longer for redirect to clear
                        continue

                    aid = data['data']['aid']
                    title = data['data']['title']

                    # 再获取 pagelist 拿到 cid
                    page_url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&aid={aid}"
                    resp2 = await client.get(page_url)
                    if resp2.status_code == 200 and resp2.json()['code'] == 0:
                        pages = resp2.json()['data']
                        if pages: return pages[0]['cid'], title
                    
                    return None, title
                    
                except Exception as e:
                    log_print(f"❌ [{self.name}] 获取CID失败: {e}", "warning")
                    await asyncio.sleep(1)
            
            return None, None

    async def _get_candidates(self, bvid: str, cid: str) -> List[SubtitleCandidate]:
        """获取并排序字幕候选列表"""
        url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
        async with HttpClient.get_async_client(self.use_cookies) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200: return []
                data = resp.json()
                subtitles = data.get('data', {}).get('subtitle', {}).get('subtitles', [])
                
                candidates = []
                for sub in subtitles:
                    sub_url = sub.get('subtitle_url', '')
                    if not sub_url: continue
                    if sub_url.startswith('//'): sub_url = 'https:' + sub_url
                    
                    ai_type = sub.get('ai_type', 1)
                    lang_doc = sub.get('lan_doc', '未知')
                    
                    # 评分逻辑
                    score = 0
                    if ai_type == 0: score += 10 # 人工优先
                    if '中' in lang_doc or 'zh' in sub.get('lan', ''): score += 5 # 中文优先
                    
                    candidates.append(SubtitleCandidate(
                        url=sub_url,
                        ai_type=ai_type,
                        lang=sub.get('lan', ''),
                        lang_doc=lang_doc,
                        priority=score
                    ))
                
                # 按优先级降序排序
                candidates.sort(key=lambda x: x.priority, reverse=True)
                return candidates
                
            except Exception as e:
                log_print(f"❌ [{self.name}] 获取字幕列表失败: {e}", "warning")
                return []

    async def _download_subtitle(self, url: str, bvid: str) -> str:
        """下载并解析字幕"""
        async with HttpClient.get_async_client(self.use_cookies) as client:
            resp = await client.get(url)
            if resp.status_code != 200: raise NetworkError(f"HTTP {resp.status_code}")
            
            try:
                data = resp.json()
            except json.JSONDecodeError:
                # 有时候返回的不是 json? 暂时主要处理 json 失败情况
                raise ApiError("非 JSON 响应")
                
            body = data.get('body', [])
            if not body: raise ApiError("字幕内容为空")
            
            lines = []
            for item in body:
                content = item.get('content', '').strip()
                if not content: continue
                
                # 格式化时间戳
                secs = item.get('from', 0)
                if secs >= 3600:
                    t_str = f"{int(secs)//3600}:{int(secs)%3600//60:02d}:{int(secs)%60:02d}"
                else:
                    t_str = f"{int(secs)//60:02d}:{int(secs)%60:02d}"
                    
                lines.append(f"[{t_str}] {content}")
            
            return "\n".join(lines)

# ============ 具体实现类 ============

class ApiSubtitleStrategy(HttpSubtitleStrategy):
    """无 Cookie 策略"""
    def __init__(self):
        super().__init__("API", 1, False)

class CookieSubtitleStrategy(HttpSubtitleStrategy):
    """Cookie 增强策略"""
    def __init__(self):
        super().__init__("Cookie", 2, True)

    async def fetch(self, bvid: str) -> SubtitleResult:
        if not cookie_manager.is_enabled():
            return SubtitleResult("", self.name, False, "Cookie未启用")
        return await super().fetch(bvid)

# ============ 主服务类 ============

class SubtitleService:
    def __init__(self):
        self.strategies = [
            ApiSubtitleStrategy(),
            CookieSubtitleStrategy()
        ]
        
    async def fetch(self, bvid: str) -> str:
        log_print(f"🎬 [SubtitleService] 启动获取 ({bvid})", "info")
        
        last_error = ""
        
        for strategy in self.strategies:
            res = await strategy.fetch(bvid)
            if res.success:
                return res.content
            last_error = res.error_message
            
        # 全部失败
        return self._get_help_msg(bvid)

    def _get_help_msg(self, bvid: str) -> str:
        return f"⚠️ 字幕获取失败\n可能的解决方案：\n1. 视频确实无字幕\n2. 需要配置 Cookie (请查看 cookies.txt)"

subtitle_service = SubtitleService()

if __name__ == "__main__":
    # 测试入口
    import sys
    test_id = sys.argv[1] if len(sys.argv) > 1 else "BV1dQSCBgENY"
    
    async def main():
        print(f"Testing {test_id}...")
        res = await subtitle_service.fetch(test_id)
        print(f"\nResult Length: {len(res)}")
        print("Peek:\n" + res[:200])
        
    asyncio.run(main())
