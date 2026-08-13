# TradingAgents React 投研工作台

这是一个基于开源 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 的二次开发作品集项目。项目保留 LangGraph 多智能体投研链路，并新增面向产品展示的 React 前端、FastAPI 流式接口、结构化决策、组合约束和确定性硬风控。

> 本项目用于研究与产品演示，不连接券商、不自动下单，输出不构成投资建议。

## 展示亮点

- React + Framer Motion：清新、未来感的响应式交互界面。
- 八阶段渐进式输出：市场、情绪、新闻、基本面、研究辩论、交易提案、风险审查、最终决策。
- FastAPI NDJSON 流式接口：每个 Agent 阶段完成后立即推送到页面。
- Pydantic 结构化输入与输出：统一组合、仓位、止损和风险预算字段。
- 硬风控边界：模型给出研究意见，确定性代码负责仓位与风险约束。
- 历史演示模式：不调用模型、不消耗 API 额度也能展示完整交互流程。

## 本地启动

### Windows 一键启动

```powershell
Copy-Item .env.example .env
# 只在本地 .env 中填入 API Key，切勿提交或打包该文件
.\scripts\run_react.ps1
```

打开 `http://127.0.0.1:8000/`。

### Docker

```bash
docker build -t tradingagents-react .
docker run --rm -p 8000:8000 \
  -e TRADINGAGENTS_LLM_PROVIDER=deepseek \
  -e DEEPSEEK_API_KEY=your_server_side_key \
  tradingagents-react
```

API Key 必须通过部署平台的 Secret / Environment Variables 注入，不能写进镜像、代码或前端。

## 验证

```powershell
.\.venv\Scripts\python.exe scripts\smoke_react_api.py
cd frontend
npm.cmd ci
npm.cmd run build
```

`smoke_react_api.py` 覆盖八阶段协议、输入校验、路径安全、演示流、真实流事件顺序、生产前端和报告接口。

## 部署

- 中国大陆演示：参见 [DEPLOY_CN.md](DEPLOY_CN.md)，推荐腾讯云 CloudBase Run 单容器部署。
- 其他 Docker 平台：监听平台提供的 `PORT`，启动命令已写入根目录 `Dockerfile`。
- 旧 Streamlit 页面仍保留为兼容入口，但 React + FastAPI 是当前主版本。

## 安全边界

公开发布包只包含运行所需源码、前端、测试和一份脱敏演示报告。以下内容均不得进入仓库或 ZIP：

- `.env`、`.streamlit/secrets.toml` 和任何真实 API Key；
- `.venv`、`node_modules`、缓存和字节码；
- 本地日志、编辑器配置、运行轨迹和未审计报告；
- Git 凭据、云平台凭据和个人路径信息。

完整发布边界见 [PUBLIC_RELEASE_MANIFEST.md](PUBLIC_RELEASE_MANIFEST.md)。

## 归属与许可证

底层 TradingAgents 框架来自 TauricResearch。本仓库展示的是在其开源基础上的产品化二次开发，不代表从零独立实现原始框架。许可证见 [LICENSE](LICENSE)。
