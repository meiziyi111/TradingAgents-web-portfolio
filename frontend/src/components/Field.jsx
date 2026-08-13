export default function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field__head">
        <span>{label}</span>
        {hint ? <small>{hint}</small> : null}
      </span>
      {children}
    </label>
  )
}
