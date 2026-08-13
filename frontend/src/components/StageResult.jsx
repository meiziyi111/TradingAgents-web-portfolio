import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, CheckCircle2, LoaderCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function StageResult({ stage, state, expanded, onToggle }) {
  const running = state?.status === 'running'
  const done = state?.status === 'done'
  if (!running && !done) return null

  return (
    <motion.article
      layout
      className={`result-card result-card--${state.status}`}
      initial={{ opacity: 0, y: 28, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 180, damping: 23 }}
    >
      <button className="result-card__head" type="button" onClick={onToggle} disabled={running}>
        <span className="result-card__status">
          {running ? <LoaderCircle className="spin" size={20} /> : <CheckCircle2 size={20} />}
        </span>
        <span className="result-card__title">
          <small>STAGE {String(stage.index).padStart(2, '0')} · {stage.role}</small>
          <strong>{stage.label}</strong>
        </span>
        {done ? (
          <span className="result-card__ready">内容已生成</span>
        ) : (
          <span className="result-card__typing"><i /><i /><i /></span>
        )}
        {done ? <ChevronDown className={expanded ? 'rotate' : ''} size={18} /> : null}
      </button>
      <AnimatePresence initial={false}>
        {done && expanded ? (
          <motion.div
            className="result-card__content markdown"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.content || '本阶段已完成。'}</ReactMarkdown>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.article>
  )
}
