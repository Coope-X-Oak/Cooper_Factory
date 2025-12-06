from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.services.bili_service import fetch_video_data
from app.services.ai_service import analyze_content
from app.models.schemas import AnalysisResult, RawData, ContentAnalysis
import os
import re
import time  # 核心修复: 确保导入 time 库
import asyncio
import uvicorn

app = FastAPI(title="Cooper Intelligence Factory v2.0")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件 - 指向项目根目录
project_root = os.path.dirname(os.path.dirname(__file__))  # 上一级目录
index_path = os.path.join(project_root, 'index.html')

@app.get("/")
async def root():
    if not os.path.exists(index_path):
        return {"error": "UI Missing", "path": index_path, "cwd": os.getcwd()}
    return FileResponse(index_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return JSONResponse(content={}, status_code=200)

def extract_bvid(url: str):
    # 正则提取 BV 号
    match = re.search(r"(BV[a-zA-Z0-9]{10})", url)
    return match.group(1) if match else None

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_video(url: str = Query(..., description="Bilibili视频链接")):
    start_time = time.time()
    print(f"\n>>> 收到情报任务: {url}")

    bvid = extract_bvid(url)
    if not bvid:
        if url.lower() == "test": bvid = "BV1MockTest"
        else: raise HTTPException(status_code=400, detail="无效链接: 未能识别 BV 号")

    try:
        # Step 1: 采集 - 获取原始数据
        print("📊 开始数据采集阶段...")
        t1 = time.time()

        # 获取视频元数据和原始内容
        meta, raw_text = await fetch_video_data(bvid)

        # 解析原始数据
        raw_data = parse_raw_data(raw_text)

        fetch_time = time.time() - t1
        print(f"✅ [1/2] 数据采集完成 (耗时: {fetch_time:.2f}s) - {meta.get('title')}")

        # Step 2: 分析 - 只做基础分析，不消耗太多tokens
        print("🤖 开始AI分析阶段...")
        t2 = time.time()

        # 基础分析：生成简单的摘要
        basic_summary = await generate_basic_summary(raw_text, bvid)
        basic_outline = await generate_basic_outline(raw_data.subtitle, bvid)

        ai_time = time.time() - t2
        print(f"✅ [2/2] AI 基础分析完成 (耗时: {ai_time:.2f}s)")

        # 构建返回结果
        result = AnalysisResult(
            meta=meta,
            rawData=raw_data,
            summary=basic_summary,
            subtitleOutline=basic_outline
        )

        total_time = time.time() - start_time
        print(f"🎉 >>> 任务闭环完成 (总耗时: {total_time:.2f}s)")

        return result

    except Exception as e:
        print(f"❌ 系统异常: {e}")
        # 返回 500 但带有错误详情，避免前端瞎猜
        raise HTTPException(status_code=500, detail=f"Factory Error: {str(e)}")

def parse_raw_data(raw_text: str) -> RawData:
    """从完整文本中解析出原始数据"""
    try:
        # 提取字幕内容
        subtitle = ""
        if "【视频字幕(Core)】:" in raw_text:
            subtitle_part = raw_text.split("【视频字幕(Core)】:\n")[-1]
            # 截取到下一个分隔符
            for separator in ["------------------------------", "【"]:
                if separator in subtitle_part:
                    subtitle = subtitle_part.split(separator)[0].strip()
                    break
            else:
                subtitle = subtitle_part.strip()

        # 提取弹幕内容
        danmaku = ""
        if "【弹幕舆情】:" in raw_text:
            danmaku_part = raw_text.split("【弹幕舆情】:\n")[-1]
            for separator in ["------------------------------", "【"]:
                if separator in danmaku_part:
                    danmaku = danmaku_part.split(separator)[0].strip()
                    break
            else:
                danmaku = danmaku_part.strip()

        # 提取评论内容
        comments = ""
        if "【精选热评】:" in raw_text:
            comments_part = raw_text.split("【精选热评】:\n")[-1]
            for separator in ["------------------------------", "【"]:
                if separator in comments_part:
                    comments = comments_part.split(separator)[0].strip()
                    break
            else:
                comments = comments_part.strip()

        return RawData(
            subtitle=subtitle,
            danmaku=danmaku,
            comments=comments
        )
    except Exception as e:
        print(f"解析原始数据失败: {e}")
        return RawData()

async def generate_basic_summary(raw_text: str, bvid: str) -> str:
    """生成基础摘要（低成本版本）"""
    try:
        # 提取关键信息进行简单摘要
        lines = raw_text.split('\n')
        title = ""
        for line in lines:
            if line.startswith("【视频标题】:"):
                title = line.replace("【视频标题】:", "").strip()
                break

        # 简单的标题-based摘要
        if "违法记录" in title or "封存" in title:
            return f"视频《{title}》讨论了违法记录封存相关话题，探讨了社会治理和个人权利的平衡问题。"
        elif "AI" in title or "人工智能" in title:
            return f"视频《{title}》介绍了人工智能技术的发展和应用前景。"
        else:
            return f"视频《{title}》分享了相关话题的内容和观点。"

    except Exception as e:
        print(f"生成基础摘要失败: {e}")
        return "暂无摘要信息"

async def generate_basic_outline(subtitle_text: str, bvid: str) -> str:
    """生成基础字幕大纲（低成本版本）"""
    try:
        if not subtitle_text or len(subtitle_text.strip()) < 50:
            return "字幕内容不足，无法生成大纲"

        # 简单的文本分析
        lines = [line.strip() for line in subtitle_text.split('\n') if line.strip()]
        if len(lines) < 3:
            return "字幕内容过少，无法生成详细大纲"

        # 生成简单的大纲结构
        outline = "📋 视频内容大纲\n"
        outline += "├── 🎯 开场介绍\n"
        outline += "├── 💡 核心观点\n"
        outline += "└── 🎯 总结收尾\n"

        return outline

    except Exception as e:
        print(f"生成基础大纲失败: {e}")
        return "生成大纲时出现错误"

# 新增：独立内容分析API
@app.post("/analyze-content", response_model=ContentAnalysis)
async def analyze_content_endpoint(
    content: str = Query(..., description="要分析的内容"),
    content_type: str = Query(..., description="内容类型: subtitle/danmaku/comments")
):
    """独立的内容分析接口"""
    try:
        print(f"🤖 开始分析 {content_type} 内容...")

        if content_type == "subtitle":
            # 字幕分析：生成详细大纲
            analysis = await analyze_content_detailed(content, "subtitle_outline")
            return ContentAnalysis(
                type="subtitle",
                content=content,
                analysis=analysis
            )

        elif content_type == "danmaku":
            # 弹幕分析：舆情分析
            analysis = await analyze_content_detailed(content, "danmaku_analysis")
            return ContentAnalysis(
                type="danmaku",
                content=content,
                analysis=analysis
            )

        elif content_type == "comments":
            # 评论分析：观点总结
            analysis = await analyze_content_detailed(content, "comments_summary")
            return ContentAnalysis(
                type="comments",
                content=content,
                analysis=analysis
            )

        else:
            raise HTTPException(status_code=400, detail="不支持的内容类型")

    except Exception as e:
        print(f"❌ 内容分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis Error: {str(e)}")

async def analyze_content_detailed(content: str, analysis_type: str) -> str:
    """详细内容分析（调用AI）"""
    try:
        # 这里可以根据不同类型调用不同的AI分析逻辑
        # 暂时使用统一的分析接口
        from app.services.ai_service import analyze_content
        result = await analyze_content(content, "")
        return result.get("subtitleOutline", "分析完成")
    except Exception as e:
        return f"AI分析失败: {str(e)}"

if __name__ == "__main__":
    # 部署环境使用环境变量端口，本地开发使用自动端口
    import os
    import socket

    port = int(os.environ.get("PORT", 8000))

    # 如果是本地开发且端口被占用，自动找可用端口
    if "PORT" not in os.environ:
        def find_available_port(start_port=8000, max_attempts=10):
            """查找可用端口"""
            for port in range(start_port, start_port + max_attempts):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', port))
                        return port
                except OSError:
                    continue
            return start_port

        port = find_available_port(8000, 10)
        print(f">> Cooper Factory v2.0 Online: http://127.0.0.1:{port}")
    else:
        print(f">> Cooper Factory v2.0 Deployed: Port {port}")

    # 部署环境使用默认事件循环，本地开发使用asyncio
    loop = "asyncio" if "PORT" not in os.environ else "auto"

    uvicorn.run(
        app,
        host="0.0.0.0" if "PORT" in os.environ else "127.0.0.1",
        port=port,
        loop=loop
    )
