"""
TradingAgents 可视化分析面板 (直接调用模式)
运行: streamlit run dashboard.py
"""
import streamlit as st
import queue
import threading
import time
import os
import re
from pathlib import Path
from datetime import datetime

# 启动时加载 .env，确保后续线程能读到环境变量
try:
    from dotenv import load_dotenv, find_dotenv
    # Streamlit may run with a working directory different from this file.
    # Resolve the local secrets file relative to dashboard.py first so the
    # worker and DEFAULT_CONFIG see the same provider configuration.
    _local_env = Path(__file__).resolve().with_name(".env")
    if _local_env.exists():
        load_dotenv(_local_env, override=True)
    else:
        _fallback_env = find_dotenv(usecwd=True)
        if _fallback_env:
            load_dotenv(_fallback_env, override=True)
except ImportError:
    pass

st.set_page_config(
    page_title="TradingAgents 分析面板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

REPORTS_DIR = Path("reports")

STAGES = [
    ("📊", "市场分析",     "market_report"),
    ("💬", "情绪分析",     "sentiment_report"),
    ("📰", "新闻分析",     "news_report"),
    ("📈", "基本面分析",   "fundamentals_report"),
    ("🧠", "研究团队辩论", "investment_plan"),
    ("💹", "交易员计划",   "trader_investment_plan"),
    ("🏆", "投资组合经理决策", "final_trade_decision"),
]

# Seven business stages contain twelve specialized agent roles.
AGENT_ROLES = [
    ("Market Analyst", "市场与技术分析", "market_report"),
    ("Sentiment Analyst", "情绪与社媒分析", "sentiment_report"),
    ("News Analyst", "新闻与事件分析", "news_report"),
    ("Fundamentals Analyst", "财报与基本面分析", "fundamentals_report"),
    ("Bull Researcher", "多头研究员", "investment_plan"),
    ("Bear Researcher", "空头研究员", "investment_plan"),
    ("Research Manager", "研究经理", "investment_plan"),
    ("Trader", "交易提案", "trader_investment_plan"),
    ("Aggressive Risk Analyst", "激进风险分析师", "risk_assessment"),
    ("Neutral Risk Analyst", "中性风险分析师", "risk_assessment"),
    ("Conservative Risk Analyst", "保守风险分析师", "risk_assessment"),
    ("Portfolio Manager", "组合经理最终裁决", "final_trade_decision"),
]

# ========== Session State ==========

if "app_state" not in st.session_state:
    st.session_state.app_state = "idle"       # idle | running | done | error
    st.session_state.analysis_log = []         # list[str]
    st.session_state.completed_stages = set()  # set of keys (market_report, …)
    st.session_state.status_queue = None       # queue.Queue
    st.session_state.analysis_thread = None    # Thread
    st.session_state.last_ticker = ""
    st.session_state.last_date = ""
    st.session_state.error_detail = ""
    st.session_state.current_report = None     # {"ticker": …, "date": …}


# ========== Helper: scan / parse / extract (与之前相同) ==========

def scan_reports():
    reports = []
    if not REPORTS_DIR.exists():
        return reports
    for ticker_dir in sorted(REPORTS_DIR.iterdir()):
        if ticker_dir.is_dir():
            for date_dir in sorted(ticker_dir.iterdir(), reverse=True):
                report_file = date_dir / "complete_report.md"
                if report_file.exists():
                    reports.append({
                        "ticker": ticker_dir.name,
                        "date": date_dir.name,
                        "path": report_file,
                        "mtime": datetime.fromtimestamp(report_file.stat().st_mtime),
                    })
    return sorted(reports, key=lambda r: r["mtime"], reverse=True)


def parse_sections(md_content):
    sections = {}
    current_section, current_content = None, []
    mapping = {
        "市场分析": "market_report", "情绪分析": "sentiment_report",
        "新闻分析": "news_report", "基本面分析": "fundamentals_report",
        "研究团队决策": "investment_plan",
        "交易团队计划": "trader_investment_plan",
        "最终交易决策": "final_trade_decision",
        "最终交易建议": "final_trade_decision",
        "最终交易提案": "final_trade_decision",
        "风险评估": "risk_assessment",
        "证据链与数据来源": "evidence_chain",
    }
    for line in md_content.split("\n"):
        matched = False
        for header, key in mapping.items():
            # Only level-2 headings are report sections.  A nested heading
            # such as ``### 最终交易决策`` must remain inside the PM section.
            if line.strip().startswith("## ") and header in line:
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = key
                current_content = []
                matched = True
                break
        if not matched and current_section:
            current_content.append(line)
    if current_section and current_content:
        sections[current_section] = "\n".join(current_content).strip()
    return sections


def _normalize_signal(value):
    """Normalize Chinese/English recommendations to one display vocabulary."""
    if not value:
        return "N/A"
    cleaned = re.sub(r"[*_`（）()]", " ", str(value)).strip()
    upper = cleaned.upper()
    aliases = {
        "BUY": "BUY", "买入": "BUY", "增持": "OVERWEIGHT",
        "OVERWEIGHT": "OVERWEIGHT", "加仓": "OVERWEIGHT",
        "HOLD": "HOLD", "持有": "HOLD", "观望": "HOLD",
        "SELL": "SELL", "卖出": "SELL", "清仓": "SELL",
        "UNDERWEIGHT": "UNDERWEIGHT", "减持": "UNDERWEIGHT",
    }
    for alias, normalized in aliases.items():
        if upper == alias or cleaned == alias:
            return normalized
    return upper.split()[0] if upper else "N/A"


def _first_capture(texts, patterns):
    """Return the first non-empty regex capture, searching by priority."""
    for text in texts:
        if not text:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
    return None


def extract_info(sections):
    """Extract headline fields with PM-first precedence.

    The old implementation searched one concatenated document, so Trader's
    ``Action: Buy`` could overwrite the PM's final Hold/Underweight decision.
    """
    final = sections.get("final_trade_decision", "")
    trader = sections.get("trader_investment_plan", "")
    research = sections.get("investment_plan", "")

    rating_raw = _first_capture([final], [
        r"\*{0,2}Rating\*{0,2}\s*[：:]\s*\*{0,2}([A-Za-z]+)",
        r"\*{0,2}Recommendation\*{0,2}\s*[：:]\s*\*{0,2}([A-Za-z]+)",
        r"(?:执行)?评级\s*[：:]\s*\*{0,2}(买入|增持|持有|观望|减持|卖出|清仓|Buy|Overweight|Hold|Underweight|Sell)",
        r"最终交易决策\s*[：:]\s*\*{0,2}(买入|增持|持有|观望|减持|卖出|清仓|Buy|Overweight|Hold|Underweight|Sell)",
    ])
    trader_action_raw = _first_capture([trader], [
        r"\*{0,2}Action\*{0,2}\s*[：:]\s*\*{0,2}(Buy|Hold|Sell|买入|持有|卖出)",
        r"FINAL TRANSACTION PROPOSAL\s*[：:]\s*\*{0,2}(BUY|HOLD|SELL)",
    ])

    price = _first_capture([final, trader, research], [
        r"\*{0,2}Price Target\*{0,2}\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)",
        r"目标价(?:位|格)?\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)",
        r"价格目标(?:（[^）]*）|\([^)]*\))?\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?\s*(?:[-–—~至]\s*\$?[0-9]+(?:\.[0-9]+)?)?)",
        r"价格目标[\s\S]{0,160}?(?:执行区间|入场区间|目标价格)[：:]\s*\$?([0-9]+(?:\.[0-9]+)?\s*(?:[-–—~至]\s*\$?[0-9]+(?:\.[0-9]+)?)?)",
    ])
    stop = _first_capture([final, trader, research], [
        r"\*{0,2}Stop Loss\*{0,2}\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)",
        r"(?:核心)?止损(?:位|线)?\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)",
    ])
    sizing = _first_capture([final, trader, research], [
        r"\*{0,2}Position Sizing\*{0,2}\s*[：:]\s*(.+)",
        r"仓位(?:依据|建议|规模)?\s*[：:]\s*(.+)",
    ])

    rating = _normalize_signal(rating_raw)
    action = _normalize_signal(trader_action_raw)
    final_signal = rating if rating != "N/A" else action
    return {
        "signal": final_signal,
        "action": action,
        "price": price or "N/A",
        "stop": stop or "N/A",
        "rating": rating if rating != "N/A" else final_signal,
        "position_sizing": sizing or "N/A",
    }


# ========== 分析工作线程 ==========

def _analysis_worker(ticker: str, date: str, q: queue.Queue):
    """在线程中运行分析，通过队列向主线程发送更新。"""
    import traceback
    try:
        from tradingagents.llm_clients.api_key_env import get_api_key_env
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        provider = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai").strip().lower()
        key_env = get_api_key_env(provider)
        if key_env and not os.getenv(key_env, "").strip():
            raise RuntimeError(
                f"当前模型提供商为 {provider}，但未配置 {key_env}。"
                "请在本地副本的 .env 中配置新 key，或先选择已有报告进行展示。"
            )

        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["output_language"] = "Chinese"

        q.put({"type": "log", "msg": f"🚀 开始分析 {ticker} ({date})..."})

        ta = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
        )

        init_state = ta.propagator.create_initial_state(ticker, date)
        args = ta.propagator.get_graph_args()

        chapter_titles = {
            "market_report":         "[1/7] 市场分析报告",
            "sentiment_report":      "[2/7] 情绪分析报告",
            "news_report":           "[3/7] 新闻分析报告",
            "fundamentals_report":   "[4/7] 基本面分析报告",
            "investment_plan":       "[5/7] 研究团队决策",
            "trader_investment_plan":"[6/7] 交易团队计划",
            "final_trade_decision":  "[7/7] 最终交易决策",
        }

        completed = set()
        final_state = {}

        for chunk in ta.graph.stream(init_state, **args):
            final_state.update(chunk)
            for key, title in chapter_titles.items():
                if key in chunk and chunk[key] and key not in completed:
                    completed.add(key)
                    q.put({"type": "stage_done", "key": key})
                    q.put({"type": "log", "msg": f"  ✅ {title}"})

        # Do not save a report that cannot satisfy the PM decision contract.
        pm_text = str(final_state.get("final_trade_decision", ""))
        required_fields = {
            "Price Target": r"\*{0,2}Price Target\*{0,2}\s*[：:]\s*\$?[0-9]+(?:\.[0-9]+)?",
            "Stop Loss": r"\*{0,2}Stop Loss\*{0,2}\s*[：:]\s*\$?[0-9]+(?:\.[0-9]+)?",
            "Position Sizing": r"\*{0,2}Position Sizing\*{0,2}\s*[：:]\s*.+",
        }
        missing_fields = [
            name for name, pattern in required_fields.items()
            if not re.search(pattern, pm_text, flags=re.IGNORECASE)
        ]
        if missing_fields:
            raise RuntimeError(
                "Portfolio Manager 输出缺少必填字段："
                + ", ".join(missing_fields)
                + "。本次不会保存不完整报告，请重试。"
            )

        # 保存报告
        report_dir = REPORTS_DIR / ticker / date
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / "complete_report.md"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# {ticker} 完整分析报告\n")
            f.write(f"分析日期: {date}\n\n")
            section_map = [
                ("market_report",         "## 市场分析报告"),
                ("sentiment_report",      "## 情绪分析报告"),
                ("news_report",           "## 新闻分析报告"),
                ("fundamentals_report",   "## 基本面分析报告"),
                ("investment_plan",       "## 研究团队决策"),
                ("trader_investment_plan","## 交易团队计划"),
                ("final_trade_decision",  "## 最终交易决策"),
            ]
            for key, title in section_map:
                if key in final_state and final_state[key]:
                    f.write(f"\n{title}\n\n{final_state[key]}\n\n---\n")

            # Persist the risk debate so the final PM decision is auditable.
            risk_state = final_state.get("risk_debate_state", {}) or {}
            risk_parts = []
            for label, key in [
                ("Aggressive Risk Analyst", "aggressive_history"),
                ("Neutral Risk Analyst", "neutral_history"),
                ("Conservative Risk Analyst", "conservative_history"),
            ]:
                value = risk_state.get(key, "")
                if value:
                    risk_parts.append(f"### {label}\n\n{value}")
            if risk_state.get("judge_decision"):
                risk_parts.append(
                    "### Risk Debate Decision Context\n\n"
                    + str(risk_state["judge_decision"])
                )
            if risk_parts:
                f.write("\n## 风险评估\n\n" + "\n\n".join(risk_parts) + "\n\n---\n")

            f.write(
                "\n## 证据链与数据来源\n\n"
                "本报告由以下工具类别为 Agent 提供分析上下文：\n\n"
                "- 市场：行情数据与技术指标工具\n"
                "- 情绪：新闻、StockTwits 与 Reddit 数据\n"
                "- 新闻：公司新闻、全球新闻与内幕交易信息\n"
                "- 基本面：公司基本面、资产负债表、现金流量表与利润表\n\n"
                "说明：报告保存 Agent 处理后的证据摘要；原始工具响应不写入公开报告。\n\n---\n"
            )

        q.put({"type": "done", "ticker": ticker, "date": date})

    except Exception as e:
        q.put({"type": "error", "msg": str(e), "detail": traceback.format_exc()})


