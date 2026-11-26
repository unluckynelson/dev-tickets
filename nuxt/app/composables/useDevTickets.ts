/**
 * Dev tickets: state shared by the board, the widget and the bell, and every call
 * they make. A ticket's `id` is its identifier ("APP-12"), the same handle the
 * route carries.
 *
 * Who may use it is the server's decision: `devSupportConfig` answers
 * `enabled: false` for anyone else, and every part hides itself on that answer.
 * Nothing here asks the host app who the user is.
 */
import type {
  Board, BoardIssue, DevTicketFeed, DevTicketsConfig, IssueComment, IssueDetail, NewTicket,
  TicketChanges, TicketLabel, TicketRef,
} from '../lib/types'

const CONFIG = `
  query DevSupportConfig {
    devSupportConfig {
      enabled prefix boardUrl teamName defaultAssigneeId emailUpdates
      states { id name type onBoard }
      labels { id name color }
      assignees { id name email }
      priorities { value label }
    }
  }
`

const CARD_FIELDS = `
  id identifier title priority stateId stateName stateType
  assigneeId assigneeName reporterId reporterName contextLabel commentCount coverId createdAt updatedAt
  labels { id name color }
`

const REF = 'id identifier title stateName stateType'

const DETAIL_FIELDS = `
  id identifier title description priority stateId stateName stateType
  assigneeId assigneeName reporterId reporterName pageUrl contextLabel
  subscriberNames subscribed createdAt updatedAt
  labels { id name color }
  comments { id body authorId authorName createdAt editedAt mine }
  events { id kind actorName summary createdAt }
  relations { id kind label ticket { ${REF} } }
  attachments { id name contentType size uploaderName createdAt }
`

const COMMENT = 'id body authorId authorName createdAt editedAt mine'

const FEED = `
  query DevTickets {
    devTickets {
      unreadCount emailUpdates
      notifications { id read summary createdAt ticket { ${REF} } }
    }
  }
`

/** How often the bell re-reads while the page is visible. */
const POLL_MS = 60 * 1000

/** One config request per page load, however many parts mount at once. */
let configRequest: Promise<DevTicketsConfig | null> | null = null

