/** A 0–100 name-match score with the WARN and PASS thresholds marked. */
export function ScoreBar({ score, warn, pass }: { score: number; warn: number; pass: number }) {
  const tone = score >= pass ? "bg-approved" : score >= warn ? "bg-pending" : "bg-rejected"
  return (
    <div className="w-full max-w-xs" aria-label={`Match score ${score} out of 100`}>
      <div className="relative h-1.5 bg-secondary">
        <div className={`h-1.5 ${tone}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
        {[warn, pass].map((mark) => (
          <span key={mark} className="absolute -top-0.5 h-2.5 w-px bg-foreground/50" style={{ left: `${mark}%` }} aria-hidden />
        ))}
      </div>
      <div className="relative mt-1 h-4 text-[10px] text-muted-foreground">
        <span className="absolute -translate-x-1/2" style={{ left: `${warn}%` }}>{warn}</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${pass}%` }}>{pass}</span>
      </div>
    </div>
  )
}