# ========== 队列处理 ==========

def drain_queue():
    """将队列中所有待处理的消息写入 session_state。"""
    q = st.session_state.status_queue
    if q is None:
        return
    try:
        while True:
            msg = q.get_nowait()
            t = msg["type"]
            if t == "log":
                st.session_state.analysis_log.append(msg["msg"])
            elif t == "stage_done":
                st.session_state.completed_stages.add(msg["key"])
            elif t == "done":
                st.session_state.last_ticker = msg["ticker"]
                st.session_state.last_date = msg["date"]
                st.session_state.app_state = "done"
            elif t == "error":
                st.session_state.analysis_log.append(f"❌ {msg['msg']}")
                st.session_state.error_detail = msg.get("detail", "")
                st.session_state.app_state = "error"
    except queue.Empty:
        pass


def start_analysis(ticker: str, date: str):
    """启动后台分析线程。"""
    q = queue.Queue()
    st.session_state.status_queue = q
    st.session_state.analysis_log = []
    st.session_state.completed_stages = set()
    st.session_state.app_state = "running"
    st.session_state.last_ticker = ticker
    st.session_state.last_date = date
    st.session_state.error_detail = ""
    st.session_state.current_report = None

    t = threading.Thread(
        target=_analysis_worker,
        args=(ticker, date, q),
        daemon=True,
    )
    t.start()
    st.session_state.analysis_thread = t


