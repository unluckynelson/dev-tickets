/**
 * The board's search, filters and sort, client-side over the board in memory.
 * `useState`, not refs and not the query string: opening a ticket is a route change
 * and the host page is re-created over it, and a query change would tear the board
 * down on every keystroke typed into the search box.
 */
import type { BoardIssue, BoardLane } from '../lib/types'

/** People filters travel as names, so "nobody" needs a value of its own. */
const NOBODY = '~none'

export function useDevTicketFilters() {
  const search = useState('devtickets.filter.search', () => '')
  const assignees = useState<string[]>('devtickets.filter.assignees', () => [])
  const reporters = useState<string[]>('devtickets.filter.reporters', () => [])
  const priorities = useState<number[]>('devtickets.filter.priorities', () => [])
  const labels = useState<string[]>('devtickets.filter.labels', () => [])
  const sortBy = useState('devtickets.filter.sort', () => 'default')

  const active = computed(() =>
    !!search.value.trim() || assignees.value.length > 0 || reporters.value.length > 0
    || priorities.value.length > 0 || labels.value.length > 0,
  )

  function matches(issue: BoardIssue): boolean {
    const q = search.value.trim().toLowerCase()
    if (q && !`${issue.identifier} ${issue.title}`.toLowerCase().includes(q)) return false
    if (assignees.value.length && !assignees.value.includes(issue.assigneeName || NOBODY)) return false
    if (reporters.value.length && !reporters.value.includes(issue.reporterName || NOBODY)) return false
    if (priorities.value.length && !priorities.value.includes(issue.priority)) return false
    if (labels.value.length && !issue.labels.some(l => labels.value.includes(l.name))) return false
    return true
  }

  /** 0 (no priority) sorts last, not first. */
  const rank = (p: number) => (p === 0 ? Number.MAX_SAFE_INTEGER : p)
  const at = (iso: string) => new Date(iso).getTime()

  function ordered(issues: BoardIssue[]): BoardIssue[] {
    const copy = [...issues]
    switch (sortBy.value) {
      case 'priority': return copy.sort((a, b) => rank(a.priority) - rank(b.priority))
      case 'updated': return copy.sort((a, b) => at(b.updatedAt) - at(a.updatedAt))
      case 'newest': return copy.sort((a, b) => at(b.createdAt) - at(a.createdAt))
      case 'oldest': return copy.sort((a, b) => at(a.createdAt) - at(b.createdAt))
      default: return issues
    }
  }

  /** Lanes are filtered, never removed: an empty lane is still a drop target. */
  function view(lanes: BoardLane[]): BoardLane[] {
    return lanes.map(lane => ({ ...lane, issues: ordered(lane.issues.filter(matches)) }))
  }

  function clear() {
    search.value = ''
    assignees.value = []
    reporters.value = []
    priorities.value = []
    labels.value = []
  }

  return { search, assignees, reporters, priorities, labels, sortBy, active, view, clear, NOBODY }
}
