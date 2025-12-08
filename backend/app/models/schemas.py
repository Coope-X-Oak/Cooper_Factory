from pydantic import BaseModel
from typing import List, Optional

class VideoMeta(BaseModel):
    title: str = "未知标题"
    uploader: str = "未知UP主"
    duration: str = "00:00"
    cover: str = ""

class RawData(BaseModel):
    """原始采集数据"""
    subtitle: str = ""  # 字幕内容
    danmaku: str = ""   # 弹幕内容
    comments: str = ""  # 评论内容

class AnalysisResult(BaseModel):
    meta: VideoMeta
    rawData: RawData = RawData()  # 原始数据
    summary: str = "AI 未生成摘要"
    subtitleOutline: str = "AI 未生成字幕大纲"

# 新增：独立分析结果模型
class ContentAnalysis(BaseModel):
    """内容分析结果"""
    type: str  # "subtitle", "danmaku", "comments"
    content: str
    analysis: str
    status: str = "completed"  # "pending", "processing", "completed", "error"
