<script setup lang="ts">
// Floating "log a dev ticket" button, bottom-right, for whoever the server lets
// use dev tickets (it hides for everyone else).
//
// Floating rather than a nav item because you log the bug from the page you
// found it on -- which is why the current URL is captured and stored on the
// ticket; the server adds the context you are working in. You are its reporter,
// and you hear about every change to it. Screenshots can be pasted or picked and
// are uploaded once the ticket exists.
//
// Position it from the host with `--dev-tickets-fab-bottom` and
// `--dev-tickets-fab-right` (both default to 1.5rem), e.g. to clear a chat
// composer or another floating button.
import { errorText } from '../lib/helpers'
import type { BoardIssue } from '../lib/types'

const props = withDefaults(defineProps<{
  /** Description only, the server writes the title (its title generator, or the
   * first line). False asks for a title as well. */
  autoTitle?: boolean
  /** Open "Open the ticket" in a new tab, for hosts where the board is another app. */
  newTab?: boolean
}>(), { autoTitle: true, newTab: false })

const { config, available, loadConfig, createTicket, uploadAttachments, ticketPath } = useDevTickets()

const visible = ref(false)
const saving = ref(false)
const error = ref('')
// The ticket just created. Non-null swaps the dialog to its confirmation view.
const created = ref<BoardIssue | null>(null)

