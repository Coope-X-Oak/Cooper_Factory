import asyncio
from .ai_client import ai_client
from .prompt_manager import prompt_manager

async def analyze_content(text: str, bvid: str = ""):
    print(f"   [AI Core] 正在调用引擎: {ai_client.provider.upper()}...")
    print(f"   [AI Debug] 输入文本长度: {len(text)}")

    # 提取字幕内容用于专门分析
    subtitle_content = _extract_subtitle_from_text(text)

    # 第一步：生成字幕大纲（如果有字幕的话）
    subtitle_outline = ""
    if subtitle_content and not subtitle_content.startswith("("):
        print(f"   [AI Core] 发现字幕内容 ({len(subtitle_content)} 字符)，正在生成大纲...")
        subtitle_outline = await asyncio.to_thread(_generate_subtitle_outline, subtitle_content, bvid)
    else:
        print("   [AI Core] 未发现有效字幕内容，跳过大纲生成")
        subtitle_outline = "该视频暂无字幕内容，无法生成字幕大纲"

    # 第二步：生成核心摘要
    try:
        # 使用配置化的Prompt
        summary_prompt = prompt_manager.get_prompt(
            "video_summary",
            content=text[:3000]
        )

        # 获取输出配置
        summary_config = prompt_manager.get_output_config("video_summary")

        summary = await asyncio.to_thread(
            _generate_summary,
            summary_prompt,
            **summary_config
        )
        return {
            'summary': summary,
            'subtitleOutline': subtitle_outline
        }
    except Exception as e:
        print(f"   [AI Error] 调用失败: {e}")
        return {
            'summary': 'AI分析失败',
            'subtitleOutline': subtitle_outline or '字幕大纲生成失败'
        }



def _extract_subtitle_from_text(text: str) -> str:
    """从完整文本中提取字幕内容"""
    try:
        # 查找字幕部分
        if "【视频字幕(Core)】:" in text:
            subtitle_part = text.split("【视频字幕(Core)】:\n")[-1]
            # 如果有其他分隔符，截取到下一个分隔符
            for separator in ["------------------------------", "【"]:
                if separator in subtitle_part:
                    subtitle_part = subtitle_part.split(separator)[0]
                    break
            return subtitle_part.strip()
        return ""
    except:
        return ""

def _generate_subtitle_outline(subtitle_text: str, bvid: str = "") -> str:
    """专门生成字幕大纲的函数，返回树状文本结构"""
    if not subtitle_text or len(subtitle_text.strip()) < 50:
        return "字幕内容过短，无法生成有意义的大纲"

    # 获取字幕时间戳数据（如果可用）
    from app.services.subtitle_service import CURRENT_SUBTITLE_DATA
    timestamp_info = ""
    if CURRENT_SUBTITLE_DATA and len(CURRENT_SUBTITLE_DATA) > 0:
        # 选择几个关键时间点作为示例
        sample_timestamps = CURRENT_SUBTITLE_DATA[:15]  # 增加到15个时间点
        timestamp_examples = []
        for item in sample_timestamps:
            time_seconds = int(item.get('time', 0))
            time_str = item.get('time_str', '00:00')
            content = item.get('content', '')[:40]  # 内容前40字符
            if content:
                timestamp_examples.append(f"{time_str} ({time_seconds}s): {content}")

        if timestamp_examples:
            timestamp_info = f"""

时间戳信息（用于生成跳转链接）：
{chr(10).join(timestamp_examples)}

请在合适的位置添加时间戳链接，格式为 [时间点](https://www.bilibili.com/video/{bvid}?t=秒数)
例如：[02:30](https://www.bilibili.com/video/{bvid}?t=150)"""

    try:
        # 使用配置化的Prompt
        outline_prompt = prompt_manager.get_prompt(
            "subtitle_outline",
            subtitle_content=subtitle_text[:4000],
            timestamp_info=timestamp_info
        )

        # 获取输出配置
        outline_config = prompt_manager.get_output_config("subtitle_outline")

        # 使用统一的AI客户端生成大纲
        if ai_client.is_available():
            outline = ai_client.call_ai(
                outline_prompt,
                **outline_config
            )
            # 本地处理：将时间戳转换为HTML链接
            outline = _convert_timestamps_to_links(outline, bvid)
            return outline
        else:
            # 如果AI不可用，提供基础分析
            return _generate_basic_outline(subtitle_text)
    except Exception as e:
        print(f"   [AI Outline] 生成失败: {e}")
        return _generate_basic_outline(subtitle_text)

def _convert_timestamps_to_links(outline: str, bvid: str) -> str:
    """将纯文本时间戳转换为HTML链接"""
    if not bvid:
        return outline

    import re

    # 正则表达式匹配 [时间:时间] 格式
    timestamp_pattern = r'\[(\d{1,2}):(\d{2})\]'

    def replace_timestamp(match):
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        total_seconds = minutes * 60 + seconds
        time_str = match.group(0)  # 保持原格式 [02:30]

        # 生成HTML链接
        url = f"https://www.bilibili.com/video/{bvid}?t={total_seconds}"
        return f'<a href="{url}" target="_blank">{time_str[1:-1]}</a>'  # 移除[]只保留时间

    # 替换所有时间戳
    converted_outline = re.sub(timestamp_pattern, replace_timestamp, outline)

    return converted_outline

def _generate_summary(prompt: str, max_tokens: int = 300, temperature: float = 0.3, **kwargs) -> str:
    """生成视频内容的核心摘要"""
    try:
        # 使用统一的AI客户端生成摘要
        if ai_client.is_available():
            return ai_client.call_ai(prompt, max_tokens=max_tokens, temperature=temperature)
        else:
            return "AI服务不可用，无法生成摘要"
    except Exception as e:
        print(f"   [AI Summary] 生成失败: {e}")
        return "AI生成摘要失败"

def _generate_basic_outline(subtitle_text: str) -> str:
    """基础字幕大纲生成（当AI不可用时）"""
    # 简单的文本分析和结构化
    sentences = [s.strip() for s in subtitle_text.split('。') if s.strip()][:5]

    outline = "📋 视频字幕大纲\n"
    for i, sentence in enumerate(sentences, 1):
        if len(sentence) > 10:
            outline += f"├── 🎯 核心观点{i}: {sentence[:50]}{'...' if len(sentence) > 50 else ''}\n"

    return outline

def _clean_json(text):
    print(f"   [AI Debug] 原始AI响应: {text[:200]}...")
    text = text.replace('```json', '').replace('```', '').strip()
    try:
        parsed = json.loads(text)
        print(f"   [AI Debug] 成功解析JSON，包含字段: {list(parsed.keys()) if isinstance(parsed, dict) else '非字典类型'}")
        return parsed
    except json.JSONDecodeError:
        print(f"   [AI Warning] 返回了非 JSON 格式: {text[:50]}...")
        return {}

# ==========================================
#   独立诊断入口 (Diagnostic Runner)
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("🏥 Cooper 工厂 AI 模块诊断程序")
    print("=" * 50)

    # 1. 环境检查
    print(f"⚙️ 当前引擎: {ai_client.provider.upper()}")
    print(f"✅ AI服务可用: {ai_client.is_available()}")

    # 2. 连通性测试
    if ai_client.is_available():
        print("\n📡 正在尝试连接 AI 服务...")
        try:
            test_response = ai_client.call_ai("Hello, just testing connection.", max_tokens=10)
            print("✅ 连接成功！AI 回复:", test_response[:50])
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("💡 建议：检查API密钥配置或网络连接")
    else:
        print("\n❌ AI服务不可用：请检查 .env 配置或安装依赖 (pip install openai google-generativeai)")
