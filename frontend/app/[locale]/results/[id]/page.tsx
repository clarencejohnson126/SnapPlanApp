'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'

// Types for room/flooring data
interface RoomData {
  id: string
  room_number: string
  room_type: string
  area_m2: number
  perimeter_m?: number
  ceiling_height_m?: number
  floor_type?: string
}

interface DoorData {
  id: string
  door_number: string
  room: string
  type: string
  fire_rating: string | null
  width_m: number
  height_m: number
  category: string
}

// API response structures
interface FireRatingSummary {
  total_fire_rated: number
  count_t90: number
  count_t30: number
  count_dss: number
  count_standard: number
  t90_doors: string[]
  t30_doors: string[]
}

interface DoorsApiResponse {
  total_doors: number
  doors: Array<{
    door_id: string
    door_label: string | null
    page_number: number
    width_m: number | null
    arc_radius_px: number | null
    fire_rating: string | null
    fire_category: string | null
    confidence: number
    detection_method: string
  }>
  by_width: Record<string, number>
  by_fire_rating: FireRatingSummary
}

interface FlooringApiResponse {
  total_rooms: number
  total_area_m2: number
  rooms: Array<{
    room_id: string
    room_name: string | null
    room_type: string | null
    area_m2: number | null
    perimeter_m: number | null
    ceiling_height_m: number | null
    page_number: number
    confidence: number
  }>
  by_room_type: Record<string, number>
}

interface DrywallApiResponse {
  summary: {
    total_wall_length_m: number
    total_drywall_area_m2: number
    average_wall_height_m: number
  }
  items?: Array<{
    wall_length_m: number
    wall_height_m: number
    drywall_area_m2: number
    wall_segment_count: number
  }>
}

interface ExtractionResult {
  doors?: DoorsApiResponse
  flooring?: FlooringApiResponse
  drywall?: DrywallApiResponse
  // Legacy format support
  rooms?: RoomData[]
  items?: DoorData[]
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  const t = useTranslations()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<'overview' | 'doors' | 'areas' | 'export'>('overview')
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [fileName, setFileName] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load data from sessionStorage
  useEffect(() => {
    const storedResult = sessionStorage.getItem('analysisResult')
    const storedFileName = sessionStorage.getItem('fileName')

    if (storedResult) {
      try {
        const parsed = JSON.parse(storedResult)
        console.log('Loaded extraction result:', parsed)
        console.log('Has doors:', !!parsed?.doors, 'total:', parsed?.doors?.total_doors)
        console.log('Has flooring:', !!parsed?.flooring, 'total rooms:', parsed?.flooring?.total_rooms)
        setResult(parsed)
      } catch (e) {
        console.error('Failed to parse stored result:', e)
        setError('Failed to load extraction results')
      }
    } else {
      setError('No extraction results found. Please upload a file first.')
    }

    if (storedFileName) {
      setFileName(storedFileName.replace('.pdf', ''))
    }

    setIsLoading(false)
  }, [])

  // Get data from result - handle both new API format and legacy format
  const rooms: RoomData[] = useMemo(() => {
    // New API format: result.flooring.rooms
    if (result?.flooring?.rooms) {
      return result.flooring.rooms.map((r, idx) => ({
        id: r.room_id || `room-${idx}`,
        room_number: r.room_id || `Room ${idx + 1}`,
        room_type: r.room_type || 'Unknown',
        area_m2: r.area_m2 || 0,
        perimeter_m: r.perimeter_m || undefined,
        ceiling_height_m: r.ceiling_height_m || undefined,
        floor_type: r.room_type || undefined,
      }))
    }
    // Legacy format: result.rooms
    return result?.rooms || []
  }, [result])

  const doors: DoorData[] = useMemo(() => {
    // New API format: result.doors.doors
    if (result?.doors?.doors) {
      return result.doors.doors.map((d, idx) => ({
        id: d.door_id || `door-${idx}`,
        door_number: d.door_label || d.door_id || `Door ${idx + 1}`,
        room: '-',
        type: d.detection_method || 'detected',
        fire_rating: d.fire_rating || null,
        width_m: d.width_m || 0,
        height_m: 2.1, // Default height
        category: d.fire_category || 'Standard',
      }))
    }
    // Legacy format: result.items
    return result?.items || []
  }, [result])

