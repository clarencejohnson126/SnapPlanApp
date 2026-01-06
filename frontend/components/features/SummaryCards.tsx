'use client'

import { Card } from '@/components/ui/Card'

interface SummaryStat {
  label: string
  value: string | number
  icon: string
  subtext?: string
}

interface SummaryCardsProps {
  stats: SummaryStat[]
}

export function SummaryCards({ stats }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {stats.map((stat, index) => (
        <Card key={index} variant="interactive" padding="md">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl">{stat.icon}</span>
            <span className="text-sm text-text-secondary">{stat.label}</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{stat.value}</p>
          {stat.subtext && (
            <p className="text-xs text-text-muted mt-1">{stat.subtext}</p>
          )}
        </Card>
      ))}
    </div>
  )
}

// Fire rating breakdown chart (horizontal bars)
interface FireRatingData {
  rating: string
  count: number
  color: string
}

interface FireRatingChartProps {
  data: FireRatingData[]
  total: number
}

export function FireRatingChart({ data, total }: FireRatingChartProps) {
  const sortedData = [...data].sort((a, b) => b.count - a.count)
  const maxCount = Math.max(...data.map(d => d.count))

  return (
    <div className="space-y-3">
      {sortedData.map((item) => (
        <div key={item.rating} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-text-primary font-medium">{item.rating}</span>
            <span className="text-text-secondary">{item.count}</span>
          </div>
          <div className="h-2 bg-bg-hover rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(item.count / maxCount) * 100}%`,
                backgroundColor: item.color,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

// Dimension breakdown (for widths/heights)
interface DimensionData {
  dimension: string
  count: number
}

interface DimensionBreakdownProps {
  title: string
  data: DimensionData[]
  unit?: string
}

export function DimensionBreakdown({ title, data, unit = 'm' }: DimensionBreakdownProps) {
  const sortedData = [...data].sort((a, b) => b.count - a.count)

  return (
    <div>
      <h4 className="text-sm font-medium text-text-secondary mb-3">{title}</h4>
      <div className="space-y-2">
        {sortedData.map((item) => (
          <div key={item.dimension} className="flex justify-between text-sm">
            <span className="text-text-primary font-mono">{item.dimension} {unit}</span>
            <span className="text-text-muted">{item.count} doors</span>
          </div>
        ))}
      </div>
    </div>
  )
}
