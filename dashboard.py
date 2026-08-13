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

from tradingagents.dashboard_ui import (
    inject_theme,
    render_agent_grid,
    render_empty_state,
    render_legal_footer,
    render_metric_grid,
    render_report_hero,
    render_running_header,
    render_section_head,
    render_sidebar_brand,
    render_stage_rail,
    render_state_card,
    render_terminal,
    signal_tone,
)

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
    # Let Streamlit keep the research controls open on desktop while collapsing
    # them on narrow screens so the report is not hidden behind the sidebar.
    initial_sidebar_state="auto",
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
        "risk_validation": "N/A",
    }


# ========== 分析工作线程 ==========

def _analysis_worker(ticker: str, date: str, q: queue.Queue, portfolio_context: dict):
    """在线程中运行分析，通过队列向主线程发送更新。"""
    import traceback
    try:
        from tradingagents.llm_clients.api_key_env import get_api_key_env
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.report_artifacts import write_decision_artifact
        from tradingagents.dataflows.provenance import get_tool_trace, reset_tool_trace

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
        config["checkpoint_enabled"] = True

        q.put({"type": "log", "msg": f"🚀 开始分析 {ticker} ({date})..."})
        reset_tool_trace()

        ta = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
        )

        # output key -> (UI stage key, title).  The last stage must wait for the
        # deterministic Hard Risk Engine, rather than being marked complete as
        # soon as the Portfolio Manager emits its advisory recommendation.
        chapter_titles = {
            "market_report": (
                "market_report", "[1/7] 市场分析报告"
            ),
            "sentiment_report": (
                "sentiment_report", "[2/7] 情绪分析报告"
            ),
            "news_report": ("news_report", "[3/7] 新闻分析报告"),
            "fundamentals_report": (
                "fundamentals_report", "[4/7] 基本面分析报告"
            ),
            "investment_plan": (
                "investment_plan", "[5/7] 研究团队决策"
            ),
            "trader_investment_plan": (
                "trader_investment_plan", "[6/7] 交易团队计划"
            ),
            "final_decision_structured": (
                "final_trade_decision", "[7/7] 硬风控后的最终交易决策"
            ),
        }

        completed = set()
        final_state = {}

        for chunk in ta.stream_propagate(
            ticker, date, portfolio_context=portfolio_context
        ):
            final_state.update(chunk)
            for output_key, (stage_key, title) in chapter_titles.items():
                if (
                    output_key in chunk
                    and chunk[output_key]
                    and output_key not in completed
                ):
                    completed.add(output_key)
                    q.put({"type": "stage_done", "key": stage_key})
                    q.put({"type": "log", "msg": f"  ✅ {title}"})
        evidence_records = get_tool_trace()

        # Validate the Hard Risk Engine's exact typed State value rather than
        # re-parsing a human-readable Markdown rendering with regex.
        final_decision = final_state.get("final_decision_structured")
        if not isinstance(final_decision, dict):
            raise RuntimeError(
                "Hard Risk Engine 未返回已校验的结构化决策。"
                "本次不会保存无法审计的报告，请重试。"
            )

        # 保存报告
        report_dir = REPORTS_DIR / ticker / date
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / "complete_report.md"
        write_decision_artifact(
            report_dir / "decision.json",
            ticker=ticker,
            trade_date=date,
            decision_payload=final_decision,
            trading_proposal_payload=final_state.get("trading_proposal_structured"),
            risk_reviews_payload=(final_state.get("risk_debate_state") or {}).get(
                "structured_reviews", []
            ),
            portfolio_context_payload=final_state.get("portfolio_context"),
            portfolio_recommendation_payload=final_state.get(
                "portfolio_recommendation_structured"
            ),
            risk_validation_payload=final_state.get("risk_validation"),
            evidence_records=evidence_records,
            run_id=final_state.get("run_id") or ta.current_run_id,
            trace_summary=(ta.last_trace or {}).get("summary"),
            trace_file=(
                Path(ta.last_trace_path).name if ta.last_trace_path else None
            ),
        )

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

            f.write("\n## 证据链与数据来源\n\n")
            if evidence_records:
                for record in evidence_records:
                    f.write(
                        f"- `{record.get('tool')}` via `{record.get('vendor')}` | "
                        f"status={record.get('status')} | source={record.get('source_uri')} | "
                        f"fetched_at={record.get('completed_at') or record.get('requested_at') or 'n/a'} | "
                        f"output_sha256={record.get('output_sha256', 'n/a')}\n"
                    )
            else:
                f.write("- 本次运行未捕获到工具证据记录。\n")
            f.write(
                "\n说明：公开报告只保存调用元数据和响应哈希；原始工具响应不写入公开报告。"
                "这能证明调用发生和结果未被替换，但不等于数据供应商提供了历史 point-in-time 保证。\n\n---\n"
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


def start_analysis(ticker: str, date: str, portfolio_context: dict):
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
        args=(ticker, date, q, portfolio_context),
        daemon=True,
    )
    t.start()
    st.session_state.analysis_thread = t


