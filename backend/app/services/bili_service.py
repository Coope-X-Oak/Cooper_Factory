"""
简化的B站数据采集服务
专注于核心功能：视频元数据、字幕、弹幕采集
"""

import httpx
import json
import asyncio
import re
from pathlib import Path

# 导入依赖
from .cookie_manager import cookie_manager
from .subtitle_service import subtitle_service

# 尝试导入日志管理器
try:
    from main import log_print
except ImportError:
    def log_print(message: str, level: str = "info", end: str = "\n"):
        print(message, end=end)

# ============ 简化的HTTP配置 ============
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



# ============ 全局变量 ============
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

async def fetch_video_data(bvid: str):
    if bvid == "BV1MockTest":
        return _mock_data()

    log_print(f"🚀 [System] 启动混合采集引擎: {bvid}", "info")

    # 1. 并行执行：API 采集基础信息 + 浏览器采集字幕 + 弹幕采集
    #    (Playwright 和弹幕都启动较慢，尽早开始)
    log_print("📡 启动并行数据采集任务...", "info")
    task_meta = _fetch_metadata_via_api(bvid)
    task_subtitle = subtitle_service.fetch(bvid)
    task_danmaku = _fetch_danmaku_via_api(bvid)  # 新增弹幕采集

    # 等待结果
    try:
        results = await asyncio.gather(task_meta, task_subtitle, task_danmaku)
        meta_data, subtitle_text, danmaku_text = results
        log_print("✅ 所有采集任务完成", "info")
    except Exception as e:
        log_print(f"❌ 采集流程异常: {e}", "error")
        raise e

    # 2. 解包数据
    info, tags_str, hot_comments = meta_data

    # 3. 组装标准元数据
    meta = {
        "title": info["title"],
        "uploader": info["owner"]["name"],
        "duration": _format_duration(info["duration"]),
        "cover": info["pic"]
    }

    # 4. 组装终极情报文本
    raw_text = f"【视频标题】: {meta['title']}\n"
    raw_text += f"【UP主】: {meta['uploader']}\n"
    raw_text += f"【所属分区】: {info.get('tname', '未知')}\n"
    raw_text += f"【核心标签】: {tags_str}\n"
    raw_text += "-" * 30 + "\n"
    raw_text += f"【视频简介】:\n{info.get('desc', '（无简介）')}\n"
    raw_text += "-" * 30 + "\n"
    raw_text += f"【精选热评】:\n{hot_comments}\n"
    raw_text += "-" * 30 + "\n"
    raw_text += f"【弹幕舆情】:\n{danmaku_text}\n"
    raw_text += "-" * 30 + "\n"
    # Cooper: 这里就是你梦寐以求的字幕 - 不再截断完整字幕
    raw_text += f"【视频字幕(Core)】:\n{subtitle_text}"

    # 存档所有数据
    _save_archive(bvid, raw_text, subtitle_text, danmaku_text, meta_data)

    return meta, raw_text

# --- 模块 A: 原生 API 快速采集 (HTTPX) ---

