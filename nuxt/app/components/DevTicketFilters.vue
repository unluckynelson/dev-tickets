<script setup lang="ts">
// Search, filters and sort over the board already in memory. State lives in
// `useState` (see useDevTicketFilters): opening a ticket is a route change that
// re-creates the page, so component refs would come back empty on every close.
import { PRIORITY_LABELS } from '../lib/helpers'
import type { BoardIssue } from '../lib/types'

const props = defineProps<{ issues: BoardIssue[] }>()
const f = useDevTicketFilters()
const { NOBODY } = f
const { prefix } = useDevTickets()

const SORTS = [
  { label: 'Board order', value: 'default' },
  { label: 'Priority', value: 'priority' },
  { label: 'Recently updated', value: 'updated' },
  { label: 'Newest', value: 'newest' },
  { label: 'Oldest', value: 'oldest' },
]

/** Options from what is on the board, so no filter can only return nothing. */
function people(pick: (i: BoardIssue) => string, empty: string) {
  return [...new Set(props.issues.map(pick))]
    .sort((a, b) => (a || '\uffff').localeCompare(b || '\uffff'))
    .map(name => ({ label: name || empty, value: name || NOBODY }))
}
const assigneeOptions = computed(() => people(i => i.assigneeName, 'Unassigned'))
const reporterOptions = computed(() => people(i => i.reporterName, 'Unknown'))
const labelOptions = computed(() =>
  [...new Set(props.issues.flatMap(i => i.labels.map(l => l.name)))]
    .sort((a, b) => a.localeCompare(b))
    .map(name => ({ label: name, value: name })),
)
const priorityOptions = computed(() => {
  const present = new Set(props.issues.map(i => i.priority))
  return [1, 2, 3, 4, 0].filter(p => present.has(p)).map(p => ({ label: PRIORITY_LABELS[p]!, value: p }))
})
</script>

<template>
  <div class="filters">
    <IconField class="search">
      <InputIcon class="pi pi-search" />
      <InputText v-model="f.search.value" :placeholder="`Search title or ${prefix}-…`" size="small" fluid />
    </IconField>

    <MultiSelect
      v-model="f.reporters.value" :options="reporterOptions" option-label="label" option-value="value"
      placeholder="Reported by" size="small" :max-selected-labels="1" selected-items-label="{0} reporters" class="pick"
    />
    <MultiSelect
      v-model="f.assignees.value" :options="assigneeOptions" option-label="label" option-value="value"
      placeholder="Assignee" size="small" :max-selected-labels="1" selected-items-label="{0} assignees" class="pick"
    />
    <MultiSelect
      v-model="f.priorities.value" :options="priorityOptions" option-label="label" option-value="value"
      placeholder="Priority" size="small" :max-selected-labels="1" selected-items-label="{0} priorities" class="pick"
    />
    <MultiSelect
      v-if="labelOptions.length"
      v-model="f.labels.value" :options="labelOptions" option-label="label" option-value="value"
      placeholder="Label" size="small" :max-selected-labels="1" selected-items-label="{0} labels" class="pick"
    />
    <Select
      v-model="f.sortBy.value" :options="SORTS" option-label="label" option-value="value"
      size="small" class="pick sort" aria-label="Sort tickets"
    />
    <Button v-if="f.active.value" label="Clear" icon="pi pi-times" severity="secondary" text size="small" @click="f.clear" />
  </div>
</template>

<style scoped>
.filters {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.search {
  flex: 1 1 14rem;
  max-width: 22rem;
}
.pick {
  flex: 0 1 10rem;
}
.sort {
  margin-left: auto;
}
</style>