# ========== 样式 ==========

inject_theme()


# ========== 侧边栏 ==========

with st.sidebar:
    render_sidebar_brand()

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

    st.sidebar.markdown(
        '<div class="ta-side-label">Research library · 历史研究</div>',
        unsafe_allow_html=True,
    )
    sel_label = st.sidebar.selectbox(
        "选择报告", report_labels,
        index=default_idx,
        label_visibility="collapsed",
        key="report_selector",
    )
    selected_report = report_map[sel_label]
else:
    selected_report = None

st.sidebar.markdown(
    '<div class="ta-side-label">New mission · 新分析</div>',
    unsafe_allow_html=True,
)

with st.sidebar.form("new_analysis", clear_on_submit=False):
    new_ticker = st.text_input(
        "股票代码",
        value=st.session_state.last_ticker or "NVDA",
    ).strip().upper()
    new_date = st.date_input(
        "分析日期",
        datetime.now(),
    ).strftime("%Y-%m-%d")
    st.markdown(
        '<div class="ta-demo-note">Demo Portfolio · 这里的资金与持仓仅用于验证仓位和风险约束，不代表真实账户，也不会触发交易。</div>',
        unsafe_allow_html=True,
    )
    current_price = st.number_input("当前价格（0 表示缺失）", min_value=0.0, value=0.0, step=1.0)
    demo_portfolio_value = st.number_input("Demo 组合总资产", min_value=1.0, value=100000.0, step=10000.0)
    demo_cash = st.number_input("Demo 现金", min_value=0.0, value=100000.0, step=10000.0)
    demo_current_position = st.number_input("当前股票持仓市值", min_value=0.0, value=0.0, step=1000.0)
    max_single_position_pct = st.slider("单票仓位上限", 1, 100, 10)
    risk_budget_pct = st.slider("单笔风险预算", 1, 20, 1)
    run_btn = st.form_submit_button(
        "开始分析",
        use_container_width=True,
        type="primary",
        disabled=(st.session_state.app_state == "running"),
    )

if run_btn and st.session_state.app_state != "running":
    portfolio_context = {
        "source": "demo",
        "cash": demo_cash,
        "total_portfolio_value": demo_portfolio_value,
        "current_positions": (
            {new_ticker: demo_current_position} if demo_current_position > 0 else {}
        ),
        "ticker_current_position": demo_current_position,
        "ticker_current_weight": demo_current_position / demo_portfolio_value,
        "max_single_position": max_single_position_pct / 100,
        "risk_budget": risk_budget_pct / 100,
        "current_price": current_price if current_price > 0 else None,
        "price_as_of": new_date if current_price > 0 else None,
        "notes": "User-supplied Demo Portfolio from Streamlit; not a brokerage account.",
    }
    start_analysis(new_ticker, new_date, portfolio_context)
    st.rerun()

