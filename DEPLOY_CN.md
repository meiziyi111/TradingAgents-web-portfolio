# 中国大陆部署说明

更新日期：2026-08-14

## 结论

推荐将 React 静态资源和 FastAPI API 一起部署到腾讯云 CloudBase Run，保持同域访问。该方案无需拆分前后端，也不会把模型密钥暴露给浏览器。

本机地址 `http://127.0.0.1:8000/` 只能在当前电脑访问，它本身不是线上网站。旧版 Streamlit Cloud 是否能在中国大陆稳定访问无法保证；新版 React 也不能直接由 Streamlit 入口完整承载。

## CloudBase Run 部署步骤

1. 登录腾讯云，创建 CloudBase 环境。
2. 进入“云托管 CloudBase Run”，新建服务，例如 `tradingagents-react`。
3. 选择“上传代码包”，上传本发布 ZIP。上传时压缩包根目录必须直接包含 `Dockerfile`，不要在 ZIP 外再套一层目录。
4. 设置容器端口为 `8000`，Dockerfile 名称为 `Dockerfile`。
5. 在平台环境变量中配置：

```text
TRADINGAGENTS_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=<在腾讯云控制台填写，不要写进代码>
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-flash
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash
```

6. 作品集演示阶段可将最小实例数设为 `0`、最大实例数设为 `1` 以控制成本；如果需要减少首次访问冷启动，可将最小实例数设为 `1`。
7. 开启公网访问，用平台默认域名先完成测试。
8. 依次检查 `/api/health`、首页、历史动态演示和一次受控的真实分析。

## 域名与备案

- CloudBase 默认域名适合开发和面试演示，但官方说明它存在频率、有效期和稳定性限制。
- 若用于长期公开展示，建议绑定自己的域名。使用中国大陆云资源提供正式网站服务时，需要完成 ICP 备案。
- EdgeOne Pages 的中国大陆或全球含大陆加速区域同样要求备案；未备案只能选择不含中国大陆区域，不适合作为本项目的大陆访问主方案。

## 状态与持久化限制

当前展示版把生成报告写在容器本地目录。CloudBase Run 是无状态容器：实例重建、缩容或多实例运行时，新报告可能丢失或不一致。因此：

- 一份脱敏演示报告随镜像发布，始终可用于页面演示；
- 真实分析结果在生产化前应改存腾讯云 COS、CloudBase 数据库或其他持久化存储；
- 未接入持久化前建议最大实例数保持为 `1`，不要把它描述为高可用生产系统。

## 安全要求

- 使用一枚新创建、可单独撤销、设置额度上限的模型 API Key；
- API Key 只放在 CloudBase 环境变量中，不进入 GitHub、ZIP、Dockerfile、前端或日志；
- 公网演示建议增加访问频率限制、运行次数上限和身份验证，避免他人消耗模型额度；
- 不上传用户真实持仓、券商账户、交易凭据或个人信息；
- 保持 `execution_enabled=false`，不接入真实下单接口。
