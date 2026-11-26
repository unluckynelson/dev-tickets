<script setup lang="ts">
// The ticket's pickers: lane, priority, assignee and labels, plus who reported it
// and whether you follow it. Each picker saves on change and hands the result up;
// the dialog owns the ticket.
import { date } from '../lib/helpers'
import type { IssueDetail } from '../lib/types'

const props = defineProps<{ detail: IssueDetail }>()
const emit = defineEmits<{
  lane: [stateId: string]
  assignee: [assigneeId: string | null]
  priority: [priority: number]
  labels: [labelIds: string[]]
  follow: [on: boolean]
}>()

const { config } = useDevTickets()

const assigneeOptions = computed(() => [
  { label: 'Unassigned', value: null as string | null },
  ...(config.value?.assignees ?? []).map(p => ({ label: p.name, value: p.id })),
])
const labelIds = computed(() => props.detail.labels.map(l => l.id))

/** The page's path and query ("/schedule?site=128"), which says more than "a page". */
const pagePath = computed(() => {
  const url = props.detail.pageUrl
  if (!url) return ''
  try {
    const u = new URL(url)
    return decodeURIComponent(u.pathname + u.search) || '/'
  }
  catch {
    return url
  }
})
</script>

<template>
  <div class="fields">
    <div class="field">
      <label>Status</label>
      <Select
        :model-value="detail.stateId"
        :options="config?.states ?? []"
        option-label="name"
        option-value="id"
        size="small"
        @update:model-value="emit('lane', $event)"
      />
    </div>
    <div class="field">
      <label>Priority</label>
      <Select
        :model-value="detail.priority"
        :options="config?.priorities ?? []"
        option-label="label"
        option-value="value"
        size="small"
        @update:model-value="emit('priority', $event)"
      />
    </div>
    <div class="field">
      <label>Assignee</label>
      <Select
        :model-value="detail.assigneeId || null"
        :options="assigneeOptions"
        option-label="label"
        option-value="value"
        size="small"
        @update:model-value="emit('assignee', $event)"
      />
    </div>
    <div class="field">
      <label>Labels</label>
      <MultiSelect
        :model-value="labelIds"
        :options="config?.labels ?? []"
        option-label="name"
        option-value="id"
        placeholder="None"
        size="small"
        display="chip"
        @update:model-value="emit('labels', $event)"
      >
        <template #option="{ option }">
          <span class="dot" :style="{ background: option.color }" /> {{ option.name }}
        </template>
      </MultiSelect>
    </div>

    <div class="meta">
      <span>
        Reported by <strong>{{ detail.reporterName || 'unknown' }}</strong>
        <template v-if="detail.contextLabel"> in {{ detail.contextLabel }}</template>
        · {{ date(detail.createdAt) }}
      </span>
      <a
        v-if="detail.pageUrl" v-tooltip.bottom="detail.pageUrl" :href="detail.pageUrl" target="_blank"
        rel="noopener" class="page"
      >
        <i class="pi pi-link" /> <span class="path">{{ pagePath }}</span>
      </a>
      <span class="grow" />
      <Button
        v-tooltip.left="detail.subscriberNames.length ? `Following: ${detail.subscriberNames.join(', ')}` : 'Nobody follows this yet'"
        :label="detail.subscribed ? 'Following' : 'Follow'"
        :icon="detail.subscribed ? 'pi pi-bell' : 'pi pi-bell-slash'"
        :severity="detail.subscribed ? 'primary' : 'secondary'"
        size="small"
        text
        @click="emit('follow', !detail.subscribed)"
      />
    </div>
  </div>
</template>

<style scoped>
.fields {
  display: grid;
  gap: 0.6rem 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}
.field label {
  color: var(--p-text-muted-color);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.meta {
  align-items: center;
  color: var(--p-text-muted-color);
  display: flex;
  flex-wrap: wrap;
  font-size: 0.8rem;
  gap: 0.75rem;
  grid-column: 1 / -1;
}
.page {
  align-items: center;
  color: var(--p-primary-color);
  display: inline-flex;
  gap: 0.3rem;
  min-width: 0;
  text-decoration: none;
}
.path {
  font-family: var(--p-font-family-mono, ui-monospace, monospace);
  max-width: 28rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.grow {
  flex: 1;
}
.dot {
  border-radius: 50%;
  display: inline-block;
  height: 0.6rem;
  margin-right: 0.35rem;
  width: 0.6rem;
}
</style>
