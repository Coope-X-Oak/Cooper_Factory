"""
Cookie管理器
统一处理Cookie加载、验证和管理逻辑
"""
import os
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

class CookieManager:
    """Cookie管理器，负责加载和验证Cookie"""

    def __init__(self, cookie_file: Optional[Path] = None):
        self.cookie_file = cookie_file or Path(__file__).parent.parent.parent / "cookies.txt"
        self.cookies: Dict[str, str] = {}
        self.enabled = False
        self._load_cookies()

    def _load_cookies(self) -> None:
        """加载Cookie文件或环境变量"""
        # 加载环境变量文件
        current_dir = Path(__file__).resolve().parent
        backend_dir = current_dir.parent.parent
        env_path = backend_dir / ".env"

        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            load_dotenv()

        # 首先尝试从环境变量加载
        env_cookies = os.getenv("BILI_COOKIES", "").strip()
        if env_cookies:
            try:
                # 环境变量格式：SESSDATA=xxx; bili_jct=yyy; ...
                cookies = {}
                for cookie_pair in env_cookies.split(';'):
                    if '=' in cookie_pair:
                        name, value = cookie_pair.strip().split('=', 1)
                        cookies[name.strip()] = value.strip()

                if cookies:
                    self.cookies = cookies
                    self.enabled = True
                    print(f"   [Cookie] ✅ 已从环境变量加载 {len(cookies)} 个 Cookie 项")
                    print("   [Cookie] ⚠️  注意：使用 Cookie 可能违反 B站服务条款，请谨慎使用")
                    return
            except Exception as e:
                print(f"   [Cookie] ❌ 环境变量 Cookie 解析失败: {e}")

        # 如果环境变量没有，尝试从文件加载
        if not self.cookie_file.exists():
            print("   [Cookie] ℹ️  未找到 cookies.txt 文件且无环境变量，使用无 Cookie 模式")
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
                print(f"   [Cookie] ✅ 已从文件加载 {len(cookies)} 个 Cookie 项")
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
