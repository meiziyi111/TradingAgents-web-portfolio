# TradingAgents 在线部署说明

## 推荐方式：Streamlit Community Cloud

1. 将本目录上传到一个新的 GitHub 仓库。
2. 在 Streamlit Community Cloud 选择该仓库的 `dashboard.py` 作为入口。
3. 在应用的 Secrets 中填写环境变量，不要把 Key 写入代码或仓库：

```toml
TRADINGAGENTS_LLM_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = ""
TRADINGAGENTS_DEEP_THINK_LLM = "deepseek-v4-flash"
TRADINGAGENTS_QUICK_THINK_LLM = "deepseek-v4-flash"
```

4. 部署完成后，平台会生成一个可以点击访问的 HTTPS 网页。

## Docker / Render / Railway

使用 `Dockerfile.web` 构建。平台需要把外部端口映射到 `8501`，并通过 Secret / Environment Variables 注入上述变量。不要上传 `.env`。

## 安全边界

- API Key 只存在于部署平台的服务端环境变量中，浏览器只访问 Streamlit 服务，不会直接看到 Key。
- 本发布包不含 `.env`、虚拟环境、历史研究报告、运行日志、缓存或测试数据。
- 如果曾经把真实 Key 提交到 GitHub、截图或公开日志中，应立即在 DeepSeek 控制台撤销并重新生成。
- 这是投研展示工具，不是自动交易系统；输出仍需人工复核，不构成投资建议。

## 本地运行

```powershell
Copy-Item .env.example .env
# 编辑 .env 填入 Key
streamlit run dashboard.py
```
