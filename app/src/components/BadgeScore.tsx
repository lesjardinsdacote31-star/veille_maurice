interface Props {
  score: number | null
}

export function BadgeScore({ score }: Props) {
  if (score === null) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-700 px-2.5 py-1 text-sm font-medium text-slate-200">
        Non noté
      </span>
    )
  }

  const couleur =
    score >= 8
      ? 'bg-emerald-600 text-white'
      : score >= 6
        ? 'bg-amber-500 text-white'
        : 'bg-slate-600 text-white'

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-sm font-semibold ${couleur}`}>
      {score.toFixed(1)}/10
    </span>
  )
}
