<script setup lang="ts">
// The dev-ticket board. The host app gives it a page of its own:
//
//   <!-- pages/admin/dev-tickets/[[id]].vue -->
//   <template><DevTicketBoard base-path="/admin/dev-tickets" /></template>
//
// Cards drag between lanes; each drop is applied optimistically, settled on the
// card the server returns and reverted if the call fails. Lanes share the width
// of the page rather than scrolling sideways. Clicking a card opens the detail
// dialog -- the open ticket IS the route (<base-path>/APP-12), so a card is
// shareable. Search, filters and sort are client-side (useDevTicketFilters).
import { errorText } from '../lib/helpers'
import type { BoardIssue, BoardLane } from '../lib/types'

const props = withDefaults(defineProps<{
  /** Where the host mounted this page. The segment after it is the open ticket. */
  basePath?: string
  /** The page heading; empty hides it. */
  title?: string
}>(), { basePath: '', title: 'Dev tickets' })

const { loadConfig, fetchBoard, moveTicket, basePath: sharedBase, ticketPath } = useDevTickets()
if (props.basePath) sharedBase.value = props.basePath

const route = useRoute()

// Client-only: the session cookie lives in the browser, so a server-rendered pass
// would always be anonymous. Nothing is fetched for a user the server refuses.
const allowed = ref<boolean | null>(null)
const { data: board, refresh, pending, error } = useAsyncData('devtickets-board', async () => {
  const config = await loadConfig()
  allowed.value = !!config?.enabled
  return allowed.value ? fetchBoard() : null
  // deep: the board is edited in place (a moved card is spliced between lanes), and
  // Nuxt 4 hosts default to a shallow ref, which would leave the card where it was.
}, { server: false, deep: true })

// The open ticket IS the route: <base>/APP-12 deep-links straight onto the card,
// <base> closes it. Read from the path, so the host may name its param anything.
const openId = computed(() => {
  const base = ticketPath()
  if (!route.path.startsWith(base)) return null
  const rest = route.path.slice(base.length).replace(/^\/+|\/+$/g, '')
  return rest ? decodeURIComponent(rest) : null
})
const dialogVisible = computed({
  get: () => !!openId.value,
  set: (open) => { if (!open) navigateTo(ticketPath()) },
})

/** The card under the cursor, and the lane it came from, while a drag is live. */
const dragging = ref<{ issue: BoardIssue, laneId: string } | null>(null)
const overLaneId = ref<string | null>(null)
// A set, not one id: dragging a second card while the first is still in flight
// is ordinary on a board, and each move is independent of the others.
const moving = ref(new Set<string>())
const moveError = ref('')

function openTicket(issue: BoardIssue) {
  navigateTo(ticketPath(issue.identifier))
}

function laneAccent(type: string): string {
  if (type === 'completed') return 'var(--p-green-500)'
  if (type === 'started') return 'var(--p-blue-500)'
  if (type === 'triage') return 'var(--p-orange-500)'
  if (type === 'unstarted') return 'var(--p-primary-color)'
  return 'var(--p-surface-400)'
}

const filters = useDevTicketFilters()
const showLabels = ref(false)

const allIssues = computed<BoardIssue[]>(() => board.value?.lanes.flatMap(lane => lane.issues) ?? [])
const total = computed(() => allIssues.value.length)
/** What the board renders; `board.lanes` stays what drag-and-drop mutates. */
const visibleLanes = computed<BoardLane[]>(() => filters.view(board.value?.lanes ?? []))
const shown = computed(() => visibleLanes.value.reduce((sum, lane) => sum + lane.issues.length, 0))
const filtered = filters.active

/** A save in the dialog that is not a lane/assignee move: refresh in place. */
async function quietRefresh() {
  try {
    board.value = await fetchBoard()
  }
  catch {
    // The board keeps what it had; the Refresh button is there.
  }
}

function laneById(id: string): BoardLane | null {
  return board.value?.lanes.find(lane => lane.id === id) ?? null
}

/** Pull a card off whichever lane holds it, reporting where it was. */
function detach(id: string): { laneId: string, index: number } | null {
  for (const lane of board.value?.lanes ?? []) {
    const index = lane.issues.findIndex(issue => issue.id === id)
    if (index >= 0) {
      lane.issues.splice(index, 1)
      return { laneId: lane.id, index }
    }
  }
  return null
}

/**
 * Move a card into `laneId`, optimistically.
 *
 * The card is put in its new lane before the request so the drop feels
 * immediate, then replaced by the card the server returns. A failure puts it
 * back exactly where it was rather than refetching.
 */
async function moveTo(issue: BoardIssue, laneId: string) {
  if (moving.value.has(issue.id)) return
  const from = detach(issue.id)
  if (!from) return
  if (from.laneId === laneId) {
    laneById(from.laneId)?.issues.splice(from.index, 0, issue)
    return
  }

  laneById(laneId)?.issues.unshift(issue)
  moving.value = new Set(moving.value).add(issue.id)
  moveError.value = ''
  try {
    settle(await moveTicket(issue.id, laneId))
  }
  catch (e) {
    detach(issue.id)
    laneById(from.laneId)?.issues.splice(from.index, 0, issue)
    moveError.value = errorText(e)
  }
  finally {
    const busy = new Set(moving.value)
    busy.delete(issue.id)
    moving.value = busy
  }
}

/** Put a card from the server into its lane. A card moved off the board
 *  (canceled, duplicate) simply drops out, as a refresh would do. */
function settle(card: BoardIssue) {
  detach(card.id)
  laneById(card.stateId)?.issues.unshift(card)
}