const title = ref('')
const description = ref('')
const autoTitle = computed(() => props.autoTitle)
const ready = computed(() => !!(autoTitle.value ? description.value : title.value).trim())
const priority = ref(3)
const assigneeId = ref<string | null>(null)
const labelIds = ref<string[]>([])
const files = ref<File[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

/** Absolute URL of the page the reporter is on, which is what a dev needs to reproduce.
 * Read from the address bar when the dialog opens, not the route, which an app in
 * an iframe or a host with its own history handling may not keep in step. */
const currentUrl = ref('')

onMounted(async () => {
  try {
    await loadConfig()
  }
  catch {
    // Signed out, or the server is unreachable: the button just stays hidden.
  }
})

const ticketTarget = computed(() => (props.newTab ? '_blank' : undefined))

const show = computed(() => available.value)

function reset() {
  title.value = ''
  description.value = ''
  priority.value = 3
  assigneeId.value = config.value?.defaultAssigneeId ?? null
  labelIds.value = []
  files.value = []
  created.value = null
  error.value = ''
}

function open() {
  reset()
  currentUrl.value = window.location.href
  visible.value = true
}

// "Highlight on page": the dialog steps aside while the reporter marks up the page,
// and the marked-up screenshot comes back as an attachment.
const marking = ref(false)
function startMarkup() {
  visible.value = false
  marking.value = true
}
function endMarkup(file?: File) {
  marking.value = false
  if (file) files.value.push(file)
  visible.value = true
}

function picked(event: Event) {
  files.value.push(...((event.target as HTMLInputElement).files ?? []))
  if (fileInput.value) fileInput.value.value = ''
}

function pasted(event: ClipboardEvent) {
  const pastedFiles = [...(event.clipboardData?.files ?? [])]
  if (pastedFiles.length) {
    event.preventDefault()
    files.value.push(...pastedFiles)
  }
}

async function submit() {
  if (!ready.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const ticket = await createTicket({
      title: autoTitle.value ? '' : title.value.trim(),
      description: description.value,
      priority: priority.value,
      assigneeId: assigneeId.value,
      labelIds: labelIds.value,
      pageUrl: currentUrl.value,
    })
    if (files.value.length) {
      try {
        await uploadAttachments(ticket.id, files.value)
      }
      catch {
        error.value = `${ticket.identifier} was logged, but the attachments did not upload. Add them from the ticket.`
      }
    }
    created.value = ticket
  }
  catch (e) {
    error.value = errorText(e)
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="show">
    <!-- Hidden while its own dialog is up: the button sits above every modal
         (see .dev-fab), so without this it would float over the ticket form. -->
    <Button
      v-show="!visible && !marking"
      v-tooltip.left="'Log a dev ticket'"
      class="dev-fab"
      icon="pi pi-ticket"
      rounded
      raised
      aria-label="Log a dev ticket"
      @click="open"
    />

    <Dialog
      v-model:visible="visible"
      modal
      :header="created ? 'Ticket logged' : 'Log a dev ticket'"
      :style="{ width: '34rem' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div v-if="created" class="form">
        <Message v-if="error" severity="warn" :closable="false">{{ error }}</Message>
        <Message severity="success" :closable="false">
          <strong>{{ created.identifier }}</strong> is in {{ created.stateName }}. You'll hear
          about every change to it.
        </Message>
        <p class="created-title">{{ created.title }}</p>
        <NuxtLink :to="ticketPath(created.identifier)" :target="ticketTarget" class="link" @click="visible = false">
          <i class="pi pi-arrow-right" /> Open the ticket
        </NuxtLink>
      </div>

      <div v-else class="form" @paste="pasted">
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

        <div v-if="!autoTitle" class="field">
          <label for="dt-title">Title</label>
          <InputText
            id="dt-title"
            v-model="title"
            autofocus
            maxlength="300"
            placeholder="Short summary of the problem"
            @keydown.enter="submit"
          />
        </div>

        <div class="field">
          <label for="dt-desc">Description</label>
          <Textarea
            id="dt-desc"
            v-model="description"
            rows="6"
            auto-resize
            :autofocus="autoTitle"
            placeholder="What did you expect, and what happened instead?"
          />
          <small class="hint">
            <i class="pi pi-link" /> {{ currentUrl }} is attached automatically.<template v-if="autoTitle"> The title is written from your description.</template>
          </small>
        </div>

        <div class="row">
          <div class="field">
            <label for="dt-assignee">Assignee</label>
            <Select
              id="dt-assignee"
              v-model="assigneeId"
              :options="config?.assignees ?? []"
              option-label="name"
              option-value="id"
              placeholder="Unassigned"
              show-clear
            />
          </div>
          <div class="field">
            <label for="dt-priority">Priority</label>
            <Select
              id="dt-priority"
              v-model="priority"
              :options="config?.priorities ?? []"
              option-label="label"
              option-value="value"
            />
          </div>
        </div>

        <div class="field">
          <label for="dt-labels">Labels</label>
          <MultiSelect
            id="dt-labels"
            v-model="labelIds"
            :options="config?.labels ?? []"
            option-label="name"
            option-value="id"
            placeholder="None"
            display="chip"
          />
        </div>

        <div class="field">
          <label>Screenshots and files</label>
          <div class="files">
            <Chip
              v-for="(f, i) in files"
              :key="i"
              :label="f.name"
              removable
              @remove="files.splice(i, 1)"
            />
            <Button label="Add" icon="pi pi-paperclip" text size="small" @click="fileInput?.click()" />
            <Button label="Highlight on page" icon="pi pi-pencil" text size="small" @click="startMarkup" />
            <input ref="fileInput" type="file" multiple hidden @change="picked">
          </div>
          <small class="hint">Or paste a screenshot into this dialog. Highlight on page lets you draw on the page and attaches a screenshot of it.</small>
        </div>
      </div>

      <template #footer>
        <template v-if="created">
          <Button label="Log another" severity="secondary" text @click="reset" />
          <Button label="Done" @click="visible = false" />
        </template>
        <template v-else>
          <Button
            label="Cancel"
            severity="secondary"
            text
            :disabled="saving"
            @click="visible = false"
          />
          <Button
            label="Log ticket"
            icon="pi pi-send"
            :loading="saving"
            :disabled="!ready"
            @click="submit"
          />
        </template>
      </template>
    </Dialog>
    <DevTicketMarkup v-if="marking" @done="endMarkup" @cancel="endMarkup()" />
  </div>
</template>

<style scoped>
/* Two classes, so it outranks PrimeVue's `.p-button-icon-only.p-button-rounded` height
   whatever order the stylesheets land in: with equal weight, a later PrimeVue sheet
   took the height back to 2.5rem while the width stayed, and the circle went oval. */
.dev-fab.p-button {
  bottom: var(--dev-tickets-fab-bottom, 1.5rem);
  height: 3.25rem;
  position: fixed;
  right: var(--dev-tickets-fab-right, 1.5rem);
  width: 3.25rem;
  /* Above PrimeVue's modal mask (zIndex.modal = 1100; each open dialog takes
     1101, 1102, ...) so a bug can be logged from inside an entity editor -- a
     ticket filed after closing the dialog no longer says where the reporter
     was. The button hides while its own dialog is open (v-show above). */
  z-index: 1190;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}
.field label {
  font-size: 0.85rem;
  font-weight: 600;
}
.row {
  display: flex;
  gap: 1rem;
}
.hint {
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}
.created-title {
  margin: 0;
  font-weight: 600;
}
.files {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.link {
  align-items: center;
  color: var(--p-primary-color);
  display: inline-flex;
  gap: 0.4rem;
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}
</style>
