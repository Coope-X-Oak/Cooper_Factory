from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.services.bili_service import fetch_video_data
from app.services.ai_service import analyze_content
from app.models.schemas import AnalysisResult
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

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(static_dir, 'index.html')
    if not os.path.exists(index_path):
        return {"error": "UI Missing", "path": index_path}
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
        # Step 1: 采集
        print("📊 开始数据采集阶段...")
        t1 = time.time()
        meta, raw_text = await fetch_video_data(bvid)
        fetch_time = time.time() - t1
        print(f"✅ [1/2] 数据采集完成 (耗时: {fetch_time:.2f}s) - {meta.get('title')}")

        # Step 2: 分析
        print("🤖 开始AI分析阶段...")
        t2 = time.time()
        ai_result = await analyze_content(raw_text, bvid)
        ai_time = time.time() - t2
        print(f"✅ [2/2] AI 研判完成 (耗时: {ai_time:.2f}s)")

        # 合并元数据
        final_meta = ai_result.get("meta")
        if not final_meta or not final_meta.get("title"):
            ai_result["meta"] = meta

        total_time = time.time() - start_time
        print(f"🎉 >>> 任务闭环完成 (总耗时: {total_time:.2f}s)")

        return ai_result

    except Exception as e:
        print(f"❌ 系统异常: {e}")
        # 返回 500 但带有错误详情，避免前端瞎猜
        raise HTTPException(status_code=500, detail=f"Factory Error: {str(e)}")

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
