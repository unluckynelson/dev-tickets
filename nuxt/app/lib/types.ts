/**
 * The shapes the dev-tickets GraphQL API returns. Kept out of `composables/` on
 * purpose: everything exported from there is auto-imported into the host app,
 * and names as plain as `Board` or `TicketLabel` would collide with the host's own.
 */

export interface TicketMember { id: string, name: string, email: string }
export interface TicketPriority { value: number, label: string }
export interface TicketState { id: string, name: string, type: string, onBoard: boolean }
/** A lane as the Settings dialog edits it, with how many tickets it holds. */
export interface Lane extends TicketState { tickets: number }

/** An environment allowed to reach this hub (hub mode). */
export interface HubEnvironment {
  id: string
  name: string
  source: string
  keyPrefix: string
  readOnly: boolean
  lastUsedAt: string | null
  revokedAt: string | null
}

export type TrackerMode = 'standalone' | 'hub' | 'client'

/** `/devtickets/settings/`: this install's mode and hub connection. */
export interface ConnectionState {
  mode: TrackerMode
  modes: TrackerMode[]
  hubUrl: string
  source: string
  /** A client key is saved; it is never sent back, only its first characters. */
  hasKey: boolean
  keyHint: string
  /** Fixed in the host's settings, so not editable here. */
  locked: { mode: boolean, hubUrl: boolean, hubApiKey: boolean, source: boolean }
  clients: HubEnvironment[]
  /** A key just made or rotated, shown once. */
  key?: string
  keyFor?: string
}

export interface ConnectionTest { ok: boolean, team?: string, prefix?: string, message?: string }
export interface TicketLabel { id: string, name: string, color: string }

export interface DevTicketsConfig {
  /** False when the signed-in user may not use dev tickets: every part then hides. */
  enabled: boolean
  /** The identifier prefix, "APP" in APP-12. */
  prefix: string
  /** Absolute URL of the board, as the server knows it (used in emails). */
  boardUrl: string
  teamName: string
  states: TicketState[]
  labels: TicketLabel[]
  assignees: TicketMember[]
  defaultAssigneeId: string | null
  priorities: TicketPriority[]
  emailUpdates: boolean
}

export interface BoardIssue {
  id: string
  identifier: string
  title: string
  priority: number
  stateId: string
  stateName: string
  stateType: string
  assigneeId: string
  assigneeName: string
  reporterId: string
  reporterName: string
  /** Where it was filed from: the host's tenant, company or workspace. */
  contextLabel: string
  labels: TicketLabel[]
  commentCount: number
  coverId: string | null
  createdAt: string
  updatedAt: string
}

export interface BoardLane { id: string, name: string, type: string, issues: BoardIssue[] }
export interface Board { teamName: string, lanes: BoardLane[] }

export interface TicketRef { id: string, identifier: string, title: string, stateName: string, stateType: string }

export interface IssueComment {
  id: string
  body: string
  authorId: string
  authorName: string
  createdAt: string
  editedAt: string | null
  mine: boolean
}

export interface TicketEvent { id: string, kind: string, actorName: string, summary: string, createdAt: string }
export interface TicketRelation { id: string, kind: string, label: string, ticket: TicketRef }
export interface TicketAttachment {
  id: string
  name: string
  contentType: string
  size: number
  uploaderName: string
  createdAt: string
}

export interface IssueDetail {
  id: string
  identifier: string
  title: string
  description: string
  priority: number
  stateId: string
  stateName: string
  stateType: string
  assigneeId: string
  assigneeName: string
  reporterId: string
  reporterName: string
  pageUrl: string
  contextLabel: string
  /** The environment it was filed through, when this board is a hub ("staging"); "" if here. */
  source: string
  labels: TicketLabel[]
  comments: IssueComment[]
  events: TicketEvent[]
  relations: TicketRelation[]
  attachments: TicketAttachment[]
  subscriberNames: string[]
  subscribed: boolean
  createdAt: string
  updatedAt: string
}

export interface TicketNotification {
  id: string
  read: boolean
  summary: string
  createdAt: string
  ticket: TicketRef
}

export interface DevTicketFeed {
  notifications: TicketNotification[]
  unreadCount: number
  emailUpdates: boolean
}

export interface NewTicket {
  title: string
  description: string
  priority: number
  assigneeId: string | null
  labelIds: string[]
  pageUrl: string
}

export interface TicketChanges {
  title?: string
  description?: string
  priority?: number
  labelIds?: string[]
}

/** A tab of the board's Settings dialog; `?settings=<tab>` on the board opens it. */
export type SettingsTab = 'lanes' | 'labels' | 'notifications' | 'connection'