  // Get fire rating summary from API
  const fireRatingSummary = result?.doors?.by_fire_rating

  // Get drywall data
  const drywallData = result?.drywall?.summary
  const drywallArea = drywallData?.total_drywall_area_m2 || 0
  const drywallWallLength = drywallData?.total_wall_length_m || 0
  const drywallWallHeight = drywallData?.average_wall_height_m || 2.6

  // Get summary totals from API response or calculate
  const totalArea = useMemo(() => {
    // New API format has total_area_m2
    if (result?.flooring?.total_area_m2) {
      return result.flooring.total_area_m2
    }
    return rooms.reduce((sum, room) => sum + room.area_m2, 0)
  }, [result, rooms])

  const totalPerimeter = useMemo(() =>
    rooms.reduce((sum, room) => sum + (room.perimeter_m || 0), 0), [rooms])

  // Group rooms by type
  const roomsByType = useMemo(() => {
    const grouped: Record<string, { count: number; area: number }> = {}
    rooms.forEach(room => {
      if (!grouped[room.room_type]) {
        grouped[room.room_type] = { count: 0, area: 0 }
      }
      grouped[room.room_type].count++
      grouped[room.room_type].area += room.area_m2
    })
    return grouped
  }, [rooms])

  // Door stats
  const doorStats = useMemo(() => {
    const stats = { t90: 0, t30: 0, dss: 0, standard: 0 }
    doors.forEach(door => {
      if (door.category === 'T90') stats.t90++
      else if (door.category === 'T30') stats.t30++
      else if (door.category === 'DSS') stats.dss++
      else stats.standard++
    })
    return stats
  }, [doors])

