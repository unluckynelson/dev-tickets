<script setup lang="ts">
// Settings → Labels: add, rename, recolour and delete ticket labels. Deleting one
// takes it off every ticket that has it.
import { errorText } from '../lib/helpers'
import type { TicketLabel } from '../lib/types'

const emit = defineEmits<{ changed: [] }>()
const { config, saveLabel, deleteLabel } = useDevTickets()

const drafts = ref<{ id: string | null, name: string, color: string }[]>([])
const error = ref('')

onMounted(() => {
  drafts.value = (config.value?.labels ?? []).map((l: TicketLabel) => ({ ...l }))
})

function add() {
  drafts.value.push({ id: null, name: '', color: '#4EA7FC' })
}

async function save(row: { id: string | null, name: string, color: string }) {
  error.value = ''
  try {
    const saved = await saveLabel(row.name.trim(), row.color.startsWith('#') ? row.color : `#${row.color}`, row.id)
    row.id = saved.id
    emit('changed')
  }
  catch (e) {
    error.value = errorText(e)
  }
}

async function remove(index: number) {
  const row = drafts.value[index]!
  if (row.id && !confirm(`Delete the label "${row.name}"? It comes off every ticket.`)) return
  try {
    if (row.id) await deleteLabel(row.id)
    drafts.value.splice(index, 1)
    emit('changed')
  }
  catch (e) {
    error.value = errorText(e)
  }
}
</script>

<template>
  <div>
    <Message v-if="error" severity="error" @close="error = ''">{{ error }}</Message>
    <ul class="rows">
      <li v-for="(row, i) in drafts" :key="row.id ?? `new-${i}`">
        <ColorPicker
          :model-value="row.color.replace('#', '')"
          @update:model-value="row.color = `#${$event}`; row.id && row.name.trim() && save(row)"
        />
        <InputText v-model="row.name" size="small" maxlength="60" placeholder="Name" fluid @change="row.name.trim() && save(row)" />
        <Button icon="pi pi-trash" text rounded size="small" severity="danger" aria-label="Delete" @click="remove(i)" />
      </li>
    </ul>
    <Button label="Add a label" icon="pi pi-plus" text size="small" @click="add" />
  </div>
</template>

<style scoped>
.rows {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  list-style: none;
  margin: 0 0 0.5rem;
  padding: 0;
}
.rows li {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}
</style>
