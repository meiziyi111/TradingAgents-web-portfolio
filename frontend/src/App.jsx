import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  History,
  Layers3,
  Leaf,
  Orbit,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  WalletCards,
} from 'lucide-react'
import Field from './components/Field'
import { LiveStageHeader, StageRail } from './components/StageRail'
import StageResult from './components/StageResult'
import DecisionPanel from './components/DecisionPanel'

const fallbackStages = [
  { id: 'market', label: '市场结构', role: 'Market Analyst', index: 1 },
  { id: 'sentiment', label: '市场情绪', role: 'Sentiment Analyst', index: 2 },
  { id: 'news', label: '新闻事件', role: 'News Analyst', index: 3 },
  { id: 'fundamentals', label: '基本面', role: 'Fundamentals Analyst', index: 4 },
  { id: 'research', label: '多空辩论', role: 'Research Team', index: 5 },
  { id: 'trader', label: '交易提案', role: 'Trader', index: 6 },
  { id: 'risk', label: '风险委员会', role: 'Risk Analysts', index: 7 },
  { id: 'decision', label: '最终决策', role: 'Portfolio Manager + Hard Risk', index: 8 },
]

const initialForm = {
  ticker: 'NVDA',
  trade_date: new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10),
  current_price: '',
  portfolio_value: '100000',
  cash: '100000',
  current_position: '0',
  max_position_pct: '10',
  risk_budget_pct: '1',
}

function createStageState(stages) {
  return Object.fromEntries(stages.map((stage) => [stage.id, { status: 'waiting', content: '' }]))
}

function parseNumber(value, nullable = false) {
  if (nullable && String(value).trim() === '') return null
  return Number(value)
}

async function readEventStream(response, onEvent) {
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const payload = await response.json()
      detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    } catch {
      // Keep the HTTP fallback when the body is not JSON.
    }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('浏览器未收到流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line))
    }
    if (done) break
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}

function Brand() {
  return (
    <a className="brand" href="#top" aria-label="TradingAgents首页">
      <span className="brand__mark"><Orbit size={21} /></span>
      <span><strong>TradingAgents</strong><small>INTELLIGENT RESEARCH</small></span>
    </a>
  )
}

function NumberInput({ value, onChange, min = 0, max, step = 1, ...props }) {
  return (
    <input
      type="number"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      min={min}
      max={max}
      step={step}
      {...props}
    />
  )
}

