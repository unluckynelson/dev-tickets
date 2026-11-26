/**
 * Small presentation helpers shared by the components. Imported by relative path,
 * never auto-imported, so none of these names reach the host app.
 */

/** WorkflowState.type values that mean the ticket is off the board. */
const CLOSED_TYPES = new Set(['completed', 'canceled', 'duplicate'])

export function isClosed(stateType: string): boolean {
  return CLOSED_TYPES.has(stateType)
}

/** State type onto a PrimeVue Tag severity. */
export function stateSeverity(stateType: string) {
  if (stateType === 'completed') return 'success'
  if (stateType === 'canceled' || stateType === 'duplicate') return 'secondary'
  if (stateType === 'started') return 'info'
  if (stateType === 'triage') return 'warn'
  return 'contrast'
}

/** 1 is Urgent, 4 is Low, 0 is unset. */
export function prioritySeverity(priority: number) {
  if (priority === 1) return 'danger'
  if (priority === 2) return 'warn'
  if (priority === 3) return 'info'
  return 'secondary'
}

export const PRIORITY_LABELS: Record<number, string> = {
  0: 'No priority',
  1: 'Urgent',
  2: 'High',
  3: 'Medium',
  4: 'Low',
}

export function initials(name: string): string {
  const parts = name.split(/[\s@.]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0]![0]! + parts[1]![0]!).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

/** "3m ago", "2d ago". */
export function timeAgo(iso: string, now = Date.now()): string {
  const mins = Math.round((now - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`
  const days = Math.round(mins / (60 * 24))
  if (days < 30) return `${days}d ago`
  if (days < 365) return `${Math.round(days / 30.44)}mo ago`
  return `${Math.round(days / 365.25)}y ago`
}

/** A date and time in the reader's own locale. */
export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}
