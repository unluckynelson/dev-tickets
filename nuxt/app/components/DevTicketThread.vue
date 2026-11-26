<script setup lang="ts">
// Comments and history, interleaved by time, then the reply box. Your own comments
// can be edited or deleted. Everyone following the ticket hears about a comment.
// Adding or deleting one emits `changed` and the dialog reloads the ticket.
import { dateTime, errorText, initials } from '../lib/helpers'
import type { IssueComment, IssueDetail, TicketEvent } from '../lib/types'

const props = defineProps<{ detail: IssueDetail }>()
const emit = defineEmits<{ changed: [], error: [message: string] }>()

const { addComment, editComment, deleteComment } = useDevTickets()

type Entry = { at: string, comment?: IssueComment, event?: TicketEvent }

const entries = computed<Entry[]>(() =>
  [
    ...props.detail.comments.map(c => ({ at: c.createdAt, comment: c })),
    ...props.detail.events.map(e => ({ at: e.createdAt, event: e })),
  ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime()),
)

const reply = ref('')
const sending = ref(false)
const editingId = ref<string | null>(null)
const editText = ref('')

function fail(e: unknown) {
  emit('error', errorText(e))
}

async function send() {
  if (!reply.value.trim() || sending.value) return
  sending.value = true
  try {
    await addComment(props.detail.id, reply.value)
    reply.value = ''
    emit('changed')
  }
  catch (e) {
    fail(e)
  }
  finally {
    sending.value = false
  }
}

function startEdit(comment: IssueComment) {
  editingId.value = comment.id
  editText.value = comment.body
}

async function saveEdit(comment: IssueComment) {
  try {
    Object.assign(comment, await editComment(comment.id, editText.value))
    editingId.value = null
  }
  catch (e) {
    fail(e)
  }
}

async function remove(comment: IssueComment) {
  if (!confirm('Delete this comment?')) return
  try {
    await deleteComment(comment.id)
    emit('changed')
  }
  catch (e) {
    fail(e)
  }
}

function when(iso: string): string {
  return dateTime(iso)
}
</script>

<template>
  <section class="block">
    <h4>Activity <span class="muted">({{ detail.comments.length }} comments)</span></h4>
    <ul class="thread">
      <li v-for="entry in entries" :key="entry.comment ? `c${entry.comment.id}` : `e${entry.event!.id}`">
        <div v-if="entry.comment" class="comment">
          <div class="head">
            <Avatar :label="initials(entry.comment.authorName)" shape="circle" class="who" />
            <strong>{{ entry.comment.authorName }}</strong>
            <small class="muted">
              {{ when(entry.comment.createdAt) }}<template v-if="entry.comment.editedAt"> · edited</template>
            </small>
            <span class="grow" />
            <template v-if="entry.comment.mine && editingId !== entry.comment.id">
              <Button icon="pi pi-pencil" text rounded size="small" aria-label="Edit" @click="startEdit(entry.comment)" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" aria-label="Delete" @click="remove(entry.comment)" />
            </template>
          </div>
          <div v-if="editingId === entry.comment.id" class="edit">
            <DevTicketMarkdownEditor v-model="editText" />
            <div class="actions">
              <Button label="Cancel" text severity="secondary" size="small" @click="editingId = null" />
              <Button label="Save" size="small" :disabled="!editText.trim()" @click="saveEdit(entry.comment)" />
            </div>
          </div>
          <DevTicketMarkdownBody v-else :text="entry.comment.body" />
        </div>
        <div v-else class="event">
          <i class="pi pi-circle-fill" />
          <span>{{ entry.event!.summary }}</span>
          <small class="muted">{{ when(entry.event!.createdAt) }}</small>
        </div>
      </li>
    </ul>

    <label class="reply-label">Add a comment</label>
    <DevTicketMarkdownEditor v-model="reply" placeholder="Reply on this ticket…" />
    <div class="actions">
      <small class="muted">Everyone following this ticket is told.</small>
      <span class="grow" />
      <Button
        label="Comment"
        icon="pi pi-comment"
        size="small"
        :loading="sending"
        :disabled="!reply.trim()"
        @click="send"
      />
    </div>
  </section>
</template>

<style scoped>
.block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
h4 {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin: 0;
  text-transform: uppercase;
}
.muted {
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
}
.thread {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.comment {
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  padding: 0.5rem 0.7rem;
}
.head {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}
.who {
  font-size: 0.6rem;
  height: 1.5rem;
  width: 1.5rem;
}
.event {
  align-items: baseline;
  color: var(--p-text-muted-color);
  display: flex;
  font-size: 0.82rem;
  gap: 0.5rem;
  padding-left: 0.4rem;
}
.event .pi {
  font-size: 0.4rem;
}
.reply-label {
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: 0.5rem;
}
.actions {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.edit {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.grow {
  flex: 1;
}
</style>
