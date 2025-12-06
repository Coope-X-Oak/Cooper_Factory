"""
字幕获取服务：专注、高稳定性的字幕数据采集
支持多策略获取、自动重试、错误分类处理
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

# ============ 错误分类 ============

class SubtitleError(Exception):
    """字幕获取基础异常"""
    pass

class NetworkError(SubtitleError):
    """网络相关错误"""
    pass

class ApiError(SubtitleError):
    """API相关错误"""
    pass

class PermissionError(SubtitleError):
    """权限相关错误"""
    pass

class DataError(SubtitleError):
    """数据解析错误"""
    pass

# ============ HTTP客户端 ============

class HttpClient:
    """简化的HTTP客户端管理"""
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/"
    }

    @staticmethod
    def get_client(use_cookies=False):
        """获取配置好的客户端"""
        headers = HttpClient.HEADERS.copy()
        if use_cookies and cookie_manager.is_enabled():
            if cookie_header := cookie_manager.get_cookie_header():
                headers['Cookie'] = cookie_header

        return httpx.Client(
            headers=headers,
            timeout=15.0,
            follow_redirects=True,
            verify=False
        )

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

# ============ 获取策略基类 ============

class SubtitleStrategy:
    """字幕获取策略基类"""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority

    async def fetch(self, bvid: str) -> SubtitleResult:
        """获取字幕的抽象方法"""
        raise NotImplementedError

    def _is_valid_result(self, content: str) -> bool:
        """检查获取结果是否有效"""
        if not content:
            return False
        # 检查是否是错误信息（以括号开头）
        if content.strip().startswith("(") or content.strip().startswith("⚠️"):
            return False
        # 检查内容长度
        return len(content.strip()) > 10

# ============ API策略 ============

class ApiSubtitleStrategy(SubtitleStrategy):
    """无Cookie API字幕获取策略"""

    def __init__(self):
        super().__init__("API", priority=1)

    async def fetch(self, bvid: str) -> SubtitleResult:
        """使用API获取字幕（无Cookie）"""
        try:
            log_print(f"🌐 [Subtitle-API] 正在使用API策略获取字幕: {bvid}", "info")

            # 获取视频信息和CID
            info = await self._get_video_info_async(bvid)
            if not info:
                return SubtitleResult("", self.name, False, "无法获取视频信息")

            aid = info['aid']
            cid = await self._get_cid_async(bvid, aid)
            if not cid:
                return SubtitleResult("", self.name, False, "无法获取分P信息")

            # 获取字幕URL
            subtitle_url = await self._get_subtitle_url_async(bvid, cid)
            if not subtitle_url:
                return SubtitleResult("", self.name, False, "该视频没有字幕")

            # 下载字幕
            content = await self._download_subtitle_async(subtitle_url, bvid)
            if self._is_valid_result(content):
                log_print("✅ [Subtitle-API] API策略成功获取字幕", "info")
                return SubtitleResult(content, self.name, True)
            else:
                return SubtitleResult("", self.name, False, "字幕内容无效")

        except NetworkError as e:
            log_print(f"❌ [Subtitle-API] 网络错误: {e}", "error")
            return SubtitleResult("", self.name, False, f"网络错误: {e}")
        except ApiError as e:
            log_print(f"❌ [Subtitle-API] API错误: {e}", "error")
            return SubtitleResult("", self.name, False, f"API错误: {e}")
        except Exception as e:
            log_print(f"❌ [Subtitle-API] 未知错误: {e}", "error")
            return SubtitleResult("", self.name, False, f"未知错误: {e}")

    async def _get_video_info_async(self, bvid: str):
        """异步获取视频信息"""
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        async with HttpClient.get_async_client() as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.json()['code'] == 0:
                    return resp.json()['data']
                else:
                    raise ApiError(f"API响应错误: {resp.status_code}")
            except httpx.TimeoutException:
                raise NetworkError("请求超时")
            except httpx.ConnectError:
                raise NetworkError("连接失败")

    async def _get_cid_async(self, bvid: str, aid: str) -> Optional[str]:
        """异步获取CID"""
        url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&aid={aid}"
        async with HttpClient.get_async_client() as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data['code'] == 0 and data['data']:
                        return data['data'][0]['cid']
                raise ApiError("CID获取失败")
            except httpx.TimeoutException:
                raise NetworkError("CID请求超时")

    async def _get_subtitle_url_async(self, bvid: str, cid: str) -> Optional[str]:
        """异步获取字幕URL"""
        url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
        headers = HttpClient.HEADERS.copy()
        headers['Referer'] = f"https://www.bilibili.com/video/{bvid}"

        async with HttpClient.get_async_client() as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    raise ApiError(f"字幕URL请求失败: {resp.status_code}")

                data = resp.json()
                if data['code'] != 0:
                    raise ApiError(f"API返回错误: {data['code']}")

                subtitles = data['data'].get('subtitle', {}).get('subtitles', [])
                if not subtitles:
                    return None

                # 优先选择人工中文字幕
                for sub in subtitles:
                    if sub.get('ai_type', 1) == 0:  # 人工字幕
                        lan_doc = sub.get('lan_doc', '').lower()
                        if any(kw in lan_doc for kw in ['中', 'zh', 'chinese']):
                            return sub.get('subtitle_url')

                # 备选：任何人工字幕
                for sub in subtitles:
                    if sub.get('ai_type', 1) == 0:
                        return sub.get('subtitle_url')

                # 最后：第一个可用字幕
                return subtitles[0].get('subtitle_url') if subtitles else None

            except httpx.TimeoutException:
                raise NetworkError("字幕URL请求超时")

    async def _download_subtitle_async(self, subtitle_url: str, bvid: str) -> str:
        """异步下载并解析字幕"""
        if subtitle_url.startswith('//'):
            subtitle_url = 'https:' + subtitle_url

        headers = HttpClient.HEADERS.copy()
        headers['Referer'] = f"https://www.bilibili.com/video/{bvid}"

        async with HttpClient.get_async_client() as client:
            try:
                resp = await client.get(subtitle_url, headers=headers)
                if resp.status_code != 200:
                    raise ApiError(f"字幕下载失败: {resp.status_code}")

                data = resp.json()
                body = data.get('body', [])
                if not body:
                    raise DataError("字幕内容为空")

                # 提取字幕文本，包含时间戳前缀
                subtitle_lines = []
                for item in body:
                    content = item.get('content', '').strip()
                    if content:
                        # 格式化时间戳为最短格式 [MM:SS] 或 [H:MM:SS]
                        time_seconds = item.get('from', 0)
                        if time_seconds >= 3600:  # 超过1小时
                            time_str = f"{int(time_seconds)//3600}:{int(time_seconds)%3600//60:02d}:{int(time_seconds)%60:02d}"
                        else:  # MM:SS格式
                            time_str = f"{int(time_seconds)//60:02d}:{int(time_seconds)%60:02d}"
                        subtitle_lines.append(f"[{time_str}] {content}")

                if not subtitle_lines:
                    raise DataError("字幕内容为空")

                # 保存时间戳数据到全局变量
                global CURRENT_SUBTITLE_DATA
                CURRENT_SUBTITLE_DATA = [
                    {
                        'time': item.get('from', 0),
                        'time_str': f"{int(item.get('from', 0))//60:02d}:{int(item.get('from', 0))%60:02d}",
                        'content': item.get('content', '').strip()
                    }
                    for item in body if item.get('content', '').strip()
                ]

                # 使用换行符连接，保持段落结构
                result = '\n'.join(subtitle_lines)
                log_print(f"   [Subtitle-API] ✅ 成功提取字幕，{len(subtitle_lines)} 行，长度: {len(result)} 字符")
                return result

            except httpx.TimeoutException:
                raise NetworkError("字幕下载超时")

# ============ Cookie策略 ============

class CookieSubtitleStrategy(SubtitleStrategy):
    """Cookie增强字幕获取策略"""

    def __init__(self):
        super().__init__("Cookie", priority=2)

    async def fetch(self, bvid: str) -> SubtitleResult:
        """使用Cookie获取字幕"""
        if not cookie_manager.is_enabled():
            return SubtitleResult("", self.name, False, "Cookie未启用")

        try:
            log_print(f"🍪 [Subtitle-Cookie] 正在使用Cookie策略获取字幕: {bvid}", "info")

            # 使用同步方式获取（因为现有SubtitleFetcher是同步的）
            fetcher = SubtitleFetcher(use_cookies=True)
            content = await asyncio.to_thread(fetcher.fetch, bvid)

            if self._is_valid_result(content):
                log_print("✅ [Subtitle-Cookie] Cookie策略成功获取字幕", "info")
                return SubtitleResult(content, self.name, True)
            else:
                return SubtitleResult("", self.name, False, "Cookie策略未能获取有效字幕")

        except Exception as e:
            log_print(f"❌ [Subtitle-Cookie] Cookie策略失败: {e}", "error")
            return SubtitleResult("", self.name, False, f"Cookie策略错误: {e}")

# ============ 浏览器策略（预留） ============

class BrowserSubtitleStrategy(SubtitleStrategy):
    """浏览器自动化字幕获取策略（预留接口）"""

    def __init__(self):
        super().__init__("Browser", priority=3)

    async def fetch(self, bvid: str) -> SubtitleResult:
        """浏览器自动化获取字幕（待实现）"""
        # TODO: 实现Playwright浏览器自动化获取
        log_print(f"🔧 [Subtitle-Browser] 浏览器策略暂未实现: {bvid}", "warning")
        return SubtitleResult("", self.name, False, "浏览器策略暂未实现")

# ============ 缓存策略 ============

class CacheSubtitleStrategy(SubtitleStrategy):
    """字幕缓存策略"""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_hours: int = 0.5):  # 30分钟缓存
        super().__init__("Cache", priority=4)
        self.cache_dir = cache_dir or (Path(__file__).parent.parent.parent / "data" / "subtitle_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours

    async def fetch(self, bvid: str) -> SubtitleResult:
        """从缓存获取字幕"""
        try:
            cache_file = self.cache_dir / f"{bvid}_subtitle.json"

            if not cache_file.exists():
                return SubtitleResult("", self.name, False, "缓存不存在")

            if not self._is_cache_valid(cache_file):
                log_print(f"🗑️ [Subtitle-Cache] 缓存已过期: {bvid}", "info")
                return SubtitleResult("", self.name, False, "缓存已过期")

            # 加载缓存
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            content = cache_data.get('content', '')
            if self._is_valid_result(content):
                log_print(f"✅ [Subtitle-Cache] 从缓存成功获取字幕: {bvid}", "info")
                return SubtitleResult(
                    content,
                    self.name,
                    True,
                    metadata={'cached_at': cache_data.get('timestamp')}
                )
            else:
                return SubtitleResult("", self.name, False, "缓存内容无效")

        except Exception as e:
            log_print(f"❌ [Subtitle-Cache] 缓存读取失败: {e}", "error")
            return SubtitleResult("", self.name, False, f"缓存错误: {e}")

    def _is_cache_valid(self, cache_file: Path) -> bool:
        """检查缓存是否有效"""
        try:
            stat = cache_file.stat()
            import time
            age_hours = (time.time() - stat.st_mtime) / 3600
            return age_hours < self.ttl_hours
        except:
            return False

# ============ 兼容性类 ============

class SubtitleFetcher:
    """兼容现有代码的字幕获取器"""

    def __init__(self, use_cookies=False):
        self.use_cookies = use_cookies
        self.client = HttpClient.get_client(use_cookies)

    def fetch(self, bvid: str) -> str:
        """同步获取字幕（兼容现有代码）"""
        try:
            # 获取视频信息和CID
            info = self._get_video_info(bvid)
            if not info:
                return "(无法获取视频信息)"

            aid = info['aid']
            cid = self._get_cid(bvid, aid)
            if not cid:
                return "(无法获取分P信息)"

            # 获取字幕
            subtitle_url = self._get_subtitle_url(bvid, cid)
            if not subtitle_url:
                return "(该视频没有字幕)"

            return self._download_subtitle(subtitle_url, bvid)

        except Exception as e:
            print(f"   [Subtitle] 提取异常: {e}")
            return f"(字幕提取异常: {str(e)})"

    def _get_video_info(self, bvid: str):
        """获取视频信息"""
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        resp = self.client.get(url)
        if resp.status_code == 200 and resp.json()['code'] == 0:
            return resp.json()['data']
        return None

    def _get_cid(self, bvid: str, aid: str) -> str:
        """获取CID"""
        url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&aid={aid}"
        resp = self.client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data['code'] == 0 and data['data']:
                return data['data'][0]['cid']
        return None

    def _get_subtitle_url(self, bvid: str, cid: str) -> str:
        """获取字幕URL"""
        url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
        headers = self.client.headers.copy()
        headers['Referer'] = f"https://www.bilibili.com/video/{bvid}"

        resp = self.client.get(url, headers=headers)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data['code'] != 0:
            return None

        subtitles = data['data'].get('subtitle', {}).get('subtitles', [])
        if not subtitles:
            return None

        # DEBUG: 打印所有可用字幕信息
        print(f"   [Subtitle] 可用字幕列表 ({len(subtitles)} 个):")
        for i, sub in enumerate(subtitles):
            ai_type = sub.get('ai_type', 1)
            lan = sub.get('lan', '')
            lan_doc = sub.get('lan_doc', '')
            url_sub = sub.get('subtitle_url', '')
            print(f"     [{i}] ai_type={ai_type}, lan='{lan}', lan_doc='{lan_doc}', url='{url_sub[:50]}...'")

        # 统一字幕选择逻辑：优先选择人工中文字幕，保持与异步版本一致
        selected_url = self._select_best_subtitle_url(subtitles)
        if selected_url:
            print(f"   [Subtitle] 选择字幕: {selected_url[:50]}...")
        return selected_url

    def _select_best_subtitle_url(self, subtitles: List[Dict[str, Any]]) -> Optional[str]:
        """选择最佳字幕URL的统一逻辑 - 只选择人工字幕，且URL不为空"""
        if not subtitles:
            return None

        # 过滤掉URL为空的字幕
        valid_subtitles = [s for s in subtitles if s.get('subtitle_url', '').strip()]

        if not valid_subtitles:
            return None  # 无有效字幕

        # 优先选择人工中文字幕
        for sub in valid_subtitles:
            if sub.get('ai_type', 1) == 0:  # 人工字幕
                lan_doc = sub.get('lan_doc', '').lower()
                if any(kw in lan_doc for kw in ['中', 'zh', 'chinese']):
                    return sub.get('subtitle_url')

        # 备选：任何人工字幕
        for sub in valid_subtitles:
            if sub.get('ai_type', 1) == 0:
                return sub.get('subtitle_url')

        # 不选择AI字幕，返回None表示无可用字幕
        return None

    def _download_subtitle(self, subtitle_url: str, bvid: str) -> str:
        """下载并解析字幕"""
        if subtitle_url.startswith('//'):
            subtitle_url = 'https:' + subtitle_url

        headers = self.client.headers.copy()
        headers['Referer'] = f"https://www.bilibili.com/video/{bvid}"

        resp = self.client.get(subtitle_url, headers=headers)
        if resp.status_code != 200:
            return f"(字幕下载失败: {resp.status_code})"

        data = resp.json()
        body = data.get('body', [])
        if not body:
            return "(字幕内容为空)"

        # 提取字幕文本，包含时间戳前缀 - 保留段落结构
        subtitle_lines = []
        for item in body:
            content = item.get('content', '').strip()
            if content:
                # 格式化时间戳为最短格式 [MM:SS] 或 [H:MM:SS]
                time_seconds = item.get('from', 0)
                if time_seconds >= 3600:  # 超过1小时
                    time_str = f"{int(time_seconds)//3600}:{int(time_seconds)%3600//60:02d}:{int(time_seconds)%60:02d}"
                else:  # MM:SS格式
                    time_str = f"{int(time_seconds)//60:02d}:{int(time_seconds)%60:02d}"
                subtitle_lines.append(f"[{time_str}] {content}")

        if not subtitle_lines:
            return "(字幕内容为空)"

        # 保存时间戳数据到全局变量
        global CURRENT_SUBTITLE_DATA
        CURRENT_SUBTITLE_DATA = [
            {
                'time': item.get('from', 0),
                'time_str': f"{int(item.get('from', 0))//60:02d}:{int(item.get('from', 0))%60:02d}",
                'content': item.get('content', '').strip()
            }
            for item in body if item.get('content', '').strip()
        ]

        # 使用换行符连接，保持段落结构
        result = '\n'.join(subtitle_lines)
        print(f"   [Subtitle] ✅ 成功提取字幕，{len(subtitle_lines)} 行，长度: {len(result)} 字符")
        return result

# ============ 全局变量 ============

CURRENT_SUBTITLE_DATA = []

# ============ 主服务类 ============

class SubtitleService:
    """字幕获取主服务"""

    def __init__(self):
        """初始化字幕服务"""
        self.strategies = [
            ApiSubtitleStrategy(),      # 优先：API策略
            CookieSubtitleStrategy(),   # 备选：Cookie策略
            BrowserSubtitleStrategy(),  # 兜底：浏览器策略（预留）
            CacheSubtitleStrategy()     # 缓存：历史数据
        ]
        # 按优先级排序
        self.strategies.sort(key=lambda s: s.priority)

    async def fetch(self, bvid: str) -> str:
        """
        多策略获取字幕

        Args:
            bvid: B站视频BV号

        Returns:
            字幕内容字符串，失败时返回错误信息
        """
        log_print(f"🎬 [SubtitleService] 开始获取字幕: {bvid}", "info")

        # 尝试各个策略
        for strategy in self.strategies:
            log_print(f"🔄 [SubtitleService] 尝试策略: {strategy.name}", "info")

            result = await strategy.fetch(bvid)

            if result.success and self._is_valid_result(result.content):
                log_print(f"✅ [SubtitleService] 策略 {strategy.name} 成功获取字幕", "info")

                # 缓存成功结果
                await self._cache_result(bvid, result)

                return result.content

            else:
                log_print(f"❌ [SubtitleService] 策略 {strategy.name} 失败: {result.error_message}", "warning")

        # 所有策略都失败，返回帮助信息
        help_message = self._generate_help_message(bvid)
        log_print(f"💥 [SubtitleService] 所有策略都失败，返回帮助信息", "error")
        return help_message

    def _is_valid_result(self, content: str) -> bool:
        """检查获取结果是否有效"""
        if not content:
            return False
        # 检查是否是错误信息（以括号开头）
        if content.strip().startswith("(") or content.strip().startswith("⚠️"):
            return False
        # 检查内容长度
        return len(content.strip()) > 10

    async def _cache_result(self, bvid: str, result: SubtitleResult):
        """缓存成功的结果"""
        try:
            cache_strategy = next((s for s in self.strategies if isinstance(s, CacheSubtitleStrategy)), None)
            if cache_strategy:
                import time
                cache_file = cache_strategy.cache_dir / f"{bvid}_subtitle.json"
                cache_data = {
                    'content': result.content,
                    'strategy': result.strategy,
                    'timestamp': time.time(),
                    'bvid': bvid
                }
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                log_print(f"💾 [SubtitleService] 已缓存字幕结果: {bvid}", "info")
        except Exception as e:
            log_print(f"❌ [SubtitleService] 缓存失败: {e}", "warning")

    def _generate_help_message(self, bvid: str) -> str:
        """生成字幕获取失败的帮助信息"""
        help_message = f"""