function SetupView({ form, setForm, onStart, onDemo, recentReports, onOpenReport, error }) {
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))
  const exposure = Number(form.portfolio_value) > 0
    ? Math.round((Number(form.current_position) / Number(form.portfolio_value)) * 1000) / 10
    : 0

  return (
    <motion.main
      className="setup-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, y: -12 }}
    >
      <section className="setup-intro">
        <motion.div
          className="setup-intro__copy"
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="eyebrow"><Sparkles size={15} /> MULTI-AGENT INVESTMENT RESEARCH</span>
          <h1>从你的持仓出发，<br /><em>让研究逐步发生。</em></h1>
          <p>
            输入标的与组合约束。四类分析师将并行获取证据，多空团队进行辩论，
            最终由组合经理与确定性硬风控共同给出建议。
          </p>
          <div className="trust-row">
            <span><ShieldCheck size={16} /> 非执行型建议</span>
            <span><Clock3 size={16} /> Point-in-Time边界</span>
            <span><Layers3 size={16} /> 8阶段实时生成</span>
          </div>
        </motion.div>

        <div className="ambient-orbit" aria-hidden="true">
          <div className="ambient-orbit__halo halo-a" />
          <div className="ambient-orbit__halo halo-b" />
          {[0, 1, 2, 3, 4, 5, 6, 7].map((node) => <i style={{ '--i': node }} key={node} />)}
          <span><Leaf size={29} /><small>RESEARCH<br />FLOW</small></span>
        </div>
      </section>

      <motion.section
        className="setup-card"
        initial={{ opacity: 0, y: 35 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18, duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="setup-card__head">
          <div>
            <span>01 · RESEARCH BRIEF</span>
            <h2>设置本次研究任务</h2>
          </div>
          <div className="setup-card__step"><strong>1</strong><span>/ 2</span></div>
        </div>

        <form onSubmit={onStart}>
          <div className="form-section">
            <div className="form-section__title">
              <BarChart3 size={18} />
              <div><strong>研究标的</strong><small>确定分析对象与数据截止时间</small></div>
            </div>
            <div className="form-grid form-grid--two">
              <Field label="股票代码" hint="Ticker">
                <div className="input-shell input-shell--ticker">
                  <span>US</span>
                  <input
                    value={form.ticker}
                    onChange={(event) => update('ticker', event.target.value.toUpperCase())}
                    maxLength={15}
                    required
                    placeholder="NVDA"
                    aria-label="股票代码"
                  />
                </div>
              </Field>
              <Field label="分析日期" hint="As-of date">
                <div className="input-shell">
                  <CalendarDays size={17} />
                  <input type="date" value={form.trade_date} onChange={(event) => update('trade_date', event.target.value)} required aria-label="分析日期" />
                </div>
              </Field>
            </div>
          </div>

          <div className="form-section">
            <div className="form-section__title">
              <WalletCards size={18} />
              <div><strong>组合与持仓</strong><small>用于仓位、现金和风险预算约束</small></div>
              <span className="exposure-badge">当前单票敞口 {exposure}%</span>
            </div>
            <div className="form-grid form-grid--four">
              <Field label="组合总资产" hint="USD">
                <div className="input-shell"><CircleDollarSign size={17} /><NumberInput value={form.portfolio_value} onChange={(value) => update('portfolio_value', value)} min={0} step={1000} required aria-label="组合总资产" /></div>
              </Field>
              <Field label="可用现金" hint="USD">
                <div className="input-shell"><CircleDollarSign size={17} /><NumberInput value={form.cash} onChange={(value) => update('cash', value)} step={1000} required aria-label="可用现金" /></div>
              </Field>
              <Field label="当前持仓市值" hint="USD">
                <div className="input-shell"><CircleDollarSign size={17} /><NumberInput value={form.current_position} onChange={(value) => update('current_position', value)} step={1000} required aria-label="当前持仓市值" /></div>
              </Field>
              <Field label="参考现价" hint="可选">
                <div className="input-shell"><CircleDollarSign size={17} /><NumberInput value={form.current_price} onChange={(value) => update('current_price', value)} step={0.01} placeholder="自动获取" aria-label="参考现价" /></div>
              </Field>
            </div>
          </div>

          <div className="form-section">
            <div className="form-section__title">
              <ShieldCheck size={18} />
              <div><strong>风险约束</strong><small>硬风控将以此限制最终建议</small></div>
            </div>
            <div className="range-grid">
              <Field label="单票仓位上限" hint={`${form.max_position_pct}%`}>
                <input className="range" type="range" min="1" max="100" value={form.max_position_pct} onChange={(event) => update('max_position_pct', event.target.value)} />
              </Field>
              <Field label="单笔风险预算" hint={`${form.risk_budget_pct}%`}>
                <input className="range" type="range" min="0.5" max="20" step="0.5" value={form.risk_budget_pct} onChange={(event) => update('risk_budget_pct', event.target.value)} />
              </Field>
            </div>
          </div>

          {error ? <div className="form-error" role="alert">{error}</div> : null}

          <div className="form-actions">
            <div className="form-actions__note"><ShieldCheck size={16} /> 所有持仓数据仅用于本次本地研究，不会连接券商。</div>
            <button className="button button--ghost" type="button" onClick={onDemo}><Play size={17} /> 观看历史动态演示</button>
            <button className="button button--primary" type="submit">开始智能研究 <ArrowRight size={18} /></button>
          </div>
        </form>
      </motion.section>

      {recentReports.length ? (
        <section className="recent-section">
          <div className="recent-section__head"><span><History size={16} /> 最近完成的研究</span><small>读取本地已保存报告</small></div>
          <div className="recent-grid">
            {recentReports.slice(0, 4).map((report) => (
              <button type="button" key={`${report.ticker}-${report.trade_date}`} onClick={() => onOpenReport(report)}>
                <span>{report.ticker}</span><small>{report.trade_date}</small><ArrowRight size={15} />
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </motion.main>
  )
}

function ResearchView({ ticker, tradeDate, stages, stageStates, selected, setSelected, expanded, toggleExpanded, elapsed, report, error, demo, onReset }) {
  const completedCount = Object.values(stageStates).filter((item) => item.status === 'done').length
  const active = stages.find((stage) => stageStates[stage.id]?.status === 'running')
  const progress = Math.round((completedCount / stages.length) * 100)
  const resultsRef = useRef(null)

  useEffect(() => {
    if (completedCount > 0) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [completedCount])

  return (
    <motion.main className="research-page" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <section className="research-hero">
        <div className="research-hero__top">
          <div>
            <span className="eyebrow"><Sparkles size={15} /> {demo ? 'HISTORY REPLAY' : 'LIVE RESEARCH SESSION'}</span>
            <h1>{ticker}<em> 正在形成观点</em></h1>
            <p>数据截止 {tradeDate} · 每个Agent阶段完成后，结果会立即出现在下方。</p>
          </div>
          <div className="progress-orb" style={{ '--progress': `${progress * 3.6}deg` }}>
            <span><strong>{progress}%</strong><small>COMPLETE</small></span>
          </div>
        </div>
        <LiveStageHeader stage={active} elapsed={elapsed} />
      </section>

      <section className="flow-section">
        <div className="section-head">
          <div><span>02 · LIVE ORCHESTRATION</span><h2>研究正在逐步推进</h2></div>
          <p>{completedCount} / {stages.length} 阶段已完成</p>
        </div>
        <StageRail stages={stages} states={stageStates} onSelect={setSelected} selected={selected} />
      </section>

      <section className="results-section" ref={resultsRef}>
        <div className="section-head">
          <div><span>03 · GENERATED INSIGHTS</span><h2>逐阶段研究结果</h2></div>
          <p>新完成的内容会自动展开；你可以随时回看前序阶段。</p>
        </div>
        <div className="result-stack">
          {stages.map((stage) => (
            <StageResult
              key={stage.id}
              stage={stage}
              state={stageStates[stage.id]}
              expanded={expanded.has(stage.id)}
              onToggle={() => toggleExpanded(stage.id)}
            />
          ))}
          {!completedCount && !error ? (
            <div className="await-card"><span className="await-card__wave"><i /><i /><i /><i /></span><strong>正在连接研究Agent</strong><p>第一份分析完成后会直接出现在这里。</p></div>
          ) : null}
        </div>
      </section>

      <DecisionPanel report={report} />

      {error ? (
        <section className="error-panel" role="alert">
          <strong>本次研究未完成</strong><p>{error}</p><button className="button button--primary" type="button" onClick={onReset}><RotateCcw size={17} /> 返回重新设置</button>
        </section>
      ) : null}

      {report ? (
        <div className="complete-actions">
          <span><CheckCircle2 size={17} /> 报告、结构化决策与审计记录已保存</span>
          <button className="button button--ghost" type="button" onClick={onReset}><RotateCcw size={17} /> 发起新的研究</button>
        </div>
      ) : null}
    </motion.main>
  )
}

export default function App() {
  const [view, setView] = useState('setup')
  const [form, setForm] = useState(initialForm)
  const [stages, setStages] = useState(fallbackStages)
  const [stageStates, setStageStates] = useState(() => createStageState(fallbackStages))
  const [expanded, setExpanded] = useState(() => new Set())
  const [selected, setSelected] = useState(null)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [runStartedAt, setRunStartedAt] = useState(null)
  const [recentReports, setRecentReports] = useState([])
  const [demo, setDemo] = useState(false)

  useEffect(() => {
    fetch('/api/reports').then((response) => response.json()).then((payload) => setRecentReports(payload.reports || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!runStartedAt || report || error) return undefined
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - runStartedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [runStartedAt, report, error])

  const ticker = report?.ticker || form.ticker
  const tradeDate = report?.trade_date || form.trade_date

  const toggleExpanded = (stageId) => {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(stageId)) next.delete(stageId)
      else next.add(stageId)
      return next
    })
  }

  const handleEvent = (event) => {
    if (event.type === 'run_started') {
      if (event.stages?.length) {
        setStages(event.stages)
        setStageStates(createStageState(event.stages))
      }
      return
    }
    if (event.type === 'stage_started') {
      const stageId = event.stage.id
      setSelected(stageId)
      setStageStates((current) => ({ ...current, [stageId]: { ...(current[stageId] || {}), status: 'running' } }))
      return
    }
    if (event.type === 'stage_completed') {
      setSelected(event.stage_id)
      setStageStates((current) => ({
        ...current,
        [event.stage_id]: { status: 'done', content: event.content || '', structured: event.structured || null },
      }))
      setExpanded(new Set([event.stage_id]))
      return
    }
    if (event.type === 'analysis_completed') {
      setReport(event.report)
      // The dedicated final panel owns the complete decision presentation.
      // Keep the stage card compact to avoid showing the same long text twice.
      setExpanded(new Set())
      return
    }
    if (event.type === 'analysis_error') {
      setError(event.message || '研究过程中发生未知错误')
    }
  }

  const validate = () => {
    const portfolio = Number(form.portfolio_value)
    const cash = Number(form.cash)
    const position = Number(form.current_position)
    if (!form.ticker.trim()) return '请输入股票代码。'
    if (!form.trade_date) return '请选择分析日期。'
    if (!Number.isFinite(portfolio) || portfolio <= 0) return '组合总资产必须大于0。'
    if (cash < 0 || position < 0) return '现金和持仓不能为负数。'
    if (cash > portfolio) return '可用现金不能超过组合总资产。'
    if (position > portfolio) return '当前持仓不能超过组合总资产。'
    if (cash + position > portfolio * 1.001) return '现金与当前持仓合计不能超过组合总资产。'
    return ''
  }

  const runStream = async (url, payload, isDemo = false) => {
    setDemo(isDemo)
    setError('')
    setReport(null)
    setExpanded(new Set())
    setSelected(null)
    setElapsed(0)
    setRunStartedAt(Date.now())
    setStageStates(createStageState(stages))
    setView('research')
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload ? JSON.stringify(payload) : undefined,
      })
      await readEventStream(response, handleEvent)
    } catch (streamError) {
      setError(streamError.message || '无法连接分析服务')
    }
  }

  const startResearch = (event) => {
    event.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    runStream('/api/analysis/stream', {
      ticker: form.ticker.trim().toUpperCase(),
      trade_date: form.trade_date,
      current_price: Number(form.current_price) > 0 ? parseNumber(form.current_price) : null,
      portfolio_value: parseNumber(form.portfolio_value),
      cash: parseNumber(form.cash),
      current_position: parseNumber(form.current_position),
      max_position_pct: parseNumber(form.max_position_pct),
      risk_budget_pct: parseNumber(form.risk_budget_pct),
    })
  }

  const openSavedReport = async ({ ticker: savedTicker, trade_date: savedDate }) => {
    setError('')
    try {
      const response = await fetch(`/api/reports/${savedTicker}/${savedDate}`)
      if (!response.ok) throw new Error('无法读取历史报告')
      const saved = await response.json()
      setForm((current) => ({ ...current, ticker: savedTicker, trade_date: savedDate }))
      setReport(saved)
      setDemo(true)
      setStageStates(Object.fromEntries(stages.map((stage) => [stage.id, {
        status: 'done',
        content: saved.sections?.[{
          market: 'market_report', sentiment: 'sentiment_report', news: 'news_report', fundamentals: 'fundamentals_report', research: 'investment_plan', trader: 'trader_investment_plan', risk: 'risk_assessment', decision: 'final_trade_decision',
        }[stage.id]] || '',
      }])))
      setExpanded(new Set())
      setView('research')
    } catch (loadError) {
      setError(loadError.message)
    }
  }

  const reset = () => {
    setView('setup')
    setReport(null)
    setError('')
    setDemo(false)
    setRunStartedAt(null)
    setElapsed(0)
    setStageStates(createStageState(stages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app-shell" id="top">
      <div className="aurora aurora--one" /><div className="aurora aurora--two" />
      <header className="topbar">
        <Brand />
        <div className="topbar__status"><i /> ADVISORY SYSTEM ONLINE</div>
        {view === 'research' ? <button type="button" className="topbar__back" onClick={reset}>返回设置</button> : null}
      </header>
      <AnimatePresence mode="wait">
        {view === 'setup' ? (
          <SetupView key="setup" form={form} setForm={setForm} onStart={startResearch} onDemo={() => runStream('/api/analysis/demo-stream', null, true)} recentReports={recentReports} onOpenReport={openSavedReport} error={error} />
        ) : (
          <ResearchView key="research" ticker={ticker} tradeDate={tradeDate} stages={stages} stageStates={stageStates} selected={selected} setSelected={setSelected} expanded={expanded} toggleExpanded={toggleExpanded} elapsed={elapsed} report={report} error={error} demo={demo} onReset={reset} />
        )}
      </AnimatePresence>
      <footer className="footer"><span>TradingAgents Portfolio Demo</span><span>Research advisory only · Execution disabled</span></footer>
    </div>
  )
}