st.sidebar.markdown(
    '<div class="ta-system-note"><span class="ta-system-dot"></span>'
    '<span>Research engine ready · Local advisory mode</span></div>',
    unsafe_allow_html=True,
)


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
    # 当前阶段推断（最后完成的 stage 的下一个）
    completed = st.session_state.completed_stages
    current_idx = 0
    for i, (_, _, key) in enumerate(STAGES):
        if key in completed:
            current_idx = i + 1

    progress = min(len(completed) / len(STAGES), 1.0)
    if current_idx < len(STAGES):
        _, cur_name, _ = STAGES[current_idx]
    else:
        cur_name = "全部阶段完成，正在固化报告与审计记录"

    render_running_header(
        st.session_state.last_ticker,
        st.session_state.last_date,
        progress,
        cur_name,
    )
    render_section_head(
        "Orchestration map",
        "Agent协作进度",
        f"{len(completed)} / {len(STAGES)} 个业务阶段已完成",
    )
    render_stage_rail(
        STAGES,
        completed,
        current_idx if current_idx < len(STAGES) else None,
    )

    # 日志区
    render_section_head(
        "Event stream",
        "实时任务事件",
        "仅展示节点状态，不展示模型隐藏推理过程",
    )
    render_terminal(st.session_state.analysis_log)
    render_legal_footer()

    # 自动刷新
    time.sleep(1)
    st.rerun()
    st.stop()

elif st.session_state.app_state == "done":
    # ==================== 完成 ====================
    ticker = st.session_state.last_ticker
    date = st.session_state.last_date
    render_state_card(
        "success",
        f"{ticker} 研究任务已完成",
        f"七个业务阶段已经结束，报告、结构化决策和审计记录已保存。数据截止 {date}。",
    )

    # 自动设置 current_report 以便展示
    st.session_state.current_report = {"ticker": ticker, "date": date}

    with st.expander("📜 查看运行日志", expanded=False):
        st.code("\n".join(st.session_state.analysis_log), language="text")

    if st.button("打开研究报告  →", type="primary", use_container_width=True):
        st.session_state.app_state = "idle"
        st.rerun()

    st.stop()

elif st.session_state.app_state == "error":
    # ==================== 错误 ====================
    render_state_card(
        "error",
        f"{st.session_state.last_ticker} 研究任务未完成",
        "系统已停止生成最终结论。请查看错误详情，修复数据、模型或配置问题后再重试。",
    )

    with st.expander("🔍 错误详情", expanded=False):
        st.code(st.session_state.error_detail, language="text")

    with st.expander("📜 运行日志", expanded=False):
        st.code("\n".join(st.session_state.analysis_log), language="text")

    if st.button("返回并重新配置  →", use_container_width=True):
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
    render_empty_state()
    render_legal_footer()
    st.stop()

if not report_path.exists():
    st.warning("报告文件不存在，可能已被删除。")
    st.session_state.current_report = None
    st.stop()

md = report_path.read_text(encoding="utf-8")
sections = parse_sections(md)
info = extract_info(sections)  # Legacy Markdown report compatibility.
decision_path = report_path.with_name("decision.json")
if decision_path.exists():
    try:
        from tradingagents.report_artifacts import (
            dashboard_summary_from_artifact,
            load_decision_artifact,
        )

        artifact = load_decision_artifact(decision_path)
        typed_summary = dashboard_summary_from_artifact(artifact)
        # Legacy v1 artifacts do not contain a final action; preserve the
        # Trader action extracted from old Markdown only for that compatibility path.
        if typed_summary["action"] is None:
            typed_summary["action"] = info["action"]
        info.update(typed_summary)
    except (OSError, ValueError, TypeError) as exc:
        st.warning(f"结构化决策文件无效，已回退为 Markdown 展示：{exc}")

ticker_display = report_meta["ticker"]
date_display = report_meta["date"]

render_report_hero(ticker_display, date_display, info["signal"])

