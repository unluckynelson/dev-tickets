<script setup lang="ts">
// Links to other tickets: related, blocks / blocked by, duplicate. Marking this one
// a duplicate of another closes it.
import { errorText, stateSeverity } from '../lib/helpers'
import type { IssueDetail, TicketRef } from '../lib/types'

const props = defineProps<{ detail: IssueDetail }>()
const emit = defineEmits<{ updated: [detail: IssueDetail], error: [message: string] }>()

const { searchTickets, link, unlink, prefix, ticketPath } = useDevTickets()

const KINDS = [
  { label: 'Related to', value: 'related' },
  { label: 'Blocks', value: 'blocks' },
  { label: 'Duplicate of', value: 'duplicate' },
]

const adding = ref(false)
const kind = ref('related')
const picked = ref<TicketRef | null>(null)
const suggestions = ref<TicketRef[]>([])

async function search(event: { query: string }) {
  try {
    suggestions.value = (await searchTickets(event.query)).filter(t => t.id !== props.detail.id)
  }
  catch {
    suggestions.value = []
  }
}

async function save() {
  if (!picked.value || typeof picked.value !== 'object') return
  try {
    emit('updated', await link(props.detail.id, picked.value.id, kind.value))
    picked.value = null
    adding.value = false
  }
  catch (e) {
    emit('error', errorText(e))
  }
}

async function remove(relationId: string) {
  try {
    emit('updated', await unlink(props.detail.id, relationId))
  }
  catch (e) {
    emit('error', errorText(e))
  }
}
</script>

<template>
  <section class="block">
    <div class="title">
      <h4>Links</h4>
      <Button v-if="!adding" label="Link a ticket" icon="pi pi-plus" text size="small" @click="adding = true" />
    </div>

    <ul v-if="detail.relations.length" class="links">
      <li v-for="r in detail.relations" :key="r.id">
        <span class="kind">{{ r.label }}</span>
        <NuxtLink :to="ticketPath(r.ticket.identifier)" class="ref">
          <strong>{{ r.ticket.identifier }}</strong> {{ r.ticket.title }}
        </NuxtLink>
        <Tag :value="r.ticket.stateName" :severity="stateSeverity(r.ticket.stateType)" class="state" />
        <Button icon="pi pi-times" text rounded size="small" severity="secondary" aria-label="Unlink" @click="remove(r.id)" />
      </li>
    </ul>
    <p v-else-if="!adding" class="muted">None.</p>

    <div v-if="adding" class="add">
      <Select v-model="kind" :options="KINDS" option-label="label" option-value="value" size="small" />
      <AutoComplete
        v-model="picked"
        :suggestions="suggestions"
        option-label="identifier"
        :placeholder="`${prefix}-12 or words from the title`"
        size="small"
        class="pick"
        @complete="search"
      >
        <template #option="{ option }">
          <strong>{{ option.identifier }}</strong>&nbsp;{{ option.title }}
        </template>
      </AutoComplete>
      <Button label="Link" size="small" :disabled="!picked || typeof picked !== 'object'" @click="save" />
      <Button label="Cancel" size="small" text severity="secondary" @click="adding = false" />
    </div>
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
  font-size: 0.8rem;
  margin: 0;
}
.links {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.links li {
  align-items: center;
  display: flex;
  font-size: 0.85rem;
  gap: 0.5rem;
}
.kind {
  color: var(--p-text-muted-color);
  flex: none;
  font-size: 0.75rem;
  width: 6.5rem;
}
.ref {
  color: inherit;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-decoration: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ref:hover {
  text-decoration: underline;
}
.state {
  font-size: 0.65rem;
}
.add {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.pick {
  flex: 1 1 14rem;
}
</style>