async def _fetch_metadata_via_api(bvid):
    """使用轻量级 API 获取除了字幕以外的所有信息"""
    log_print("🔍 [API] 正在获取元数据、标签、热评...", "info")
    async with HttpClient.get_async_client() as client:
        # 基础信息
        url_view = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        resp_view = await client.get(url_view)
        if resp_view.status_code != 200: raise Exception("B站 View 接口请求失败")
        info = resp_view.json()['data']
        aid = info['aid']
        
        # 标签 & 热评 (并行)
        t_tags = client.get(f"https://api.bilibili.com/x/tag/archive/tags?bvid={bvid}")
        t_reply = client.get(f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3")
        
        r_tags, r_reply = await asyncio.gather(t_tags, t_reply, return_exceptions=True)
        
        # 处理标签
        tags_str = "(无标签)"
        if not isinstance(r_tags, Exception) and r_tags.json()['code'] == 0:
            tags_str = ", ".join([t['tag_name'] for t in r_tags.json()['data']])
            
        # 处理热评
        comments_str = "(暂无热评)"
        if not isinstance(r_reply, Exception) and r_reply.json()['code'] == 0:
            replies = r_reply.json()['data'].get('replies', [])
            if replies:
                c_list = []
                for i, r in enumerate(replies[:5]):
                    msg = r['content']['message'].replace('\n', ' ')
                    c_list.append(f"{i+1}. {msg}")
                comments_str = "\n".join(c_list)
                
        return info, tags_str, comments_str

# --- 模块 B: 弹幕采集 (API) ---

async def _fetch_danmaku_via_api(bvid):
    """通过 B站 API 获取弹幕数据"""
    log_print("💬 [Danmaku] 正在获取弹幕舆情...", "info")

    try:
        # 1. 获取视频信息和CID
        info = await _get_video_info_async(bvid)
        if not info:
            return "(无法获取视频信息，无法获取弹幕)"

        aid = info['aid']
        cid = await _get_cid_async(bvid, aid)
        if not cid:
            return "(未找到视频 CID，无法获取弹幕)"

        # 2. 下载弹幕 XML
        xml_url = f"https://comment.bilibili.com/{cid}.xml"
        async_client = HttpClient.get_async_client()
        async with async_client as client:
            resp = await client.get(xml_url)
            if resp.status_code != 200:
                return f"(弹幕下载失败: HTTP {resp.status_code})"

            # 自动识别编码
            if resp.encoding is None:
                resp.encoding = 'utf-8'
            xml_content = resp.text

        # 3. 正则解析弹幕
        danmaku_list = re.findall(r'<d p=".*?">(.*?)</d>', xml_content)

        if not danmaku_list:
            return "(该视频暂无弹幕)"

        log_print(f"✅ [Danmaku] 成功捕获 {len(danmaku_list)} 条弹幕", "info")

        # 4. 数据处理：取前 500 条，拼接成文本
        selected_danmaku = danmaku_list[:500]
        return " | ".join(selected_danmaku)

    except Exception as e:
        log_print(f"❌ [Danmaku] 获取失败: {e}", "error")
        return f"(弹幕系统故障: {str(e)})"

async def _get_video_info_async(bvid: str):
    """异步获取视频信息"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    async_client = HttpClient.get_async_client()
    async with async_client as client:
        resp = await client.get(url)
        if resp.status_code == 200 and resp.json()['code'] == 0:
            return resp.json()['data']
    return None

async def _get_cid_async(bvid: str, aid: str) -> str:
    """异步获取CID"""
    url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&aid={aid}"
    async_client = HttpClient.get_async_client()
    async with async_client as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data['code'] == 0 and data['data']:
                return data['data'][0]['cid']
    return None

# 已重构：字幕获取逻辑已迁移到 subtitle_service.py

# --- 辅助工具 ---

def _format_duration(seconds):
    if not seconds: return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def _save_archive(bvid, full_text, subtitle_text, danmaku_text, meta_data):
    """保存所有采集到的数据到 data 目录"""
    try:
        print(f"   [Archive Debug] DATA_DIR路径: {DATA_DIR}")
        print(f"   [Archive Debug] DATA_DIR存在: {DATA_DIR.exists()}")
        print(f"   [Archive Debug] DATA_DIR绝对路径: {DATA_DIR.absolute()}")

        # 确保目录存在
        DATA_DIR.mkdir(exist_ok=True)

        saved_files = []

        # 1. 保存完整情报文本
        full_intel_path = DATA_DIR / f"{bvid}_full_intel.txt"
        with open(full_intel_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        saved_files.append("full_intel.txt")
        print(f"   [Archive] ✅ 保存完整情报文本: {full_intel_path}")

        # 2. 保存字幕内容
        if subtitle_text and not subtitle_text.startswith("(") and not subtitle_text.strip().startswith("⚠️"):
            subtitle_path = DATA_DIR / f"{bvid}_subtitle.txt"
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(subtitle_text)
            saved_files.append("subtitle.txt")
            print(f"   [Archive] ✅ 保存字幕内容: {subtitle_path} (长度: {len(subtitle_text)} 字符)")
        else:
            print("   [Archive] ⚠️  跳过字幕保存: 字幕内容无效、为空或为帮助信息")

        # 3. 保存弹幕内容
        if danmaku_text and not danmaku_text.startswith("("):
            danmaku_path = DATA_DIR / f"{bvid}_danmaku.txt"
            with open(danmaku_path, "w", encoding="utf-8") as f:
                f.write(danmaku_text)
            saved_files.append("danmaku.txt")
            print(f"   [Archive] ✅ 保存弹幕内容: {danmaku_path} (长度: {len(danmaku_text)} 字符)")
        else:
            print("   [Archive] ⚠️  跳过弹幕保存: 弹幕内容无效或为空")

        # 4. 保存元数据 JSON
        metadata_path = DATA_DIR / f"{bvid}_metadata.json"
        info, tags_str, hot_comments = meta_data
        metadata = {
            "bvid": bvid,
            "title": info.get("title", ""),
            "uploader": info.get("owner", {}).get("name", ""),
            "duration": info.get("duration", 0),
            "description": info.get("desc", ""),
            "tags": tags_str,
            "hot_comments": hot_comments,
            "tname": info.get("tname", ""),
            "pic": info.get("pic", ""),
            "aid": info.get("aid", ""),
            "view": info.get("stat", {}).get("view", 0),
            "danmaku": info.get("stat", {}).get("danmaku", 0),
            "reply": info.get("stat", {}).get("reply", 0),
            "favorite": info.get("stat", {}).get("favorite", 0),
            "coin": info.get("stat", {}).get("coin", 0),
            "share": info.get("stat", {}).get("share", 0),
            "like": info.get("stat", {}).get("like", 0)
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        saved_files.append("metadata.json")
        print(f"   [Archive] ✅ 保存元数据JSON: {metadata_path}")

        print(f"   [Archive] 🎉 数据存档完成: {bvid} ({', '.join(saved_files)})")

    except Exception as e:
        print(f"   [Archive] ❌ 存档失败: {e}")
        import traceback
        traceback.print_exc()

def _mock_data():
    return {"title": "Mock", "uploader": "System", "duration": "00:00", "cover": ""}, "Mock Data"

# --- 独立测试入口 ---
if __name__ == "__main__":
    import sys
    # 默认测试那个没简介的 BV1dQSCBgENY
    test_id = "BV1dQSCBgENY"
    if len(sys.argv) > 1: test_id = sys.argv[1]

    print("="*50)
    print("🧪 Cooper 工厂爬虫 v6.0 (Cookie Support + Subtitle)")
    print(f"🎯 目标: {test_id}")
    print(f"🍪 Cookie 状态: {'✅ 已启用' if cookie_manager.is_enabled() else '❌ 未启用'}")
    if cookie_manager.is_enabled():
        print(f"   Cookie 数量: {len(cookie_manager.get_cookies())} 个")
    else:
        print("   💡 提示: 如需获取受限字幕，请在项目根目录创建 cookies.txt 文件")
    print("="*50)

    async def debug_test():
        print("\n[DEBUG] 开始分步测试...")

        # 测试 1: 元数据采集
        print("\n1️⃣ 测试元数据采集...")
        try:
            meta_data = await _fetch_metadata_via_api(test_id)
            info, tags_str, hot_comments = meta_data
            print("✅ 元数据采集成功")
            print(f"   标题: {info.get('title', 'N/A')}")
            print(f"   UP主: {info.get('owner', {}).get('name', 'N/A')}")
            print(f"   标签: {tags_str}")
            print(f"   简介: {info.get('desc', 'N/A')[:50]}...")
        except Exception as e:
            print(f"❌ 元数据采集失败: {e}")
            return

        # 测试 2: 字幕采集
        print("\n2️⃣ 测试字幕采集...")
        try:
            subtitle_text = await subtitle_service.fetch(test_id)
            print("✅ 字幕采集完成")
            print(f"   字幕长度: {len(subtitle_text)} 字符")
            if subtitle_text.startswith("("):
                print(f"   ⚠️  字幕状态: {subtitle_text}")
            else:
                print(f"   📝 字幕预览: {subtitle_text[:200]}...")
        except Exception as e:
            print(f"❌ 字幕采集失败: {e}")
            import traceback
            traceback.print_exc()
            return

        # 测试 3: 弹幕采集
        print("\n3️⃣ 测试弹幕采集...")
        try:
            danmaku_text = await _fetch_danmaku_via_api(test_id)
            print("✅ 弹幕采集完成")
            print(f"   弹幕长度: {len(danmaku_text)} 字符")
            if danmaku_text.startswith("("):
                print(f"   ⚠️  弹幕状态: {danmaku_text}")
            else:
                print(f"   💬 弹幕预览: {danmaku_text[:200]}...")
        except Exception as e:
            print(f"❌ 弹幕采集失败: {e}")
            return

        # 测试 4: 完整流程
        print("\n4️⃣ 测试完整流程...")
        try:
            meta, text = await fetch_video_data(test_id)
            print("✅ 完整流程成功")
            print(f"   总文本长度: {len(text)} 字符")

            # 检查各部分
            if "【视频字幕(Core)】:" in text:
                subtitle_part = text.split("【视频字幕(Core)】:\n")[-1][:500]
                print(f"   📝 字幕部分预览: {subtitle_part}...")
                if subtitle_part.strip().startswith("("):
                    print("   ⚠️  字幕可能未成功提取")
                else:
                    print("   ✅ 字幕部分正常")
            else:
                print("   ⚠️  未找到字幕部分")

            if "【弹幕舆情】:" in text:
                danmaku_part = text.split("【弹幕舆情】:\n")[-1].split("\n---")[0][:200]
                print(f"   💬 弹幕部分预览: {danmaku_part}...")
                if danmaku_part.strip().startswith("("):
                    print("   ⚠️  弹幕可能未成功提取")
                else:
                    print("   ✅ 弹幕部分正常")

        except Exception as e:
            print(f"❌ 完整流程失败: {e}")
            import traceback
            traceback.print_exc()

    try:
        asyncio.run(debug_test())
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        import traceback
        traceback.print_exc()
