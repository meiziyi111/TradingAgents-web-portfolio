import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity,
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CircleEllipsis,
  Newspaper,
  Scale,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

const icons = {
  market: BarChart3,
  sentiment: Activity,
  news: Newspaper,
  fundamentals: BookOpenCheck,
  research: BrainCircuit,
  trader: Sparkles,
  risk: Scale,
  decision: ShieldCheck,
}

export function StageRail({ stages, states, onSelect, selected }) {
  return (
    <div className="stage-rail" aria-label="分析进度">
      <div className="stage-rail__line" />
      {stages.map((stage, index) => {
        const state = states[stage.id]?.status || 'waiting'
        const Icon = icons[stage.id] || CircleEllipsis
        return (
          <motion.button
            layout
            type="button"
            key={stage.id}
            className={`stage-node stage-node--${state} ${selected === stage.id ? 'is-selected' : ''}`}
            onClick={() => onSelect(stage.id)}
            disabled={state === 'waiting'}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.055 }}
            aria-label={`${stage.label}：${state}`}
          >
            <span className="stage-node__index">{String(index + 1).padStart(2, '0')}</span>
            <span className="stage-node__orb">
              {state === 'done' ? <Check size={17} /> : <Icon size={18} />}
              {state === 'running' ? <span className="stage-node__pulse" /> : null}
            </span>
            <span className="stage-node__text">
              <strong>{stage.label}</strong>
              <small>{state === 'done' ? '已生成' : state === 'running' ? '分析中' : '等待中'}</small>
            </span>
          </motion.button>
        )
      })}
    </div>
  )
}
export function LiveStageHeader({ stage, elapsed }) {
  const Icon = icons[stage?.id] || BrainCircuit
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={stage?.id || 'preparing'}
        className="live-stage"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
      >
        <span className="live-stage__icon"><Icon size={20} /></span>
        <span>
          <small>NOW PROCESSING</small>
          <strong>{stage?.label || '正在建立研究环境'}</strong>
        </span>
        <span className="live-stage__elapsed">{elapsed}s</span>
      </motion.div>
    </AnimatePresence>
  )
}