export function useDevTickets() {
  const { graphql, upload, filesUrl, boardPath } = useDevTicketsApi()

  const config = useState<DevTicketsConfig | null>('devtickets.config', () => null)
  const feed = useState<DevTicketFeed | null>('devtickets.feed', () => null)
  const loadingFeed = useState('devtickets.loadingFeed', () => false)
  // Where the board lives. DevTicketBoard sets it from its `base-path`, so links
  // from the widget, the bell and the ticket links all agree with the host's route.
  const basePath = useState('devtickets.basePath', () => boardPath)
  // One shared timer for the whole app, however many components mount this.
  const timer = useState<ReturnType<typeof setInterval> | null>('devtickets.timer', () => null)

  const available = computed(() => !!config.value?.enabled)
  const prefix = computed(() => config.value?.prefix || 'DEV')
  const unreadCount = computed(() => feed.value?.unreadCount ?? 0)

  function ticketPath(identifier = ''): string {
    const base = basePath.value.replace(/\/+$/, '')
    return identifier ? `${base}/${identifier}` : base
  }

  /** URL of an attachment's bytes; `download` saves rather than shows it. */
  function attachmentUrl(id: string, download = false): string {
    return filesUrl(`attachment/${id}/${download ? '?download=1' : ''}`)
  }

  async function loadConfig(force = false): Promise<DevTicketsConfig | null> {
    if (config.value && !force) return config.value
    configRequest ??= graphql<{ devSupportConfig: DevTicketsConfig }>(CONFIG)
      .then((data) => {
        config.value = data.devSupportConfig
        return config.value
      })
      .finally(() => { configRequest = null })
    return configRequest
  }

  async function loadFeed() {
    if (!available.value) return null
    loadingFeed.value = true
    try {
      const data = await graphql<{ devTickets: DevTicketFeed }>(FEED)
      feed.value = data.devTickets
      return feed.value
    }
    finally {
      loadingFeed.value = false
    }
  }

  /** Mark the bell read: everything, or one ticket's rows (opening it). */
  async function markSeen(id: string | null = null) {
    const data = await graphql<{ markDevTicketsSeen: number }>(
      'mutation($id: String) { markDevTicketsSeen(id: $id) }', { id },
    )
    if (feed.value) {
      feed.value.unreadCount = data.markDevTicketsSeen
      for (const n of feed.value.notifications) {
        if (!id || n.ticket.id === id) n.read = true
      }
    }
  }

  async function setEmailUpdates(on: boolean) {
    await graphql('mutation($on: Boolean!) { setDevTicketEmail(on: $on) }', { on })
    if (feed.value) feed.value.emailUpdates = on
    if (config.value) config.value.emailUpdates = on
  }

  function startPolling() {
    if (!available.value || timer.value) return
    timer.value = setInterval(() => {
      if (document.visibilityState === 'visible') loadFeed().catch(() => {})
    }, POLL_MS)
  }

  function stopPolling() {
    if (timer.value) {
      clearInterval(timer.value)
      timer.value = null
    }
  }

  async function createTicket(input: NewTicket): Promise<BoardIssue> {
    const data = await graphql<{ createDevTicket: BoardIssue }>(`
      mutation($title: String!, $description: String!, $priority: Int!, $assigneeId: String,
               $labelIds: [String!], $pageUrl: String!) {
        createDevTicket(title: $title, description: $description, priority: $priority,
          assigneeId: $assigneeId, labelIds: $labelIds, pageUrl: $pageUrl) { ${CARD_FIELDS} }
      }`, { ...input })
    return data.createDevTicket
  }

  async function fetchBoard(): Promise<Board> {
    const data = await graphql<{ devTicketBoard: Board }>(`
      query { devTicketBoard { teamName lanes { id name type issues { ${CARD_FIELDS} } } } }`)
    return data.devTicketBoard
  }

  async function fetchDetail(id: string): Promise<IssueDetail | null> {
    const data = await graphql<{ devTicketDetail: IssueDetail | null }>(
      `query($id: String!) { devTicketDetail(id: $id) { ${DETAIL_FIELDS} } }`, { id },
    )
    return data.devTicketDetail
  }

  async function searchTickets(query: string): Promise<TicketRef[]> {
    const data = await graphql<{ devTicketSearch: TicketRef[] }>(
      `query($q: String!) { devTicketSearch(query: $q) { ${REF} } }`, { q: query },
    )
    return data.devTicketSearch
  }

  /** Edit title, description, priority or labels; omitted keys stay as they are. */
  async function updateTicket(id: string, changes: TicketChanges): Promise<IssueDetail> {
    const data = await graphql<{ updateDevTicket: IssueDetail }>(`
      mutation($id: String!, $title: String, $description: String, $priority: Int, $labelIds: [String!]) {
        updateDevTicket(id: $id, title: $title, description: $description, priority: $priority,
          labelIds: $labelIds) { ${DETAIL_FIELDS} }
      }`, { id, ...changes })
    return data.updateDevTicket
  }

  async function moveTicket(id: string, stateId: string): Promise<BoardIssue> {
    const data = await graphql<{ moveDevTicket: BoardIssue }>(
      `mutation($id: String!, $s: String!) { moveDevTicket(id: $id, stateId: $s) { ${CARD_FIELDS} } }`,
      { id, s: stateId },
    )
    return data.moveDevTicket
  }

  /** A null `assigneeId` takes the ticket off whoever holds it. */
  async function assignTicket(id: string, assigneeId: string | null): Promise<BoardIssue> {
    const data = await graphql<{ assignDevTicket: BoardIssue }>(
      `mutation($id: String!, $a: String) { assignDevTicket(id: $id, assigneeId: $a) { ${CARD_FIELDS} } }`,
      { id, a: assigneeId },
    )
    return data.assignDevTicket
  }

  async function addComment(id: string, body: string): Promise<IssueComment> {
    const data = await graphql<{ commentOnDevTicket: IssueComment }>(
      `mutation($id: String!, $b: String!) { commentOnDevTicket(id: $id, body: $b) { ${COMMENT} } }`,
      { id, b: body },
    )
    return data.commentOnDevTicket
  }

  async function editComment(id: string, body: string): Promise<IssueComment> {
    const data = await graphql<{ editDevTicketComment: IssueComment }>(
      `mutation($id: String!, $b: String!) { editDevTicketComment(id: $id, body: $b) { ${COMMENT} } }`,
      { id, b: body },
    )
    return data.editDevTicketComment
  }

  async function deleteComment(id: string) {
    await graphql('mutation($id: String!) { deleteDevTicketComment(id: $id) }', { id })
  }

  async function link(id: string, otherId: string, kind: string): Promise<IssueDetail> {
    const data = await graphql<{ linkDevTickets: IssueDetail }>(`
      mutation($id: String!, $o: String!, $k: String!) {
        linkDevTickets(id: $id, otherId: $o, kind: $k) { ${DETAIL_FIELDS} }
      }`, { id, o: otherId, k: kind })
    return data.linkDevTickets
  }

  async function unlink(id: string, relationId: string): Promise<IssueDetail> {
    const data = await graphql<{ unlinkDevTickets: IssueDetail }>(`
      mutation($id: String!, $r: String!) { unlinkDevTickets(id: $id, relationId: $r) { ${DETAIL_FIELDS} } }`,
    { id, r: relationId })
    return data.unlinkDevTickets
  }

  async function subscribe(id: string, on: boolean) {
    await graphql('mutation($id: String!, $on: Boolean!) { subscribeDevTicket(id: $id, on: $on) }', { id, on })
  }

  /** Multipart upload; the server takes several files under `file`. */
  async function uploadAttachments(id: string, files: File[]) {
    const body = new FormData()
    for (const f of files) body.append('file', f)
    await upload(`${encodeURIComponent(id)}/`, body)
  }

  async function deleteAttachment(id: string, attachmentId: string): Promise<IssueDetail> {
    const data = await graphql<{ deleteDevTicketAttachment: IssueDetail }>(`
      mutation($id: String!, $a: String!) {
        deleteDevTicketAttachment(id: $id, attachmentId: $a) { ${DETAIL_FIELDS} }
      }`, { id, a: attachmentId })
    return data.deleteDevTicketAttachment
  }

  async function saveLabel(name: string, color: string, id: string | null = null): Promise<TicketLabel> {
    const data = await graphql<{ saveDevTicketLabel: TicketLabel }>(`
      mutation($n: String!, $c: String!, $id: String) {
        saveDevTicketLabel(name: $n, color: $c, id: $id) { id name color }
      }`, { n: name, c: color, id })
    await loadConfig(true)
    return data.saveDevTicketLabel
  }

  async function deleteLabel(id: string) {
    await graphql('mutation($id: String!) { deleteDevTicketLabel(id: $id) }', { id })
    await loadConfig(true)
  }

  return {
    config,
    feed,
    loadingFeed,
    available,
    prefix,
    unreadCount,
    basePath,
    ticketPath,
    attachmentUrl,
    loadConfig,
    loadFeed,
    markSeen,
    setEmailUpdates,
    startPolling,
    stopPolling,
    createTicket,
    fetchBoard,
    fetchDetail,
    searchTickets,
    updateTicket,
    moveTicket,
    assignTicket,
    addComment,
    editComment,
    deleteComment,
    link,
    unlink,
    subscribe,
    uploadAttachments,
    deleteAttachment,
    saveLabel,
    deleteLabel,
  }
}
