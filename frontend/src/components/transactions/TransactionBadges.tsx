import Badge from '../ui/Badge'
import type { ResolutionSource } from '../../types/transaction'

const SOURCE_LABELS: Record<ResolutionSource, string> = {
  RULE: 'Rule',
  EXACT_MATCH: 'Exact Match',
  ALIAS_MATCH: 'Alias Match',
  SIMILARITY_MATCH: 'Similarity Match',
  AI_PREDICTION: 'AI Predicted',
  MANUAL: 'Manual',
  AI_FAILED: 'AI Failed',
}

export function ResolutionSourceBadge({ source }: { source: ResolutionSource | null }) {
  if (!source) return <Badge tone="gray">Unresolved</Badge>
  const tone = source === 'AI_FAILED' ? 'red' : source === 'AI_PREDICTION' ? 'blue' : 'gray'
  return <Badge tone={tone}>{SOURCE_LABELS[source]}</Badge>
}

export function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) return <Badge tone="gray">—</Badge>
  const tone = confidence >= 90 ? 'green' : confidence >= 60 ? 'amber' : 'red'
  return <Badge tone={tone}>{confidence}%</Badge>
}

export function ReviewFlagBadges({
  requiresReview,
  isDuplicate,
}: {
  requiresReview: boolean
  isDuplicate: boolean
}) {
  return (
    <div className="flex gap-1">
      {requiresReview && <Badge tone="amber">Needs Review</Badge>}
      {isDuplicate && <Badge tone="red">Duplicate</Badge>}
    </div>
  )
}
