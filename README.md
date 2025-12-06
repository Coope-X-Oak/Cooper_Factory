# Cooper Intelligence Factory

一个基于AI的Bilibili视频智能分析系统，能够自动提取视频内容、生成摘要和大纲。

## 🚀 功能特性

- **智能视频分析**：自动获取B站视频信息和字幕内容
- **AI内容摘要**：使用DeepSeek/Gemini生成高质量视频摘要
- **字幕大纲生成**：基于字幕内容生成树状结构的逻辑框架
- **时间戳跳转**：大纲中的时间戳链接可直接跳转到视频对应位置
- **现代化界面**：基于FastAPI的后端 + 响应式Web前端

## 🏗️ 项目结构 

```
Cooper_Factory/
├── .gitignore              # Git忽略文件
├── README.md               # 项目说明
├── index.html              # 项目入口页面
├── .env.example            # 环境变量配置模板
├── cookies.txt.example     # B站Cookie配置模板
└── backend/                # 后端服务
    ├── main.py             # FastAPI主应用
    ├── requirements.txt    # Python依赖
    ├── .env                # 环境变量配置（请勿上传）
    ├── cookies.txt         # B站Cookie文件（可选，请勿上传）
    ├── app/
    │   ├── models/
    │   │   └── schemas.py  # Pydantic数据模型
    │   └── services/
    │       ├── ai_service.py      # AI分析服务
    │       └── bili_service.py    # B站数据采集服务
    └── static/
        └── index.html      # Web前端界面
```

## 📋 核心功能

### 1. 视频内容采集
- 支持B站BV号视频链接
- 自动获取视频元数据（标题、UP主、时长等）
- 智能字幕提取（支持Cookie和无Cookie模式）
- 弹幕舆情分析

### 2. AI智能分析
- **核心摘要**：200字以内的高质量内容提炼
- **字幕大纲**：树状结构的逻辑框架展示
- **时间戳链接**：关键节点可直接跳转到视频位置
- 支持DeepSeek和Gemini双引擎

### 3. Web界面
- 现代化响应式设计
- 实时处理状态显示
- 直观的结果展示

## 🛠️ 安装和运行

### 环境要求
- Python 3.8+
- Node.js (可选，用于前端开发)

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd Cooper_Factory
```

2. **安装Python依赖**
```bash
cd backend
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
# 从模板创建配置文件
cp .env.example .env

# 编辑.env文件，配置AI API密钥
# AI_PROVIDER=deepseek  # 或 gemini
# DEEPSEEK_API_KEY=your_key_here
# GEMINI_API_KEY=your_key_here
```

4. **运行服务**
```bash
python main.py
```

5. **访问界面**
打开浏览器访问：http://127.0.0.1:8000

## 🔧 配置说明

### AI引擎配置
支持两种AI引擎，根据需要选择：

- **DeepSeek**：推荐，性价比高
- **Gemini**：Google出品，稳定性好

### Cookie配置（可选）
如果需要访问需要登录的视频内容：

1. 浏览器登录B站
2. 按F12打开开发者工具
3. 复制关键Cookie值：`SESSDATA`、`bili_jct`、`DedeUserID`
4. 在项目根目录创建`cookies.txt`文件

## 📖 使用指南

1. 在输入框中粘贴B站视频链接
2. 点击"开始提取"按钮
3. 等待系统自动分析
4. 查看生成的摘要和大纲
5. 点击大纲中的时间戳可跳转到视频对应位置

## 🔒 安全注意事项

- API密钥请妥善保管，不要上传到公共仓库
- Cookie文件包含个人登录信息，请谨慎使用
- 项目仅用于学习和研究目的，请遵守相关法律法规

## 🛠️ 开发工具

项目在 `backend/test/` 目录下提供了完整的开发工具集：

- **`.cursorrules`** - AI助手环境配置（PowerShell语法等）
- **`.env.example`** - 环境变量配置模板
- **`cookies.txt.example`** - B站Cookie配置指南
- **测试脚本** - 用于功能验证和问题诊断

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用MIT许可证。

---

**Cooper Intelligence Factory** - 让AI为视频内容分析赋能 🚀
