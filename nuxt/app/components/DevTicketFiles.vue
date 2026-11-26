<script setup lang="ts">
// Screenshots and files on a ticket. Images show as thumbnails and open in a
// lightbox; other files open in a new tab. Everything is served through the
// access-checked file view, never a public URL.
import { errorText } from '../lib/helpers'
import type { IssueDetail } from '../lib/types'

const props = defineProps<{ detail: IssueDetail }>()
// `changed` tells the board: the first image is the card's cover.
const emit = defineEmits<{
  reload: []
  updated: [detail: IssueDetail]
  changed: []
  error: [message: string]
}>()

const { uploadAttachments, deleteAttachment, attachmentUrl } = useDevTickets()
const input = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

function isImage(type: string) {
  return type.startsWith('image/')
}

const images = computed(() => props.detail.attachments.filter(a => isImage(a.contentType)))
const shown = ref<number | null>(null)
function view(id: string) {
  shown.value = images.value.findIndex(a => a.id === id)
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function upload(files: File[]) {
  if (!files.length) return
  uploading.value = true
  try {
    await uploadAttachments(props.detail.id, files)
    emit('reload')
    emit('changed')
  }
  catch (e) {
    const data = (e as { data?: { problems?: string[] } }).data
    emit('error', data?.problems?.join(' ') || errorText(e))
  }
  finally {
    uploading.value = false
    if (input.value) input.value.value = ''
  }
}

function picked(event: Event) {
  upload([...((event.target as HTMLInputElement).files ?? [])])
}

/** Paste a screenshot straight onto the ticket. */
function pasted(event: ClipboardEvent) {
  const files = [...(event.clipboardData?.files ?? [])]
  if (files.length) {
    event.preventDefault()
    upload(files)
  }
}

async function remove(id: string, name: string) {
  if (!confirm(`Remove ${name}?`)) return
  try {
    emit('updated', await deleteAttachment(props.detail.id, id))
    emit('changed')
  }
  catch (e) {
    emit('error', errorText(e))
  }
}

defineExpose({ pasted })
</script>

<template>
  <section class="block">
    <div class="title">
      <h4>Attachments</h4>
      <Button
        label="Attach"
        icon="pi pi-paperclip"
        text
        size="small"
        :loading="uploading"
        @click="input?.click()"
      />
      <input ref="input" type="file" multiple hidden @change="picked">
    </div>
    <p v-if="!detail.attachments.length" class="muted">None. Paste a screenshot anywhere in this dialog to attach it.</p>
    <ul v-else class="files">
      <li v-for="a in detail.attachments" :key="a.id">
        <button v-if="isImage(a.contentType)" type="button" class="file" @click="view(a.id)">
          <img :src="attachmentUrl(a.id)" :alt="a.name" class="thumb">
          <span class="name">{{ a.name }}</span>
        </button>
        <a v-else :href="attachmentUrl(a.id)" target="_blank" rel="noopener" class="file">
          <i class="pi pi-file icon" />
          <span class="name">{{ a.name }}</span>
        </a>
        <small class="muted">{{ size(a.size) }}<template v-if="a.uploaderName"> · {{ a.uploaderName }}</template></small>
        <Button icon="pi pi-times" text rounded size="small" severity="secondary" aria-label="Remove" @click="remove(a.id, a.name)" />
      </li>
    </ul>
    <DevTicketLightbox v-model:index="shown" :images="images" />
  </section>
</template>

<style scoped>
.block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.title {
  align-items: center;
  display: flex;
  justify-content: space-between;
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
  margin: 0;
}
.files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.files li {
  align-items: center;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  display: flex;
  gap: 0.4rem;
  max-width: 100%;
  padding: 0.3rem 0.4rem;
}
.file {
  align-items: center;
  background: none;
  border: 0;
  color: inherit;
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-align: left;
  display: flex;
  gap: 0.4rem;
  min-width: 0;
  text-decoration: none;
}
.thumb {
  border-radius: 4px;
  height: 2.5rem;
  object-fit: cover;
  width: 3.5rem;
}
.icon {
  font-size: 1.4rem;
}
.name {
  font-size: 0.82rem;
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
