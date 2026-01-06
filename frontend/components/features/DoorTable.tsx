'use client'

import { useState, useMemo } from 'react'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableEmpty,
} from '@/components/ui/Table'
import { Badge, FireRatingBadge, ConfidenceBadge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'

export interface DoorItem {
  id: string
  door_number: string
  room: string
  type: string
  fire_rating: string | null
  width_m: number
  height_m: number
  category: 'T90' | 'T30' | 'DSS' | 'Standard' | 'Unknown'
  confidence: number
  page_number?: number
  raw_values?: Record<string, string>
}

export interface DoorTableProps {
  items: DoorItem[]
  showAuditInfo?: boolean
}

type SortField = 'door_number' | 'room' | 'width_m' | 'height_m' | 'category' | 'confidence'
type SortDirection = 'asc' | 'desc'

export function DoorTable({ items, showAuditInfo = false }: DoorTableProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<SortField>('door_number')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const filteredAndSortedItems = useMemo(() => {
    let result = [...items]

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(item =>
        item.door_number.toLowerCase().includes(query) ||
        item.room.toLowerCase().includes(query) ||
        item.type.toLowerCase().includes(query)
      )
    }

    // Apply category filter
    if (categoryFilter) {
      result = result.filter(item => item.category === categoryFilter)
    }

    // Apply sorting
    result.sort((a, b) => {
      let aVal: string | number = a[sortField] ?? ''
      let bVal: string | number = b[sortField] ?? ''

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
      }

      aVal = String(aVal).toLowerCase()
      bVal = String(bVal).toLowerCase()
      if (sortDirection === 'asc') {
        return aVal.localeCompare(bVal)
      }
      return bVal.localeCompare(aVal)
    })

    return result
  }, [items, searchQuery, categoryFilter, sortField, sortDirection])

  const categories = useMemo(() => {
    const counts: Record<string, number> = {}
    items.forEach(item => {
      counts[item.category] = (counts[item.category] || 0) + 1
    })
    return counts
  }, [items])

  if (items.length === 0) {
    return (
      <TableEmpty
        icon={
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" />
          </svg>
        }
        title="No doors found"
        description="Upload a door schedule to extract door data"
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px] max-w-sm">
          <Input
            placeholder="Search Door ID, Room..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-text-secondary">Fire Rating:</span>
          <div className="flex gap-1">
            <button
              onClick={() => setCategoryFilter(null)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                categoryFilter === null
                  ? 'bg-accent-blue text-white'
                  : 'bg-bg-hover text-text-secondary hover:text-text-primary'
              }`}
            >
              All ({items.length})
            </button>
            {Object.entries(categories).map(([category, count]) => (
              <button
                key={category}
                onClick={() => setCategoryFilter(category)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  categoryFilter === category
                    ? 'bg-accent-blue text-white'
                    : 'bg-bg-hover text-text-secondary hover:text-text-primary'
                }`}
              >
                {category} ({count})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                sortable
                sorted={sortField === 'door_number' ? sortDirection : null}
                onSort={() => handleSort('door_number')}
              >
                Door ID
              </TableHead>
              <TableHead
                sortable
                sorted={sortField === 'room' ? sortDirection : null}
                onSort={() => handleSort('room')}
              >
                Room
              </TableHead>
              <TableHead>Type</TableHead>
              <TableHead
                sortable
                sorted={sortField === 'width_m' ? sortDirection : null}
                onSort={() => handleSort('width_m')}
              >
                Width
              </TableHead>
              <TableHead
                sortable
                sorted={sortField === 'height_m' ? sortDirection : null}
                onSort={() => handleSort('height_m')}
              >
                Height
              </TableHead>
              <TableHead
                sortable
                sorted={sortField === 'category' ? sortDirection : null}
                onSort={() => handleSort('category')}
              >
                Rating
              </TableHead>
              {showAuditInfo && (
                <TableHead
                  sortable
                  sorted={sortField === 'confidence' ? sortDirection : null}
                  onSort={() => handleSort('confidence')}
                >
                  Conf.
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAndSortedItems.map((item) => (
              <TableRow key={item.id} isClickable>
                <TableCell className="font-mono text-sm">{item.door_number}</TableCell>
                <TableCell>{item.room || '-'}</TableCell>
                <TableCell>
                  <Badge variant="default" size="sm">{item.type || 'Standard'}</Badge>
                </TableCell>
                <TableCell className="font-mono">{item.width_m.toFixed(2)} m</TableCell>
                <TableCell className="font-mono">{item.height_m.toFixed(2)} m</TableCell>
                <TableCell>
                  <FireRatingBadge rating={item.fire_rating} size="sm" />
                </TableCell>
                {showAuditInfo && (
                  <TableCell>
                    <ConfidenceBadge confidence={item.confidence} />
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Results count */}
      <div className="text-sm text-text-muted">
        Showing {filteredAndSortedItems.length} of {items.length} doors
      </div>
    </div>
  )
}
