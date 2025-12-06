"""
Prompt管理器：实现Prompt配置文件化和加载逻辑
支持YAML格式的Prompt配置，实现配置即代码和业务逻辑分离
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from string import Template


class PromptManager:
    """Prompt配置管理器"""

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        初始化Prompt管理器

        Args:
            prompts_dir: Prompt配置文件目录，默认使用当前文件所在目录的prompts文件夹
        """
        if prompts_dir is None:
            current_dir = Path(__file__).parent
            prompts_dir = current_dir / "prompts"

        self.prompts_dir = Path(prompts_dir)
        self.prompts: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, Template] = {}

        # 自动加载所有Prompt配置
        self._load_all_prompts()

    def _load_all_prompts(self):
        """加载所有YAML格式的Prompt配置文件"""
        if not self.prompts_dir.exists():
            print(f"⚠️  Prompt目录不存在: {self.prompts_dir}")
            return

        yaml_files = list(self.prompts_dir.glob("*.yaml"))
        if not yaml_files:
            print(f"⚠️  未找到YAML配置文件在: {self.prompts_dir}")
            return

        for yaml_file in yaml_files:
            try:
                self._load_prompt_config(yaml_file)
                print(f"✅ 已加载Prompt配置: {yaml_file.name}")
            except Exception as e:
                print(f"❌ 加载Prompt配置失败 {yaml_file.name}: {e}")

    def _load_prompt_config(self, config_file: Path):
        """加载单个Prompt配置文件"""
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        prompt_name = config.get('name')
        if not prompt_name:
            raise ValueError(f"Prompt配置文件 {config_file.name} 缺少 'name' 字段")

        # 存储配置
        self.prompts[prompt_name] = config

        # 预编译模板
        template_str = config.get('template', '')
        self.templates[prompt_name] = Template(template_str)

    def get_prompt(self, name: str, **variables) -> str:
        """
        获取格式化后的Prompt

        Args:
            name: Prompt名称
            **variables: 模板变量

        Returns:
            格式化后的Prompt字符串

        Raises:
            KeyError: Prompt不存在
            ValueError: 必需变量缺失或变量超出长度限制
        """
        if name not in self.prompts:
            available = list(self.prompts.keys())
            raise KeyError(f"Prompt '{name}' 不存在。可用Prompt: {available}")

        config = self.prompts[name]
        template = self.templates[name]

        # 验证必需变量
        required_vars = []
        for var_config in config.get('variables', []):
            if var_config.get('required', False):
                required_vars.append(var_config['name'])

        missing_vars = set(required_vars) - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Prompt '{name}' 缺少必需变量: {missing_vars}")

        # 验证变量长度
        for var_config in config.get('variables', []):
            var_name = var_config['name']
            max_length = var_config.get('max_length')

            if var_name in variables and max_length:
                var_value = variables[var_name]
                if isinstance(var_value, str) and len(var_value) > max_length:
                    # 自动截断超长变量
                    variables[var_name] = var_value[:max_length]
                    print(f"⚠️  变量 '{var_name}' 超出最大长度 {max_length}，已自动截断")

        # 格式化模板
        try:
            return template.substitute(**variables)
        except KeyError as e:
            raise ValueError(f"Prompt '{name}' 模板缺少变量: {e}")

    def get_prompt_config(self, name: str) -> Dict[str, Any]:
        """
        获取Prompt的完整配置信息

        Args:
            name: Prompt名称

        Returns:
            Prompt配置字典
        """
        if name not in self.prompts:
            raise KeyError(f"Prompt '{name}' 不存在")
        return self.prompts[name].copy()

    def get_output_config(self, name: str) -> Dict[str, Any]:
        """
        获取Prompt的输出配置（用于AI调用参数）

        Args:
            name: Prompt名称

        Returns:
            输出配置字典，包含format, max_tokens, temperature等
        """
        config = self.get_prompt_config(name)
        return config.get('output', {})

    def list_prompts(self) -> Dict[str, str]:
        """
        列出所有可用的Prompt

        Returns:
            Prompt名称到描述的映射
        """
        return {
            name: config.get('description', '无描述')
            for name, config in self.prompts.items()
        }

    def reload_prompts(self):
        """重新加载所有Prompt配置"""
        self.prompts.clear()
        self.templates.clear()
        self._load_all_prompts()
        print(f"🔄 已重新加载 {len(self.prompts)} 个Prompt配置")


# 全局Prompt管理器实例
prompt_manager = PromptManager()


if __name__ == "__main__":
    print("=" * 50)
    print("🎭 Cooper Factory Prompt管理器测试")
    print("=" * 50)

    # 显示加载的Prompt
    available = prompt_manager.list_prompts()
    print(f"📋 已加载Prompt: {len(available)} 个")
    for name, desc in available.items():
        print(f"  • {name}: {desc}")

    print("\n🧪 测试Prompt格式化...")

    # 测试摘要Prompt
    try:
        summary_prompt = prompt_manager.get_prompt(
            "video_summary",
            content="这是一个测试视频内容，包含很多重要信息..."
        )
        print("✅ 摘要Prompt格式化成功")
        print(f"📝 Prompt预览: {summary_prompt[:100]}...")

        # 获取输出配置
        output_config = prompt_manager.get_output_config("video_summary")
        print(f"⚙️  输出配置: {output_config}")

    except Exception as e:
        print(f"❌ 摘要Prompt测试失败: {e}")

    # 测试大纲Prompt
    try:
        outline_prompt = prompt_manager.get_prompt(
            "subtitle_outline",
            subtitle_content="这是字幕内容...",
            timestamp_info="\n时间戳信息..."
        )
        print("✅ 大纲Prompt格式化成功")
        print(f"📝 Prompt预览: {outline_prompt[:100]}...")

    except Exception as e:
        print(f"❌ 大纲Prompt测试失败: {e}")
