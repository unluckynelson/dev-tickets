<script setup lang="ts">
// Header bell: what happened on dev tickets you follow -- ones you reported, hold,
// commented on or followed -- done by someone else. Each row is yours alone, so
// the reporter of a bug is the one told it is fixed. Polled once a minute while
// the tab is visible; anything still unread after a couple of minutes is also
// emailed, unless switched off at the foot of the panel. Hidden for anyone the
// server does not let use dev tickets. The button takes the colour of the header
// it sits in.
import { errorText, stateSeverity, timeAgo } from '../lib/helpers'

const {
  feed, loadingFeed, available, unreadCount, loadConfig, loadFeed, markSeen,
  startPolling, stopPolling, ticketPath,
} = useDevTickets()

const panel = ref()
const error = ref('')

onMounted(async () => {
  try {
    await loadConfig()
  }
  catch {
    return // Signed out, or the server is unreachable: the bell stays hidden.
  }
  if (!available.value) return
  try {
    await loadFeed()
  }
  catch (e) {
    error.value = errorText(e)
  }
  startPolling()
})

onBeforeUnmount(stopPolling)

async function toggle(event: Event) {
  panel.value?.toggle(event)
  try {
    await loadFeed()
  }
  catch (e) {
    error.value = errorText(e)
  }
}

/** A row opens the ticket on the board; opening it marks its rows read. The
 *  popover is dismissed by hand: it is teleported out of the page being left. */
function open() {
  panel.value?.hide()
}

function when(iso: string): string {
  return timeAgo(iso)
}
</script>

<template>
  <div v-if="available" class="bell-wrap">
    <Button
      v-tooltip.bottom="'Ticket updates'"
      class="bell"
      text
      rounded
      aria-label="Ticket updates"
      @click="toggle"
    >
      <i class="pi pi-bell" />
      <Badge v-if="unreadCount > 0" :value="unreadCount" severity="danger" class="bell-badge" />
    </Button>

    <Popover ref="panel">
      <div class="panel">
        <header class="panel-head">
          <span>Ticket updates</span>
          <span class="grow" />
          <Button
            v-if="unreadCount > 0"
            label="Mark all read"
            text
            size="small"
            @click="markSeen()"
          />
          <Button
            icon="pi pi-refresh"
            text
            rounded
            size="small"
            :loading="loadingFeed"
            aria-label="Refresh"
            @click="loadFeed()"
          />
        </header>

        <Message v-if="error" severity="error" :closable="false" class="panel-msg">
          {{ error }}
        </Message>

        <p v-else-if="!feed?.notifications.length" class="empty">
          Nothing yet. You'll hear here about tickets you report, are assigned or comment on.
        </p>

        <ul v-else class="list">
          <li
            v-for="n in feed.notifications"
            :key="n.id"
            class="item"
            :class="{ unread: !n.read }"
          >
            <NuxtLink :to="ticketPath(n.ticket.identifier)" class="item-main" @click="open">
              <span class="item-top">
                <span class="ident">{{ n.ticket.identifier }}</span>
                <Tag :value="n.ticket.stateName" :severity="stateSeverity(n.ticket.stateType)" class="state" />
                <span class="grow" />
                <span class="meta">{{ when(n.createdAt) }}</span>
              </span>
              <span class="item-title">{{ n.ticket.title }}</span>
              <span class="meta">{{ n.summary }}</span>
            </NuxtLink>
          </li>
        </ul>

        <footer v-if="feed" class="panel-foot">
          <i class="pi pi-envelope" />
          <span>Emails {{ feed.emailUpdates ? 'on' : 'off' }}</span>
          <span class="grow" />
          <NuxtLink :to="{ path: ticketPath(), query: { settings: 'notifications' } }" @click="open">Notification settings</NuxtLink>
        </footer>
      </div>
    </Popover>
  </div>
</template>

<style scoped>
.bell-wrap {
  position: relative;
}
.bell {
  color: inherit !important;
  position: relative;
}
.bell-badge {
  position: absolute;
  right: 0.15rem;
  top: 0.15rem;
  transform: scale(0.75);
  transform-origin: top right;
}
.panel {
  max-height: 60vh;
  overflow-y: auto;
  width: 24rem;
}
.panel-head {
  align-items: center;
  display: flex;
  font-weight: 600;
  gap: 0.25rem;
  margin-bottom: 0.25rem;
}
.grow {
  flex: 1;
}
.panel-foot {
  align-items: center;
  border-top: 1px solid var(--p-content-border-color);
  display: flex;
  font-size: 0.8rem;
  gap: 0.5rem;
  margin-top: 0.4rem;
  padding-top: 0.6rem;
}
.panel-msg,
.empty {
  font-size: 0.85rem;
}
.empty {
  color: var(--p-text-muted-color);
  margin: 0.5rem 0;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.item {
  border-top: 1px solid var(--p-content-border-color);
}
.item:first-child {
  border-top: none;
}
.item.unread {
  /* A left rule rather than a filled row: it survives both themes without
     needing a second colour, and reads as "new" beside the state tag. */
  border-left: 3px solid var(--p-primary-color);
  margin-left: -0.5rem;
  padding-left: 0.5rem;
}
.item-main {
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.6rem 0.15rem;
  text-decoration: none;
}
.item-main:hover {
  background: var(--p-content-hover-background);
}
.item-top {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}
.ident {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.state {
  font-size: 0.68rem;
}
.item-title {
  font-size: 0.88rem;
  line-height: 1.3;
}
.meta {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}
</style>
