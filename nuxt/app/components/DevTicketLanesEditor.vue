<script setup lang="ts">
// Settings → Lanes: rename, retype, show or hide, reorder, add and remove the board's
// lanes. A lane's type is what it means (a closed type closes its tickets); its key
// never changes, so a rename moves no ticket. A lane still holding tickets is removed
// only once you say where they go.
import { LANE_TYPES, errorText, laneAccent } from '../lib/helpers'
import type { Lane } from '../lib/types'

const emit = defineEmits<{ changed: [] }>()
const { fetchLanes, saveLane, reorderLanes, deleteLane } = useDevTicketSettings()

type Row = Lane & { draft: string }
const rows = ref<Row[]>([])
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const removing = ref<Row | null>(null)
const moveTo = ref<string | null>(null)
const adding = reactive({ name: '', type: 'unstarted' })

async function load() {
  loading.value = true
  try {
    rows.value = (await fetchLanes()).map(l => ({ ...l, draft: l.name }))
  }
  catch (e) {
    error.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}
onMounted(load)

async function act(work: () => Promise<unknown>) {
  error.value = ''
  busy.value = true
  try {
    await work()
    await load()
    emit('changed')
  }
  catch (e) {
    error.value = errorText(e)
    await load()
  }
  finally {
    busy.value = false
  }
}

function save(row: Row, changes: Partial<Pick<Lane, 'type' | 'onBoard'>> = {}) {
  const name = row.draft.trim()
  if (!name) {
    row.draft = row.name
    return
  }
  const next = { id: row.id, name, type: row.type, onBoard: row.onBoard, ...changes }
  if (next.name === row.name && next.type === row.type && next.onBoard === row.onBoard) return
  return act(() => saveLane(next))
}

function move(index: number, by: number) {
  const ids = rows.value.map(r => r.id)
  const [id] = ids.splice(index, 1)
  ids.splice(index + by, 0, id!)
  return act(() => reorderLanes(ids))
}

function add() {
  const name = adding.name.trim()
  if (!name) return
  return act(async () => {
    await saveLane({ id: null, name, type: adding.type, onBoard: true })
    adding.name = ''
  })
}

function askRemove(row: Row) {
  removing.value = row
  moveTo.value = null
}

const destinations = computed(() => rows.value.filter(r => r.id !== removing.value?.id))

function remove() {
  const row = removing.value
  if (!row) return
  return act(async () => {
    await deleteLane(row.id, row.tickets ? moveTo.value : null)
    removing.value = null
  })
}
</script>

<template>
  <div class="lanes">
    <p class="hint">
      Lanes run left to right in this order. New tickets land in the first lane on the board.
      Lanes not on the board are still there to pick in a ticket.
    </p>
    <Message v-if="error" severity="error" closable @close="error = ''">{{ error }}</Message>
    <ProgressSpinner v-if="loading && !rows.length" style="width: 2rem; height: 2rem" />
    <ul class="rows">
      <li v-for="(row, i) in rows" :key="row.id" :style="{ borderLeftColor: laneAccent(row.type) }">
        <span class="order">
          <Button icon="pi pi-angle-up" text rounded size="small" :disabled="busy || i === 0" aria-label="Move up" @click="move(i, -1)" />
          <Button icon="pi pi-angle-down" text rounded size="small" :disabled="busy || i === rows.length - 1" aria-label="Move down" @click="move(i, 1)" />
        </span>
        <InputText v-model="row.draft" size="small" maxlength="40" :disabled="busy" aria-label="Lane name" class="name" @change="save(row)" @keydown.enter="save(row)" />
        <Select
          :model-value="row.type" :options="[...LANE_TYPES]" option-label="label" option-value="value"
          size="small" :disabled="busy" aria-label="What the lane means" class="type"
          @update:model-value="save(row, { type: $event })"
        >
          <template #option="{ option }">
            <span class="opt"><strong>{{ option.label }}</strong><small>{{ option.hint }}</small></span>
          </template>
        </Select>
        <span class="board">
          <ToggleSwitch :model-value="row.onBoard" :disabled="busy" :input-id="`lane-${row.id}`" @update:model-value="save(row, { onBoard: $event })" />
          <label :for="`lane-${row.id}`">On board</label>
        </span>
        <span class="count">{{ row.tickets }}</span>
        <Button icon="pi pi-trash" text rounded size="small" severity="danger" :disabled="busy" aria-label="Remove lane" @click="askRemove(row)" />
      </li>
    </ul>

    <form class="add" @submit.prevent="add">
      <InputText v-model="adding.name" size="small" maxlength="40" placeholder="New lane, e.g. In review" :disabled="busy" class="name" />
      <Select v-model="adding.type" :options="[...LANE_TYPES]" option-label="label" option-value="value" size="small" :disabled="busy" class="type" />
      <Button type="submit" label="Add lane" icon="pi pi-plus" size="small" :disabled="busy || !adding.name.trim()" />
    </form>

    <div v-if="removing" class="remove">
      <template v-if="removing.tickets">
        <span>
          Remove <strong>{{ removing.name }}</strong>? Its {{ removing.tickets }}
          {{ removing.tickets === 1 ? 'ticket moves' : 'tickets move' }} to
        </span>
        <Select v-model="moveTo" :options="destinations" option-label="name" option-value="id" placeholder="Choose a lane" size="small" />
      </template>
      <span v-else>Remove <strong>{{ removing.name }}</strong>? It holds no tickets.</span>
      <span class="grow" />
      <Button label="Keep it" text size="small" @click="removing = null" />
      <Button label="Remove" severity="danger" size="small" :disabled="busy || (removing.tickets > 0 && !moveTo)" @click="remove" />
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
  margin: 0 0 0.75rem;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  list-style: none;
  margin: 0 0 0.75rem;
  padding: 0;
}
.rows li,
.add {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}
.rows li {
  border-left: 3px solid;
  padding-left: 0.25rem;
}
.order {
  display: flex;
}
.name {
  flex: 1 1 10rem;
  min-width: 0;
}
.type {
  flex: 0 0 9.5rem;
}
.board {
  align-items: center;
  display: flex;
  font-size: 0.85rem;
  gap: 0.35rem;
  white-space: nowrap;
}
.count {
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
  min-width: 2.2rem;
  text-align: right;
}
.add {
  padding-left: calc(0.25rem + 3px + 4.5rem);
}
.opt {
  display: flex;
  flex-direction: column;
}
.opt small {
  color: var(--p-text-muted-color);
}
.remove {
  align-items: center;
  background: var(--p-content-hover-background);
  border-radius: var(--p-content-border-radius);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding: 0.6rem 0.75rem;
}
.grow {
  flex: 1;
}
</style>
