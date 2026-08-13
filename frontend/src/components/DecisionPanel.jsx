import { motion } from 'framer-motion'
import { ArrowDownToLine, BadgeCheck, CircleDollarSign, Gauge, ShieldCheck, Target } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function valueOr(value, fallback = 'N/A') {
  return value === null || value === undefined || value === '' ? fallback : value
}

export default function DecisionPanel({ report }) {
  if (!report) return null
  const summary = report.summary || {}
  const final = report.sections?.final_trade_decision || ''
  const signal = String(summary.signal || 'N/A').toUpperCase()
  const tone = ['BUY', 'OVERWEIGHT'].includes(signal)
    ? 'positive'
    : ['SELL', 'UNDERWEIGHT'].includes(signal)
      ? 'negative'
      : 'neutral'

  const metrics = [
    { label: '最终评级', value: signal, icon: BadgeCheck },
    { label: '建议动作', value: valueOr(summary.action), icon: Gauge },
    { label: '目标价', value: summary.price === 'N/A' ? 'N/A' : `$${summary.price}`, icon: Target },
    { label: '止损位', value: summary.stop === 'N/A' ? 'N/A' : `$${summary.stop}`, icon: CircleDollarSign },
    { label: '批准仓位', value: valueOr(summary.position_sizing), icon: ShieldCheck },
  ]

  return (
    <motion.section
      className={`decision-panel decision-panel--${tone}`}
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 150, damping: 22 }}
    >
      <div className="decision-panel__glow" />
      <header className="decision-panel__head">
        <div>
          <span className="eyebrow"><ShieldCheck size={15} /> HARD RISK VALIDATED</span>
          <h2>整体结论与建议</h2>
          <p>{report.ticker} · 数据截止 {report.trade_date} · 研究建议，不连接券商执行</p>
        </div>
        <div className="decision-signal">
          <small>FINAL SIGNAL</small>
          <strong>{signal}</strong>
        </div>
      </header>

      <div className="decision-metrics">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div className="decision-metric" key={label}>
            <Icon size={18} />
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <div className="decision-panel__body markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{final}</ReactMarkdown>
      </div>

      <a className="download-link" href={`/api/reports/${report.ticker}/${report.trade_date}/download`}>
        <ArrowDownToLine size={18} /> 下载完整Markdown报告
      </a>
    </motion.section>
  )
}
