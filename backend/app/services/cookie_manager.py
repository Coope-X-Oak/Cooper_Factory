"""
Cookie管理器
统一处理Cookie加载、验证和管理逻辑
"""
import os
from pathlib import Path
from typing import Dict, Optional

class CookieManager:
    """Cookie管理器，负责加载和验证Cookie"""

    def __init__(self, cookie_file: Optional[Path] = None):
        self.cookie_file = cookie_file or Path(__file__).parent.parent.parent / "cookies.txt"
        self.cookies: Dict[str, str] = {}
        self.enabled = False
        self._load_cookies()

    def _load_cookies(self) -> None:
        """加载Cookie文件"""
        if not self.cookie_file.exists():
            print("   [Cookie] ℹ️  未找到 cookies.txt 文件，使用无 Cookie 模式")
            return

        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                print("   [Cookie] ⚠️  Cookie 文件为空")
                return

            # 解析 Netscape 格式的 cookies
            cookies = {}
            lines = content.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain, flag, path, secure, expiration, name, value = parts[:7]
                        cookies[name] = value

            if cookies:
                self.cookies = cookies
                self.enabled = True
                print(f"   [Cookie] ✅ 已加载 {len(cookies)} 个 Cookie 项")
                print("   [Cookie] ⚠️  注意：使用 Cookie 可能违反 B站服务条款，请谨慎使用")
            else:
                print("   [Cookie] ⚠️  Cookie 文件存在但格式无效")

        except Exception as e:
            print(f"   [Cookie] ❌ Cookie 文件读取失败: {e}")

    def get_cookie_header(self) -> Optional[str]:
        """获取Cookie请求头字符串"""
        if not self.enabled or not self.cookies:
            return None
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def is_enabled(self) -> bool:
        """检查Cookie是否启用"""
        return self.enabled

    def get_cookies(self) -> Dict[str, str]:
        """获取所有Cookie"""
        return self.cookies.copy()

# 全局Cookie管理器实例
cookie_manager = CookieManager()
