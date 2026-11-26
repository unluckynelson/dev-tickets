/**
 * The shapes the dev-tickets GraphQL API returns. Kept out of `composables/` on
 * purpose: everything exported from there is auto-imported into the host app,
 * and names as plain as `Board` or `TicketLabel` would collide with the host's own.
 */

export interface TicketMember { id: string, name: string, email: string }
export interface TicketPriority { value: number, label: string }
export interface TicketState { id: string, name: string, type: string, onBoard: boolean }
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
