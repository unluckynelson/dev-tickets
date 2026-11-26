<script setup lang="ts">
// One card on the board. Shows who reported it as well as who holds it -- with
// a shared tracker account every ticket reads as raised by its owner.
// The first image attached is the card's cover, as on Trello.
import { PRIORITY_LABELS, dateTime, initials, prioritySeverity, timeAgo } from '../lib/helpers'
import type { BoardIssue } from '../lib/types'

defineProps<{ issue: BoardIssue, busy?: boolean, held?: boolean }>()

const { attachmentUrl } = useDevTickets()
</script>

<template>
  <article class="card" :class="{ busy, held }" role="button" tabindex="0" draggable="true">
    <img
      v-if="issue.coverId" :src="attachmentUrl(issue.coverId)" alt="" class="cover"
      loading="lazy" draggable="false"
    >
    <div class="card-top">
      <span class="ident">{{ issue.identifier }}</span>
      <i v-if="busy" class="pi pi-spin pi-spinner spin" />
      <Tag
        v-else-if="issue.priority"
        :value="PRIORITY_LABELS[issue.priority]"
        :severity="prioritySeverity(issue.priority)"
        class="prio"
      />
    </div>

    <p class="card-title">{{ issue.title }}</p>

    <div v-if="issue.labels.length" class="card-labels">
      <!-- Label colours are data, so they are inline rather than tokens. -->
      <span
        v-for="label in issue.labels"
        :key="label.id"
        class="label"
        :style="{ borderColor: label.color, color: label.color }"
      >{{ label.name }}</span>
    </div>

    <footer class="card-foot">
      <span v-if="issue.reporterName" v-tooltip.bottom="issue.contextLabel ? `From ${issue.contextLabel}` : undefined" class="from">
        <i class="pi pi-flag" /> {{ issue.reporterName }}
      </span>
      <span v-if="issue.commentCount" class="count"><i class="pi pi-comment" /> {{ issue.commentCount }}</span>
      <span
        v-tooltip.bottom="`Reported ${dateTime(issue.createdAt)}`"
        class="age"
      ><i class="pi pi-clock" /> {{ timeAgo(issue.createdAt) }}</span>
      <span class="grow" />
      <Avatar
        v-if="issue.assigneeName"
        v-tooltip.bottom="`Assigned to ${issue.assigneeName}`"
        :label="initials(issue.assigneeName)"
        shape="circle"
        class="who"
      />
    </footer>
  </article>
</template>

<style scoped>
.card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  cursor: grab;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.65rem 0.7rem;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.card:hover,
.card:focus-visible {
  border-color: var(--p-primary-color);
  box-shadow: 0 1px 6px rgb(0 0 0 / 8%);
  outline: none;
}
.cover {
  border-bottom: 1px solid var(--p-content-border-color);
  border-radius: 5px 5px 0 0;
  display: block;
  margin: -0.65rem -0.7rem 0.1rem;
  max-height: 10rem;
  object-fit: cover;
  object-position: top;
  width: calc(100% + 1.4rem);
}
.card.held {
  opacity: 0.45;
}
.card.busy {
  cursor: progress;
  pointer-events: none;
}
.card-top {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
}
.ident {
  color: var(--p-text-muted-color);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.prio {
  font-size: 0.65rem;
  white-space: nowrap;
}
.spin {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}
.card-title {
  font-size: 0.86rem;
  line-height: 1.35;
  margin: 0;
  overflow-wrap: anywhere;
}
.card-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.label {
  border: 1px solid;
  border-radius: 1rem;
  font-size: 0.66rem;
  font-weight: 600;
  padding: 0.05rem 0.45rem;
}
.card-foot {
  align-items: center;
  color: var(--p-text-muted-color);
  display: flex;
  font-size: 0.72rem;
  gap: 0.6rem;
  min-width: 0;
}
.card-foot .pi {
  font-size: 0.65rem;
}
.from {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.age {
  white-space: nowrap;
}
.grow {
  flex: 1;
}
.who {
  background: var(--p-primary-100);
  color: var(--p-primary-800);
  flex: none;
  font-size: 0.6rem;
  font-weight: 700;
  height: 1.4rem;
  width: 1.4rem;
}
</style>