function onDragStart(event: DragEvent, issue: BoardIssue, laneId: string) {
  dragging.value = { issue, laneId }
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    // Firefox refuses to start a drag unless some data is set.
    event.dataTransfer.setData('text/plain', issue.identifier)
  }
}

function onDragEnd() {
  dragging.value = null
  overLaneId.value = null
}

function onDragOver(event: DragEvent, lane: BoardLane) {
  if (!dragging.value || dragging.value.laneId === lane.id) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  overLaneId.value = lane.id
}

function onDrop(lane: BoardLane) {
  const held = dragging.value
  onDragEnd()
  if (held) moveTo(held.issue, lane.id)
}
</script>

<template>
  <!-- Client-only: the data is (the session cookie lives in the browser), so in a host that
       renders on the server the server's pass would differ from the browser's and fail to hydrate. -->
  <ClientOnly>
    <div v-if="allowed === false" class="page">
      <Message severity="info" :closable="false">You don't have access to dev tickets.</Message>
    </div>
    <div v-else class="page">
      <header class="head">
        <div>
          <h1 v-if="title">{{ title }}</h1>
          <p class="sub">
            <template v-if="filtered">{{ shown }} of {{ total }} tickets</template>
            <template v-else>{{ total }} {{ total === 1 ? 'ticket' : 'tickets' }}</template>
            on the board; canceled and duplicate ones are off it. Drag a card to another lane
            to move it. Everyone following a ticket hears about changes.
          </p>
        </div>
        <div class="tools">
          <Button icon="pi pi-tags" label="Labels" severity="secondary" text @click="showLabels = true" />
          <Button
            icon="pi pi-refresh"
            label="Refresh"
            severity="secondary"
            outlined
            :loading="pending"
            @click="refresh()"
          />
        </div>
      </header>

      <Message v-if="error" severity="error" :closable="false" class="mb">
        {{ error.message }}
      </Message>

      <div v-else-if="!board && pending" class="loading">
        <ProgressSpinner style="width: 2.5rem; height: 2.5rem" />
      </div>

      <template v-else>
        <Message v-if="moveError" severity="error" class="mb" @close="moveError = ''">
          Could not move that ticket: {{ moveError }}
        </Message>

        <DevTicketFilters :issues="allIssues" />

        <Message v-if="filtered && !shown" severity="info" :closable="false" class="mb">
          No ticket matches those filters.
        </Message>

        <div class="board">
          <section
            v-for="lane in visibleLanes"
            :key="lane.id"
            class="lane"
            :class="{ over: overLaneId === lane.id }"
            @dragover="onDragOver($event, lane)"
            @dragleave="overLaneId = overLaneId === lane.id ? null : overLaneId"
            @drop.prevent="onDrop(lane)"
          >
            <header class="lane-head" :style="{ borderTopColor: laneAccent(lane.type) }">
              <span class="lane-name">{{ lane.name }}</span>
              <Badge :value="lane.issues.length" severity="secondary" />
            </header>

            <div class="lane-body">
              <p v-if="!lane.issues.length" class="lane-empty">
                <template v-if="overLaneId === lane.id">Drop here</template>
                <template v-else-if="filtered">No match.</template>
                <template v-else>Nothing here.</template>
              </p>

              <DevTicketCard
                v-for="issue in lane.issues"
                :key="issue.id"
                :issue="issue"
                :busy="moving.has(issue.id)"
                :held="dragging?.issue.id === issue.id"
                @click="openTicket(issue)"
                @keydown.enter="openTicket(issue)"
                @keydown.space.prevent="openTicket(issue)"
                @dragstart="onDragStart($event, issue, lane.id)"
                @dragend="onDragEnd"
              />
            </div>
          </section>
        </div>
      </template>

      <DevTicketDialog
        v-model:visible="dialogVisible"
        :issue-id="openId"
        @updated="settle($event)"
        @changed="quietRefresh"
      />
      <DevTicketLabels v-model:visible="showLabels" @changed="quietRefresh" />
    </div>
    <template #fallback>
      <div class="page loading"><ProgressSpinner style="width: 2.5rem; height: 2.5rem" /></div>
    </template>
  </ClientOnly>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.head {
  align-items: flex-start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}
h1 {
  font-size: 1.4rem;
  margin: 0 0 0.25rem;
}
.sub {
  color: var(--p-text-muted-color);
  font-size: 0.88rem;
  margin: 0;
}
.mb {
  margin-bottom: 1rem;
}
.loading {
  display: flex;
  justify-content: center;
  padding: 3rem;
}
.tools {
  display: flex;
  gap: 0.5rem;
}
/* Lanes share the page width instead of scrolling sideways -- they shrink to
   fit, and only wrap onto a second row once they would be too narrow to read.
   Each lane still scrolls vertically on its own, so a long backlog never pushes
   the other lanes off the page. */
.board {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.lane {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  display: flex;
  flex: 1 1 13rem;
  flex-direction: column;
  max-height: calc(100vh - 14rem);
  min-width: 0;
}
.lane.over {
  border-color: var(--p-primary-color);
  box-shadow: inset 0 0 0 1px var(--p-primary-color);
}
.lane-head {
  align-items: center;
  border-top: 3px solid;
  border-radius: 8px 8px 0 0;
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
  padding: 0.7rem 0.8rem;
}
.lane-name {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}
.lane-body {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-height: 2.5rem;
  overflow-y: auto;
  padding: 0 0.6rem 0.75rem;
}
.lane-empty {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  margin: 0.25rem 0;
  text-align: center;
}
</style>