⚠️  字幕获取失败 - 该视频需要登录权限或暂无字幕

📋 获取Cookie步骤：
1️⃣ 浏览器访问并登录B站: https://www.bilibili.com/video/{bvid}
2️⃣ 按F12打开开发者工具 → 应用 → Cookies → bilibili.com
3️⃣ 复制以下关键Cookie值：
   • SESSDATA (必需 - 登录凭证)
   • bili_jct (必需 - CSRF令牌)
   • DedeUserID (可选 - 用户ID)
   • DedeUserID__ckMd5 (可选 - 用户ID校验)

4️⃣ 在项目根目录创建 cookies.txt 文件，格式：
.bilibili.com	TRUE	/	FALSE	1735689600	SESSDATA	[你的SESSDATA值]
.bilibili.com	TRUE	/	FALSE	1735689600	bili_jct	[你的bili_jct值]

5️⃣ 重新运行程序即可获取字幕

🔒 安全提醒：
• 请勿将Cookie文件分享给他人
• 定期更新Cookie以免过期失效
• Cookie包含个人登录信息，请妥善保管

💡 提示：Cookie模式可以获取需要登录才能访问的字幕内容
"""
        return help_message

# ============ 全局服务实例 ============

subtitle_service = SubtitleService()

# ============ 独立测试入口 ============

if __name__ == "__main__":
    print("=" * 60)
    print("🎬 Cooper Factory 字幕服务测试")
    print("=" * 60)

    # 测试配置
    test_bvid = "BV1dQSCBgENY"  # 默认测试视频

    async def test_subtitle_service():
        print(f"🎯 测试目标: {test_bvid}")
        print(f"🍪 Cookie状态: {'✅ 已启用' if cookie_manager.is_enabled() else '❌ 未启用'}")

        print("\n🧪 开始字幕获取测试...")

        try:
            result = await subtitle_service.fetch(test_bvid)

            if subtitle_service._is_valid_result(result):
                print("✅ 字幕获取成功！")
                print(f"📊 字幕长度: {len(result)} 字符")
                print(f"📝 字幕预览: {result[:200]}...")
            else:
                print("❌ 字幕获取失败")
                print(f"💬 错误信息: {result[:300]}...")

        except Exception as e:
            print(f"💥 测试异常: {e}")
            import traceback
            traceback.print_exc()

    try:
        asyncio.run(test_subtitle_service())
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        import traceback
        traceback.print_exc()
