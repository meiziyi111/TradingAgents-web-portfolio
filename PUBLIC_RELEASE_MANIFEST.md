# 公开发布清单

## 已包含

- React 前端源码与生产构建；
- FastAPI 流式服务和 TradingAgents 二次开发源码；
- Streamlit 兼容入口；
- 启动、构建和冒烟测试脚本；
- Pydantic 决策结构、硬风控、审计与报告代码；
- 一份经过路径与敏感词扫描的 NVDA 演示报告；
- 空值环境变量示例、Dockerfile、许可证和部署文档。

## 明确排除

- `.env`、`.env.txt`、`.streamlit/secrets.toml`；
- 真实 API Key、GitHub Token、云平台凭据、私钥和密码；
- `.venv`、`node_modules`、`.git`、IDE 配置；
- `__pycache__`、数据缓存、测试缓存和构建临时文件；
- 本地运行日志与 Agent 原始执行轨迹；
- 除指定演示报告以外的历史研究报告；
- 任何券商账户、真实用户持仓或个人身份信息。

## 发布前必须重新执行

1. 扫描工作树中的常见密钥格式；
2. 用本地真实 Key 的值反查发布目录和可达 Git 历史；
3. 检查 ZIP 文件清单中不存在排除项；
4. 解压 ZIP 后执行测试和前端构建；
5. 部署平台仅通过 Secret / Environment Variables 注入新 Key。