  const handleExport = () => {
    if (!result) return
    const data = { rooms, doors, summary: { totalArea, totalRooms: rooms.length, totalDoors: doors.length } }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${fileName || 'extraction'}_result.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg-primary">
        <div className="w-12 h-12 border-4 border-accent-teal border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-bg-card rounded-xl p-8 text-center border border-white/5">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="text-text-secondary mb-4">{error}</p>
          <button
            onClick={() => router.push('/upload')}
            className="px-6 py-2 bg-accent-teal text-[#06241E] font-bold rounded-lg hover:brightness-110 transition-all"
          >
            Upload File
          </button>
        </div>
      </div>
    )
  }

  const hasRooms = rooms.length > 0
  const hasDoors = doors.length > 0
  const hasData = hasRooms || hasDoors

  if (!hasData) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-bg-card rounded-xl p-8 text-center border border-white/5">
          <div className="w-16 h-16 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-white mb-2">No Data Extracted</h2>
          <p className="text-text-secondary mb-4">
            The extraction completed but no doors or rooms were found in the document.
          </p>
          <button
            onClick={() => router.push('/upload')}
            className="px-6 py-2 bg-accent-teal text-[#06241E] font-bold rounded-lg hover:brightness-110 transition-all"
          >
            Try Another File
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header */}
      <div className="bg-bg-secondary px-6 py-4 flex items-center gap-4 shadow-md z-10 border-b border-white/5">
        <button
          onClick={() => router.push('/')}
          className="text-white/70 hover:text-white transition-colors"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-bold">{fileName || 'Extraction Results'}</h1>
          <p className="text-xs text-blue-300/50">Extracted {new Date().toLocaleDateString()}</p>
        </div>
        <button
          onClick={handleExport}
          className="text-accent-teal hover:text-accent-teal/80 transition-colors"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="px-6 py-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Flooring */}
          <div className="stat-card">
            <div className="flex justify-between items-start mb-2">
              <span className="text-2xl">📐</span>
              <span className="text-xs text-blue-300/50 font-mono">TOTAL</span>
            </div>
            <div className="text-3xl font-bold text-accent-teal">
              {totalArea > 0 ? totalArea.toLocaleString('de-DE', { maximumFractionDigits: 1 }) : '-'}
            </div>
            <div className="text-xs text-blue-300/50 mt-1">Square meters</div>
          </div>

          {/* Rooms */}
          <div className="stat-card">
            <div className="flex justify-between items-start mb-2">
              <span className="text-2xl">🏠</span>
              <span className="text-xs text-blue-300/50 font-mono">COUNT</span>
            </div>
            <div className="text-3xl font-bold">
              {result?.flooring?.total_rooms || rooms.length || '-'}
            </div>
            <div className="text-xs text-blue-300/50 mt-1">Total rooms</div>
          </div>

          {/* Doors */}
          <div className="stat-card">
            <div className="flex justify-between items-start mb-2">
              <span className="text-2xl">🚪</span>
              <span className="text-xs text-blue-300/50 font-mono">QTY</span>
            </div>
            <div className="text-3xl font-bold text-amber-400">
              {result?.doors?.total_doors || doors.length || '-'}
            </div>
            <div className="text-xs text-blue-300/50 mt-1">Doors detected</div>
          </div>

          {/* Drywall */}
          <div className="stat-card">
            <div className="flex justify-between items-start mb-2">
              <span className="text-2xl">🧱</span>
              <span className="text-xs text-blue-300/50 font-mono">AREA</span>
            </div>
            <div className="text-3xl font-bold text-purple-400">
              {drywallArea > 0 ? drywallArea.toLocaleString('de-DE', { maximumFractionDigits: 1 }) : (totalPerimeter > 0 ? (totalPerimeter * drywallWallHeight).toLocaleString('de-DE', { maximumFractionDigits: 0 }) : '-')}
            </div>
            <div className="text-xs text-blue-300/50 mt-1">Drywall m²</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex px-6 border-b border-white/5">
        {(['overview', 'doors', 'areas', 'export'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-3 font-medium text-sm transition-colors ${
              activeTab === tab
                ? 'text-accent-teal border-b-2 border-accent-teal'
                : 'text-blue-200/50 hover:text-white'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Flooring Results Table */}
            {hasRooms && (
              <div>
                <h2 className="text-lg font-bold mb-4">Flooring Results</h2>
                <div className="card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Metric</th>
                        <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Total Flooring Area</td>
                        <td className="px-4 py-3 text-right font-bold text-accent-teal">
                          {totalArea.toLocaleString('de-DE', { maximumFractionDigits: 1 })} m²
                        </td>
                      </tr>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Total Rooms</td>
                        <td className="px-4 py-3 text-right font-bold">
                          {result?.flooring?.total_rooms || rooms.length}
                        </td>
                      </tr>
                      {totalPerimeter > 0 && (
                        <tr className="border-b border-white/5">
                          <td className="px-4 py-3">Total Perimeter (Walls)</td>
                          <td className="px-4 py-3 text-right font-bold text-purple-400">
                            {totalPerimeter.toLocaleString('de-DE', { maximumFractionDigits: 1 })} m
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Drywall Results Table */}
            {(drywallArea > 0 || totalPerimeter > 0) && (
              <div>
                <h2 className="text-lg font-bold mb-4">Drywall Results</h2>
                <div className="card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Metric</th>
                        <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Wall Length (perimeter)</td>
                        <td className="px-4 py-3 text-right font-bold text-blue-400">
                          {drywallWallLength > 0
                            ? drywallWallLength.toLocaleString('de-DE', { maximumFractionDigits: 1 })
                            : totalPerimeter.toLocaleString('de-DE', { maximumFractionDigits: 1 })
                          } m
                        </td>
                      </tr>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Wall Height</td>
                        <td className="px-4 py-3 text-right font-bold">
                          {drywallWallHeight.toFixed(1)} m
                        </td>
                      </tr>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Total Drywall Area</td>
                        <td className="px-4 py-3 text-right font-bold text-purple-400">
                          {drywallArea > 0
                            ? drywallArea.toLocaleString('de-DE', { maximumFractionDigits: 1 })
                            : (totalPerimeter * drywallWallHeight).toLocaleString('de-DE', { maximumFractionDigits: 1 })
                          } m²
                        </td>
                      </tr>
                      <tr className="border-b border-white/5 bg-white/5">
                        <td className="px-4 py-3 text-xs text-blue-300/50" colSpan={2}>
                          Formula: Wall Length × Wall Height = Drywall Area (single-sided)
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Largest Units */}
            {hasRooms && (
              <div>
                <h2 className="text-lg font-bold mb-4">Largest Units</h2>
                <div className="card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Room ID</th>
                        <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Type</th>
                        <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Area</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...rooms].sort((a, b) => b.area_m2 - a.area_m2).slice(0, 6).map((room) => (
                        <tr key={room.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="px-4 py-3 font-mono text-blue-200">{room.room_number}</td>
                          <td className="px-4 py-3 text-text-secondary">{room.room_type}</td>
                          <td className="px-4 py-3 text-right font-bold text-accent-teal">
                            {room.area_m2.toLocaleString('de-DE', { minimumFractionDigits: 2 })} m²
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Door Summary */}
            {hasDoors && (
              <div>
                <h2 className="text-lg font-bold mb-4">Door Detection Results</h2>
                <div className="card overflow-hidden mb-4">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Metric</th>
                        <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-white/5">
                        <td className="px-4 py-3">Total Doors</td>
                        <td className="px-4 py-3 text-right font-bold text-amber-400">
                          {result?.doors?.total_doors || doors.length}
                        </td>
                      </tr>
                      {fireRatingSummary && fireRatingSummary.total_fire_rated > 0 && (
                        <tr className="border-b border-white/5">
                          <td className="px-4 py-3">Fire-Rated Doors</td>
                          <td className="px-4 py-3 text-right font-bold text-red-400">
                            {fireRatingSummary.total_fire_rated}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Fire Rating Breakdown - from API */}
                {fireRatingSummary && (fireRatingSummary.count_t90 > 0 || fireRatingSummary.count_t30 > 0 || fireRatingSummary.count_dss > 0) && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-blue-300/50 mb-3">Fire-Rated Doors</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">T90 (90 min)</div>
                        <div className="text-2xl font-bold text-red-400">{fireRatingSummary.count_t90}</div>
                        {fireRatingSummary.t90_doors.length > 0 && (
                          <div className="text-[10px] text-gray-400 mt-1 truncate">
                            {fireRatingSummary.t90_doors.slice(0, 2).join(', ')}
                            {fireRatingSummary.t90_doors.length > 2 && '...'}
                          </div>
                        )}
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">T30 (30 min)</div>
                        <div className="text-2xl font-bold text-orange-400">{fireRatingSummary.count_t30}</div>
                        {fireRatingSummary.t30_doors.length > 0 && (
                          <div className="text-[10px] text-gray-400 mt-1 truncate">
                            {fireRatingSummary.t30_doors.slice(0, 2).join(', ')}
                            {fireRatingSummary.t30_doors.length > 2 && '...'}
                          </div>
                        )}
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">DSS (Smoke)</div>
                        <div className="text-2xl font-bold text-yellow-400">{fireRatingSummary.count_dss}</div>
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">Standard</div>
                        <div className="text-2xl font-bold text-gray-400">{fireRatingSummary.count_standard}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Door Width Breakdown */}
                {result?.doors?.by_width && Object.keys(result.doors.by_width).length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-blue-300/50 mb-3">By Width</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      {Object.entries(result.doors.by_width)
                        .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
                        .map(([width, count]) => (
                          <div key={width} className="card p-4">
                            <div className="text-xs text-blue-300/50 uppercase mb-1">{width}m</div>
                            <div className="text-2xl font-bold text-amber-400">{count as number}</div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Legacy fire rating stats if available (fallback) */}
                {!fireRatingSummary && (doorStats.t90 > 0 || doorStats.t30 > 0 || doorStats.dss > 0) && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-blue-300/50 mb-3">By Fire Rating</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">T90 Fire Doors</div>
                        <div className="text-2xl font-bold text-red-400">{doorStats.t90}</div>
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">T30 Fire Doors</div>
                        <div className="text-2xl font-bold text-amber-400">{doorStats.t30}</div>
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">Smoke Protection</div>
                        <div className="text-2xl font-bold text-yellow-400">{doorStats.dss}</div>
                      </div>
                      <div className="card p-4">
                        <div className="text-xs text-blue-300/50 uppercase mb-1">Standard</div>
                        <div className="text-2xl font-bold text-gray-400">{doorStats.standard}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {!hasRooms && !hasDoors && (
              <div className="text-center py-12 text-text-muted">
                No data to display
              </div>
            )}
          </div>
        )}

        {activeTab === 'doors' && (
          <div className="space-y-4">
            {hasDoors ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold">Detected Doors</h2>
                  <span className="text-sm text-blue-300/50">
                    {result?.doors?.total_doors || doors.length} items
                  </span>
                </div>

                {/* Door Width Summary */}
                {result?.doors?.by_width && Object.keys(result.doors.by_width).length > 0 && (
                  <div className="card p-4 mb-4">
                    <h3 className="text-xs text-blue-300/50 uppercase mb-3">Width Distribution</h3>
                    <div className="flex flex-wrap gap-3">
                      {Object.entries(result.doors.by_width)
                        .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
                        .map(([width, count]) => (
                          <div key={width} className="bg-bg-secondary px-3 py-2 rounded-lg">
                            <span className="text-accent-teal font-bold">{width}m</span>
                            <span className="text-gray-400 ml-2">× {count as number}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Door List */}
                <div className="space-y-3">
                  {doors.map((door, index) => (
                    <div
                      key={door.id}
                      className="card p-3 flex items-center hover:bg-bg-hover transition-colors"
                    >
                      <div className="w-10 h-10 bg-amber-900/50 rounded-lg flex items-center justify-center font-mono font-bold text-sm text-amber-200">
                        {index + 1}
                      </div>
                      <div className="flex-1 ml-3">
                        <div className="font-medium text-sm">{door.door_number}</div>
                        <div className="flex gap-2 mt-1">
                          <span className="text-[10px] bg-white/10 text-gray-300 px-1.5 py-0.5 rounded">
                            {door.type}
                          </span>
                          {door.fire_rating && door.fire_rating !== '-' && door.fire_rating !== null && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                              door.category === 'T90' ? 'bg-red-500/20 text-red-300 border-red-500/30' :
                              door.category === 'T30' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                              'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                            }`}>
                              {door.fire_rating}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-accent-teal">
                          {door.width_m > 0 ? `${door.width_m.toFixed(2)}m` : '-'}
                        </div>
                        {door.height_m > 0 && (
                          <div className="text-[10px] text-gray-400">h: {door.height_m.toFixed(2)}m</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-bg-hover rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-3xl">🚪</span>
                </div>
                <p className="text-text-secondary">No doors extracted from this document</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'areas' && (
          <div className="space-y-6">
            {hasRooms ? (
              <>
                {/* Pie Chart Section */}
                {Object.keys(roomsByType).length > 0 && (
                  <div className="flex flex-col items-center py-4">
                    <PieChart data={roomsByType} totalArea={totalArea} />
                  </div>
                )}

                {/* Breakdown by Type Legend */}
                <div>
                  <h3 className="text-xs font-semibold text-blue-300/50 uppercase tracking-wider mb-4">
                    Breakdown by Type
                  </h3>
                  <div className="space-y-0">
                    {Object.entries(roomsByType)
                      .sort(([,a], [,b]) => b.area - a.area)
                      .map(([type, data], index) => {
                        const colors = ['#00D4AA', '#3B82F6', '#A855F7', '#F59E0B', '#EC4899', '#10B981']
                        const color = colors[index % colors.length]
                        return (
                          <div key={type} className="flex items-center justify-between py-4 border-b border-white/5">
                            <div className="flex items-center gap-3">
                              <div
                                className="w-4 h-4 rounded-full"
                                style={{ backgroundColor: color }}
                              />
                              <div className="flex flex-col">
                                <span className="font-medium">{type}</span>
                                <span className="text-xs text-blue-300/50">{data.count} rooms</span>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className="font-bold text-lg">
                                {data.area.toLocaleString('de-DE', { maximumFractionDigits: 1 })}
                              </span>
                              <span className="text-xs text-gray-400 ml-1">m²</span>
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </div>

                {/* All Rooms Table */}
                <div>
                  <h2 className="text-lg font-bold mb-4">All Rooms</h2>
                  <div className="card overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/10">
                          <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Room ID</th>
                          <th className="text-left px-4 py-3 text-xs text-blue-300/50 uppercase">Type</th>
                          <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Area</th>
                          <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Perimeter</th>
                          <th className="text-right px-4 py-3 text-xs text-blue-300/50 uppercase">Ceiling</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rooms.map((room) => (
                          <tr key={room.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                            <td className="px-4 py-3 font-mono text-blue-200">{room.room_number}</td>
                            <td className="px-4 py-3 text-text-secondary">{room.room_type}</td>
                            <td className="px-4 py-3 text-right font-bold text-accent-teal">
                              {room.area_m2.toLocaleString('de-DE', { minimumFractionDigits: 2 })} m²
                            </td>
                            <td className="px-4 py-3 text-right text-purple-400">
                              {room.perimeter_m ? `${room.perimeter_m.toLocaleString('de-DE', { minimumFractionDigits: 1 })} m` : '-'}
                            </td>
                            <td className="px-4 py-3 text-right text-text-secondary">
                              {room.ceiling_height_m ? `${room.ceiling_height_m.toFixed(2)} m` : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-white/10 bg-white/5">
                          <td className="px-4 py-3 font-bold" colSpan={2}>Total</td>
                          <td className="px-4 py-3 text-right font-bold text-accent-teal">
                            {totalArea.toLocaleString('de-DE', { maximumFractionDigits: 1 })} m²
                          </td>
                          <td className="px-4 py-3 text-right font-bold text-purple-400">
                            {totalPerimeter > 0 ? `${totalPerimeter.toLocaleString('de-DE', { maximumFractionDigits: 1 })} m` : '-'}
                          </td>
                          <td className="px-4 py-3"></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-bg-hover rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-3xl">📐</span>
                </div>
                <p className="text-text-secondary">No room/area data extracted from this document</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'export' && (
          <div className="space-y-6">
            <h2 className="text-lg font-bold">Export Options</h2>

            <div className="grid gap-4">
              <button
                onClick={handleExport}
                className="card p-4 flex items-center gap-4 hover:bg-bg-hover transition-colors"
              >
                <div className="w-12 h-12 bg-accent-teal/20 rounded-lg flex items-center justify-center">
                  <span className="text-2xl">📄</span>
                </div>
                <div className="flex-1 text-left">
                  <div className="font-bold">JSON Export</div>
                  <div className="text-sm text-blue-300/50">Raw data for integrations</div>
                </div>
                <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </button>

              <button className="card p-4 flex items-center gap-4 hover:bg-bg-hover transition-colors opacity-50 cursor-not-allowed">
                <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
                  <span className="text-2xl">📊</span>
                </div>
                <div className="flex-1 text-left">
                  <div className="font-bold">Excel Export</div>
                  <div className="text-sm text-blue-300/50">Coming soon</div>
                </div>
              </button>

              <button className="card p-4 flex items-center gap-4 hover:bg-bg-hover transition-colors opacity-50 cursor-not-allowed">
                <div className="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center">
                  <span className="text-2xl">📑</span>
                </div>
                <div className="flex-1 text-left">
                  <div className="font-bold">PDF Report</div>
                  <div className="text-sm text-blue-300/50">Coming soon</div>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Pie Chart Component using CSS conic-gradient
function PieChart({
  data,
  totalArea
}: {
  data: Record<string, { count: number; area: number }>
  totalArea: number
}) {
  const colors = ['#00D4AA', '#3B82F6', '#A855F7', '#F59E0B', '#EC4899', '#10B981']

  // Build conic-gradient string
  const sortedEntries = Object.entries(data).sort(([,a], [,b]) => b.area - a.area)
  let cumulative = 0
  const gradientParts = sortedEntries.map(([, item], index) => {
    const percentage = (item.area / totalArea) * 100
    const start = cumulative
    cumulative += percentage
    const color = colors[index % colors.length]
    return `${color} ${start}% ${cumulative}%`
  }).join(', ')

  const gradient = `conic-gradient(${gradientParts})`

  return (
    <div
      className="relative w-48 h-48 rounded-full mb-6"
      style={{
        background: gradient,
        boxShadow: '0 0 30px rgba(0,0,0,0.3)'
      }}
    >
      {/* Inner circle with total */}
      <div className="absolute inset-4 bg-bg-primary rounded-full flex items-center justify-center flex-col">
        <span className="text-xs text-blue-300/50 uppercase">Total</span>
        <span className="text-2xl font-bold">
          {totalArea.toLocaleString('de-DE', { maximumFractionDigits: 0 })}
        </span>
        <span className="text-xs text-gray-400">m²</span>
      </div>
    </div>
  )
}
