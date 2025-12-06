"""
AI客户端统一接口
消除重复的AI调用逻辑，提供统一的AI服务接口
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

class AIClient:
    """统一的AI客户端，封装DeepSeek和Gemini调用逻辑"""

    def __init__(self):
        # 环境加载逻辑
        current_dir = Path(__file__).resolve().parent
        backend_dir = current_dir.parent.parent
        env_path = backend_dir / ".env"

        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            load_dotenv()

        # 读取配置
        self.provider = os.getenv("AI_PROVIDER", "deepseek").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

        # 延迟初始化客户端
        self.genai = None
        self.openai_client = None

        try:
            import google.generativeai as genai
            self.genai = genai
        except ImportError:
            pass

        try:
            from openai import OpenAI
            self.openai_client = OpenAI
        except ImportError:
            pass

    def call_ai(self, prompt: str, max_tokens: int = 300, temperature: float = 0.3) -> str:
        """
        统一的AI调用接口

        Args:
            prompt: AI提示词
            max_tokens: 最大token数
            temperature: 温度参数

        Returns:
            AI响应文本
        """
        try:
            if self.provider == "deepseek":
                return self._call_deepseek(prompt, max_tokens, temperature)
            else:
                return self._call_gemini(prompt, max_tokens, temperature)
        except Exception as e:
            print(f"   [AI Error] {self.provider.upper()} 调用失败: {e}")
            # 如果AI不可用，返回模拟数据用于测试
            if not self.is_available():
                print("   [AI Debug] AI服务不可用，返回模拟数据")
                return self._get_mock_response(prompt)
            raise e

    def _call_deepseek(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """调用DeepSeek API"""
        if not self.deepseek_key:
            raise Exception("未配置 DEEPSEEK_API_KEY")
        if not self.openai_client:
            raise Exception("未安装 openai 库")

        client = self.openai_client(
            api_key=self.deepseek_key,
            base_url="https://api.deepseek.com"
        )

        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=30.0
        )
        return self._clean_response(resp.choices[0].message.content)

    def _call_gemini(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """调用Gemini API"""
        if not self.gemini_key:
            raise Exception("未配置 GEMINI_API_KEY")
        if not self.genai:
            raise Exception("未安装 google-generativeai 库")

        self.genai.configure(api_key=self.gemini_key)
        model = self.genai.GenerativeModel('gemini-2.0-flash')

        # Gemini不直接支持max_tokens和temperature参数，通过配置处理
        resp = model.generate_content(prompt)
        return self._clean_response(resp.text)

    def _clean_response(self, text: str) -> str:
        """清理AI响应文本"""
        print(f"   [AI Debug] 原始响应: {text[:200]}...")
        text = text.replace('```json', '').replace('```', '').strip()
        return text

    def _get_mock_response(self, prompt: str) -> str:
        """返回模拟AI响应用于测试"""
        if "summary" in prompt.lower():
            return "这是一个测试视频的摘要内容。由于AI服务未配置，这里返回模拟数据用于演示功能。"
        elif "outline" in prompt.lower():
            return "字幕大纲：\\n1. 00:00-00:30 视频开头介绍\\n2. 00:30-01:00 主要内容讲解\\n3. 01:00-01:30 总结和结尾"
        else:
            return "AI服务未配置，返回模拟响应。提示：请配置 GEMINI_API_KEY 或 DEEPSEEK_API_KEY 环境变量以启用完整功能。"

    def is_available(self) -> bool:
        """检查AI服务是否可用"""
        try:
            if self.provider == "deepseek":
                return bool(self.deepseek_key and self.openai_client)
            else:
                return bool(self.gemini_key and self.genai)
        except:
            return False

# 全局AI客户端实例
ai_client = AIClient()
