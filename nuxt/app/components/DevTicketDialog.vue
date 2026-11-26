<script setup lang="ts">
// One ticket: title and description (editable in place), its pickers, links,
// attachments and the comment thread with its history. The parts live in
// the other DevTicket* components; this holds the ticket and saves through them.
//
// Every change goes to the server and the dialog settles on what came back. A
// change of lane, assignee, priority or labels also emits the new card, so the
// board moves without a refetch. Opening a ticket marks its bell rows read.
import { errorText } from '../lib/helpers'
import type { BoardIssue, IssueDetail } from '../lib/types'

const props = defineProps<{ issueId: string | null }>()
const visible = defineModel<boolean>('visible', { required: true })
const emit = defineEmits<{ updated: [card: BoardIssue], changed: [] }>()

const {
  loadConfig, fetchDetail, moveTicket, assignTicket, updateTicket, subscribe, markSeen,
} = useDevTickets()

onMounted(() => { loadConfig().catch(() => {}) })

const detail = ref<IssueDetail | null>(null)
const loading = ref(false)
const error = ref('')
const files = ref<{ pasted: (e: ClipboardEvent) => void } | null>(null)

const editingTitle = ref(false)
const titleDraft = ref('')
const editingDescription = ref(false)
const descriptionDraft = ref('')
const saving = ref(false)

function fail(e: unknown) {
  error.value = errorText(e)
}

async function load(id: string, quiet = false) {
  if (!quiet) {
    loading.value = true
    detail.value = null
  }
  error.value = ''
  try {
    detail.value = await fetchDetail(id)
    if (!detail.value) error.value = `There is no ticket ${id}.`
    else markSeen(detail.value.id).catch(() => {})
  }
  catch (e) {
    fail(e)
  }
  finally {
    loading.value = false
  }
}

watch(
  () => [props.issueId, visible.value] as const,
  ([id, open]) => {
    if (!open || !id) return
    editingTitle.value = false
    editingDescription.value = false
    load(id)
  },
  { immediate: true },
)

/** Fold a card from the server into the open ticket, and tell the board. */
function settle(card: BoardIssue) {
  if (!detail.value) return
  Object.assign(detail.value, {
    stateId: card.stateId, stateName: card.stateName, stateType: card.stateType,
    assigneeId: card.assigneeId, assigneeName: card.assigneeName,
    priority: card.priority, labels: card.labels,
  })
  emit('updated', card)
  reloadHistory()
}

/** History rows are made server-side; pull them after a change. */
function reloadHistory() {
  if (detail.value) load(detail.value.id, true)
}

async function run(action: () => Promise<void>) {
  saving.value = true
  error.value = ''
  try {
    await action()
  }
  catch (e) {
    fail(e)
  }
  finally {
    saving.value = false
  }
}

function changeLane(stateId: string) {
  if (!detail.value || stateId === detail.value.stateId) return
  run(async () => settle(await moveTicket(detail.value!.id, stateId)))
}

function changeAssignee(assigneeId: string | null) {
  if (!detail.value || assigneeId === (detail.value.assigneeId || null)) return
  run(async () => settle(await assignTicket(detail.value!.id, assigneeId)))
}

/** Title, description, priority, labels: the update returns the whole ticket. */
function edit(changes: Parameters<typeof updateTicket>[1]) {
  if (!detail.value) return
  run(async () => {
    detail.value = await updateTicket(detail.value!.id, changes)
    editingTitle.value = false
    editingDescription.value = false
    emit('changed')
  })
}

function follow(on: boolean) {
  if (!detail.value) return
  run(async () => {
    await subscribe(detail.value!.id, on)
    reloadHistory()
  })
}

function startTitle() {
  titleDraft.value = detail.value?.title ?? ''
  editingTitle.value = true
}

function startDescription() {
  descriptionDraft.value = detail.value?.description ?? ''
  editingDescription.value = true
}

function onPaste(event: ClipboardEvent) {
  // Text pastes into the editors are theirs; only files are caught here.
  if (event.clipboardData?.files.length) files.value?.pasted(event)
}
</script>

<template>
  <!-- Not draggable: PrimeVue starts a drag on header mouse-down, so the title
       could not be selected. -->
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    :style="{ width: '52rem' }"
    :breakpoints="{ '900px': '95vw' }"
  >
    <template #header>
      <div v-if="detail" class="head">
        <span class="ident">{{ detail.identifier }}</span>
        <div v-if="editingTitle" class="title-edit">
          <InputText v-model="titleDraft" maxlength="300" fluid autofocus @keydown.enter="edit({ title: titleDraft })" @keydown.esc="editingTitle = false" />
          <Button icon="pi pi-check" size="small" :disabled="!titleDraft.trim()" @click="edit({ title: titleDraft })" />
          <Button icon="pi pi-times" size="small" text severity="secondary" @click="editingTitle = false" />
        </div>
        <h3 v-else class="title" title="Click to rename" @click="startTitle">{{ detail.title }}</h3>
      </div>
      <span v-else>Ticket</span>
    </template>

    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 2.5rem; height: 2.5rem" />
    </div>

    <div v-else-if="detail" class="detail" @paste="onPaste">
      <Message v-if="error" severity="error" @close="error = ''">{{ error }}</Message>

      <DevTicketFields
        :detail="detail"
        @lane="changeLane"
        @assignee="changeAssignee"
        @priority="edit({ priority: $event })"
        @labels="edit({ labelIds: $event })"
        @follow="follow"
      />

      <section class="block">
        <div class="block-title">
          <h4>Description</h4>
          <Button v-if="!editingDescription" label="Edit" icon="pi pi-pencil" text size="small" @click="startDescription" />
        </div>
        <template v-if="editingDescription">
          <DevTicketMarkdownEditor v-model="descriptionDraft" />
          <div class="actions">
            <Button label="Cancel" text severity="secondary" size="small" @click="editingDescription = false" />
            <Button label="Save" size="small" :loading="saving" @click="edit({ description: descriptionDraft })" />
          </div>
        </template>
        <DevTicketMarkdownBody v-else-if="detail.description" :text="detail.description" />
        <p v-else class="muted">No description.</p>
      </section>

      <DevTicketFiles ref="files" :detail="detail" @reload="reloadHistory" @updated="detail = $event" @changed="emit('changed')" @error="error = $event" />
      <DevTicketLinks :detail="detail" @updated="detail = $event; emit('changed')" @error="error = $event" />
      <DevTicketThread :detail="detail" @changed="reloadHistory(); emit('changed')" @error="error = $event" />
    </div>

    <Message v-else severity="error" :closable="false">{{ error || 'Could not load.' }}</Message>

    <template #footer>
      <Button label="Close" severity="secondary" text @click="visible = false" />
    </template>
  </Dialog>
</template>

<style scoped>
.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}
.head {
  align-items: baseline;
  display: flex;
  flex: 1;
  gap: 0.6rem;
  min-width: 0;
}
.ident {
  color: var(--p-text-muted-color);
  flex: none;
  font-size: 0.85rem;
  font-weight: 700;
}
.title {
  cursor: text;
  font-size: 1.1rem;
  margin: 0;
}
.title:hover {
  text-decoration: underline dotted;
}
.title-edit {
  align-items: center;
  display: flex;
  flex: 1;
  gap: 0.3rem;
}
.detail {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.block-title {
  align-items: center;
  display: flex;
  justify-content: space-between;
}
.block h4 {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin: 0;
  text-transform: uppercase;
}
.muted {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  margin: 0;
}
.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