tone_map = {
    "buy": "green",
    "sell": "red",
    "hold": "amber",
    "neutral": "violet",
}
decision_tone = tone_map[signal_tone(info["signal"])]
risk_text = str(info.get("risk_validation") or "N/A")
risk_tone = "green" if risk_text.upper() in {"PASS", "PASSED", "APPROVED"} else "amber"
render_metric_grid([
    {
        "label": "最终评级",
        "value": info.get("rating") or "N/A",
        "hint": "Portfolio Manager + Hard Risk",
        "tone": decision_tone,
    },
    {
        "label": "交易建议",
        "value": info.get("action") or "N/A",
        "hint": "Advisory action",
        "tone": decision_tone,
    },
    {
        "label": "目标价",
        "value": f"${info['price']}" if info.get("price") not in {None, "N/A"} else "N/A",
        "hint": "Model-derived target",
        "tone": "violet",
    },
    {
        "label": "止损位",
        "value": f"${info['stop']}" if info.get("stop") not in {None, "N/A"} else "N/A",
        "hint": "Deterministic risk input",
        "tone": "red",
    },
    {
        "label": "硬风控",
        "value": risk_text,
        "hint": "Non-LLM validation gate",
        "tone": risk_tone,
    },
])

render_section_head(
    "Decision pipeline",
    "多智能体研究链路",
    "四类研究输入 → 多空辩论 → 交易提案 → 风险争论 → 硬风控",
)
completed_report_stages = {
    key for _, _, key in STAGES if sections.get(key, "").strip()
}
render_stage_rail(STAGES, completed_report_stages)

with st.expander("查看12个Agent角色与系统边界", expanded=False):
    render_agent_grid(AGENT_ROLES)
    st.caption(
        "Portfolio Manager 之后由非 LLM 的 Hard Risk Engine 执行确定性约束；"
        "该组件是代码风控闸门，不计入 12 个 Agent。"
    )

render_section_head(
    "Research workspace",
    "完整研究报告",
    "先读最终决策，再按需下钻研究、辩论、风险和证据",
)


def render_report_section(key: str, title: str, *, expanded: bool = False) -> None:
    content = sections.get(key, "").strip()
    if content:
        with st.expander(title, expanded=expanded):
            # Streamlit treats paired dollar signs as LaTeX delimiters.  A
            # financial report contains many currency values such as $310, so
            # escape only dollar signs immediately followed by a digit.  The
            # stored/downloaded Markdown remains unchanged.
            display_content = re.sub(r"(?<!\\)\$(?=\d)", r"\\$", content)
            st.markdown(display_content)
    else:
        with st.expander(f"{title} · 暂无内容", expanded=False):
            st.caption("当前报告没有生成这一部分。")


overview_tab, research_tab, debate_tab, risk_tab = st.tabs([
    "决策总览",
    "四维研究",
    "辩论与提案",
    "风险与证据",
])

with overview_tab:
    render_report_section("final_trade_decision", "最终风险约束决策", expanded=True)

with research_tab:
    render_report_section("market_report", "市场与技术面", expanded=True)
    render_report_section("fundamentals_report", "基本面与财务")
    render_report_section("news_report", "新闻与事件")
    render_report_section("sentiment_report", "市场情绪与社媒")

with debate_tab:
    render_report_section("investment_plan", "多空研究辩论与研究经理结论", expanded=True)
    render_report_section("trader_investment_plan", "交易员执行提案")

with risk_tab:
    render_report_section("risk_assessment", "三类风险分析师辩论", expanded=True)
    render_report_section("evidence_chain", "工具证据链与数据来源")

# 底部操作
render_section_head("Report actions", "报告操作", "导出Markdown或查看本地审计文件")
col1, col2, col3 = st.columns(3)
with col1:
    report_dir_to_open = report_path.parent
    if os.name == "nt" and st.button("打开本地报告目录", use_container_width=True):
        os.startfile(str(report_dir_to_open))
with col2:
    st.download_button(
        "下载Markdown报告",
        data=md,
        file_name=f"{ticker_display}_{date_display}_report.md",
        mime="text/markdown",
        use_container_width=True,
    )
with col3:
    # 清除 current_report 后让侧边栏历史选择器接管。
    if st.session_state.current_report is not None:
        if st.button("返回历史研究库", use_container_width=True):
            st.session_state.current_report = None
            st.rerun()
    else:
        st.button("当前已在研究库", disabled=True, use_container_width=True)

render_legal_footer()