# ========== 样式 ==========

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa; padding: 0.8rem; border-radius: 8px;
        text-align: center; border: 1px solid #eee;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #1f77b4; }
    .metric-label { font-size: 0.85rem; color: #666; }
    .stage-grid { display: flex; gap: 0.3rem; flex-wrap: wrap; }
    .stage-item { flex: 1; min-width: 80px; text-align: center;
                  padding: 0.4rem 0.2rem; border-radius: 6px;
                  background: #f8f9fa; font-size: 0.75rem; }
    .stage-item.done { background: #d4edda; }
    .stage-item.active { background: #cce5ff; border: 2px solid #007bff; }
</style>
""", unsafe_allow_html=True)


# ========== 侧边栏 ==========

st.sidebar.title("📊 TradingAgents")
st.sidebar.caption("多智能体金融交易分析面板")

# 历史报告列表
reports = scan_reports()
report_labels = []
report_map = {}
for r in reports:
    label = f"{r['ticker']} | {r['date']}"
    report_labels.append(label)
    report_map[label] = r

# 让 selectbox 的值与 current_report 联动
if report_labels:
    # 找到当前报告对应的 label
    cur = st.session_state.current_report
    default_idx = 0
    if cur:
        match_label = f"{cur['ticker']} | {cur['date']}"
        if match_label in report_map:
            default_idx = report_labels.index(match_label)

    st.sidebar.subheader("📂 历史报告")
    sel_label = st.sidebar.selectbox(
        "选择报告", report_labels,
        index=default_idx,
        label_visibility="collapsed",
        key="report_selector",
    )
    selected_report = report_map[sel_label]
else:
    selected_report = None

st.sidebar.markdown("---")
st.sidebar.subheader("🚀 新分析")

with st.sidebar.form("new_analysis", clear_on_submit=False):
    new_ticker = st.text_input(
        "股票代码",
        value=st.session_state.last_ticker or "NVDA",
    ).strip().upper()
    new_date = st.date_input(
        "分析日期",
        datetime.now(),
    ).strftime("%Y-%m-%d")
    run_btn = st.form_submit_button(
        "开始分析",
        use_container_width=True,
        type="primary",
        disabled=(st.session_state.app_state == "running"),
    )

if run_btn and st.session_state.app_state != "running":
    start_analysis(new_ticker, new_date)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Powered by DeepSeek V4 Flash")


# ========== 主区域逻辑 ==========

# 处理队列消息（每次 rerun 都会执行）
drain_queue()

# 检测线程意外死亡
if st.session_state.app_state == "running":
    thread = st.session_state.analysis_thread
    if thread and not thread.is_alive():
        # 最后一次尝试处理队列
        drain_queue()
        # 如果状态还是 running，说明线程悄无声息地挂了
        if st.session_state.app_state == "running":
            st.session_state.app_state = "error"
            st.session_state.error_detail = "分析线程意外终止。请检查日志。"
            st.rerun()

# ---- 页面分发 ----

if st.session_state.app_state == "running":
    # ==================== 运行中 ====================
    st.title(f"🔄 正在分析 {st.session_state.last_ticker}...")

    # 当前阶段推断（最后完成的 stage 的下一个）
    completed = st.session_state.completed_stages
    current_idx = 0
    for i, (_, _, key) in enumerate(STAGES):
        if key in completed:
            current_idx = i + 1

    # 阶段进度条
    cols = st.columns(len(STAGES))
    for i, (emoji, name, key) in enumerate(STAGES):
        with cols[i]:
            done = key in completed
            active = i == current_idx and not done
            cls = "done" if done else "active" if active else ""
            icon = emoji
            st.markdown(
                f"<div class='stage-item {cls}' style='font-size:1.2rem'>{icon}</div>"
                f"<div style='text-align:center;font-size:0.65rem'>{name}</div>"
                f"<div style='text-align:center;font-size:0.8rem'>{'✅' if done else '🔄' if active else '⏳'}</div>",
                unsafe_allow_html=True,
            )

    # 整体进度
    progress = min(len(completed) / len(STAGES), 1.0)
    st.progress(progress, text=f"{len(completed)}/{len(STAGES)} 阶段完成")

    # 当前阶段名
    if current_idx < len(STAGES):
        _, cur_name, _ = STAGES[current_idx]
        st.markdown(f"**当前**: {STAGES[current_idx][0]} {cur_name}")
    else:
        st.markdown("**当前**: 🎉 所有阶段已完成，正在保存报告…")

    # 日志区
    log = st.session_state.analysis_log
    with st.container():
        st.markdown("**运行日志**")
        st.code("\n".join(log[-30:]) if log else "等待输出…", language="text")

    # 自动刷新
    time.sleep(1)
    st.rerun()
    st.stop()

elif st.session_state.app_state == "done":
    # ==================== 完成 ====================
    ticker = st.session_state.last_ticker
    date = st.session_state.last_date
    st.success(f"✅ {ticker} 分析完成！")

    # 自动设置 current_report 以便展示
    st.session_state.current_report = {"ticker": ticker, "date": date}

    with st.expander("📜 查看运行日志", expanded=False):
        st.code("\n".join(st.session_state.analysis_log), language="text")

    if st.button("📊 查看完整报告", type="primary", use_container_width=True):
        st.session_state.app_state = "idle"
        st.rerun()

    st.stop()

elif st.session_state.app_state == "error":
    # ==================== 错误 ====================
    st.error(f"❌ 分析失败: {st.session_state.last_ticker}")

    with st.expander("🔍 错误详情", expanded=False):
        st.code(st.session_state.error_detail, language="text")

    with st.expander("📜 运行日志", expanded=False):
        st.code("\n".join(st.session_state.analysis_log), language="text")

    if st.button("🔄 重试", use_container_width=True):
        st.session_state.app_state = "idle"
        st.rerun()

    st.stop()

# ==================== idle: 显示报告 ====================

# 优先显示 current_report（刚分析完的），否则用 sidebar 选中的
if st.session_state.current_report:
    report_meta = st.session_state.current_report
    report_path = REPORTS_DIR / report_meta["ticker"] / report_meta["date"] / "complete_report.md"
elif selected_report:
    report_meta = selected_report
    report_path = report_meta["path"]
else:
    st.info("👈 左侧选择一个报告，或输入股票代码开始新分析")
    st.stop()

if not report_path.exists():
    st.warning("报告文件不存在，可能已被删除。")
    st.session_state.current_report = None
    st.stop()

md = report_path.read_text(encoding="utf-8")
sections = parse_sections(md)
info = extract_info(sections)

action_colors = {
    "BUY": "#28a745", "SELL": "#dc3545", "HOLD": "#ffc107",
    "UNDERWEIGHT": "#dc3545", "OVERWEIGHT": "#28a745",
}
ac = action_colors.get(info["signal"].upper(), "gray")

ticker_display = report_meta["ticker"]
date_display = report_meta["date"]

col1, col2 = st.columns([3, 1])
with col1:
    st.title(f"{ticker_display} 完整分析报告")
    st.caption(f"分析日期: {date_display}")
with col2:
    st.markdown(f"<h1 style='text-align:right; color:{ac}'>{info['signal']}</h1>", unsafe_allow_html=True)

with st.expander("🧩 系统 Agent 架构（12 个角色 / 7 个业务阶段）", expanded=False):
    role_cols = st.columns(3)
    for i, (role, label, _) in enumerate(AGENT_ROLES):
        with role_cols[i % 3]:
            st.markdown(f"**{i + 1}. {role}**  \n{label}")

# 指标卡
mcol1, mcol2, mcol3, mcol4 = st.columns(4)
for c, v, l in [
    (mcol1, info["rating"], "最终评级"),
    (mcol2, info["action"], "建议"),
    (mcol3, f"${info['price']}" if info['price'] != 'N/A' else 'N/A', "目标价"),
    (mcol4, f"${info['stop']}" if info['stop'] != 'N/A' else 'N/A', "止损"),
]:
    c.markdown(
        f"<div class='metric-card'><div class='metric-value'>{v}</div>"
        f"<div class='metric-label'>{l}</div></div>",
        unsafe_allow_html=True,
    )

st.divider()

# 团队流程
st.subheader("🤖 多智能体分析流程")
cols = st.columns(len(STAGES))
for i, (emoji, name, key) in enumerate(STAGES):
    done = key in sections and sections[key].strip()
    with cols[i]:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem'>"
            f"<div style='font-size:1.5rem'>{emoji}</div>"
            f"<div style='font-size:0.7rem;font-weight:600'>{name}</div>"
            f"<div>{'✅' if done else '⏳'}</div></div>",
            unsafe_allow_html=True,
        )

st.divider()

# 报告正文
for emoji, title, key in STAGES:
    if key in sections and sections[key].strip():
        with st.expander(f"{emoji} **{title}**", expanded=(key in ["final_trade_decision", "investment_plan"])):
            st.markdown(sections[key])
    else:
        with st.expander(f"⏳ **{title}** _(等待分析…)_", expanded=False):
            st.info("该部分尚未生成。")

for emoji, title, key in [
    ("🛡️", "风险评估辩论", "risk_assessment"),
    ("🔗", "证据链与数据来源", "evidence_chain"),
]:
    if key in sections and sections[key].strip():
        with st.expander(f"{emoji} **{title}**", expanded=False):
            st.markdown(sections[key])

st.divider()

# 底部操作
col1, col2 = st.columns(2)
with col1:
    report_dir_to_open = report_path.parent
    if os.name == "nt" and st.button("📂 打开报告文件夹"):
        os.startfile(str(report_dir_to_open))
with col2:
    st.download_button(
        "⬇️ 下载报告",
        data=md,
        file_name=f"{ticker_display}_{date_display}_report.md",
        mime="text/markdown",
    )

# 清除 current_report 点击后让 sidebar selectbox 接管
if st.session_state.current_report is not None:
    if st.button("← 返回报告列表"):
        st.session_state.current_report = None
        st.rerun()
