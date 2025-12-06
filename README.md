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
├── requirements.txt        # Python依赖
├── runtime.txt            # Python版本配置
├── Procfile               # 部署启动命令
├── render.yaml            # Render部署配置
└── backend/                # 后端服务
    ├── main.py             # FastAPI主应用
    ├── .env                # 环境变量配置（请勿上传）
    ├── app/
    │   ├── models/
    │   │   └── schemas.py  # Pydantic数据模型
    │   └── services/
    │       ├── ai_service.py      # AI分析服务
    │       ├── bili_service.py    # B站数据采集服务
    │       ├── cookie_manager.py  # Cookie管理服务
    │       └── ai_client.py       # AI客户端
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
# 编辑backend/.env文件，配置API密钥和Cookies
AI_PROVIDER=deepseek  # 或 gemini
DEEPSEEK_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# B站Cookies（可选，用于获取字幕）
BILI_COOKIES=SESSDATA=your_sessdata; bili_jct=your_bili_jct; DedeUserID=your_dedeuserid
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

**本地开发：**
1. 浏览器登录B站
2. 按F12打开开发者工具
3. 复制关键Cookie值：`SESSDATA`、`bili_jct`、`DedeUserID`
4. 在 `backend/.env` 文件中添加：
```
BILI_COOKIES=SESSDATA=your_sessdata; bili_jct=your_bili_jct; DedeUserID=your_dedeuserid
```

**生产部署：**
在Render/Heroku等平台的"Environment Variables"中设置 `BILI_COOKIES`

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

项目提供了完整的开发工具集：

- **`backend/.env`** - 环境变量配置（本地开发）
- **`backend/test/`** - 测试脚本和开发工具
- **GitHub Actions** - 自动化部署和测试
- **Render** - 云端部署平台

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用MIT许可证。

---

**Cooper Intelligence Factory** - 让AI为视频内容分析赋能 🚀
