from pydantic import BaseModel

class VideoMeta(BaseModel):
    title: str = "未知标题"
    uploader: str = "未知UP主"
    duration: str = "00:00"
    cover: str = ""

class AnalysisResult(BaseModel):
    meta: VideoMeta
    summary: str = "AI 未生成摘要"
    subtitleOutline: str = "AI 未生成字幕大纲"
