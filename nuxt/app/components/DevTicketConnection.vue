<script setup lang="ts">
// Settings → Connection: whether this install keeps its own tickets (standalone),
// shares its board with other environments (hub), or shows another install's board
// (client). A client connection is tried before it is saved. As a hub, each
// environment gets its own key, shown once. Whatever the host app fixes in its
// settings shows here as locked.
import { dateTime, errorText } from '../lib/helpers'
import type { ConnectionState, ConnectionTest, HubEnvironment, TrackerMode } from '../lib/types'

const emit = defineEmits<{ changed: [] }>()
const api = useDevTicketSettings()
const { backendOrigin } = useDevTicketsApi()
const { loadConfig } = useDevTickets()

const MODES: { value: TrackerMode, label: string, text: string }[] = [
  { value: 'standalone', label: 'Standalone', text: 'Tickets live in this app, for its own users.' },
  { value: 'hub', label: 'Hub', text: 'Tickets live here, and other environments use this board too, each with its own key.' },
  { value: 'client', label: 'Client', text: 'Tickets live on another install (the hub); this app shows that board.' },
]

const state = ref<ConnectionState | null>(null)
const refused = ref('')
const error = ref('')
const busy = ref(false)
const form = reactive({ mode: 'standalone' as TrackerMode, hubUrl: '', hubApiKey: '', source: '' })
const tested = ref<ConnectionTest | null>(null)
const fresh = ref<{ key: string, name: string } | null>(null)
const copied = ref(false)
const newEnv = reactive({ name: '', readOnly: false })
const revoking = ref<string | null>(null)

function take(next: ConnectionState) {
  state.value = next
  form.mode = next.mode
  form.hubUrl = next.hubUrl
  form.source = next.source
  form.hubApiKey = ''
  if (next.key) fresh.value = { key: next.key, name: next.keyFor ?? '' }
}

onMounted(async () => {
  try {
    take(await api.loadConnection())
  }
  catch (e) {
    refused.value = errorText(e)
  }
})

async function run(work: () => Promise<void>) {
  error.value = ''
  busy.value = true
  try {
    await work()
  }
  catch (e) {
    error.value = errorText(e)
  }
  finally {
    busy.value = false
  }
}

const changed = computed(() => !!state.value && (
  form.mode !== state.value.mode
  || (form.mode === 'client' && (form.hubUrl !== state.value.hubUrl || form.source !== state.value.source || !!form.hubApiKey))
))

const warning = computed(() => {
  if (!state.value || form.mode === state.value.mode) return ''
  if (state.value.mode === 'hub') return 'Environments using this hub stop reaching it.'
  if (form.mode === 'client') return 'Tickets already in this app stay in its database, but are not shown while it is a client.'
  if (state.value.mode === 'client') return 'This app goes back to its own tickets; the hub\'s stay on the hub.'
  return ''
})

const input = () => ({ mode: form.mode, hubUrl: form.hubUrl.trim(), hubApiKey: form.hubApiKey.trim(), source: form.source.trim() })

const test = () => run(async () => {
  tested.value = await api.testConnection(input())
})

const save = () => run(async () => {
  take(await api.saveConnection(input()))
  tested.value = null
  await loadConfig(true)
  emit('changed')
})

const addEnv = () => run(async () => {
  take(await api.addEnvironment(newEnv.name.trim(), newEnv.readOnly))
  newEnv.name = ''
  newEnv.readOnly = false
})

const rotate = (env: HubEnvironment) => run(async () => take(await api.rotateEnvironment(env.id)))
const setReadOnly = (env: HubEnvironment, on: boolean) => run(async () => take(await api.updateEnvironment(env.id, { readOnly: on })))
const revoke = (env: HubEnvironment) => run(async () => {
  take(await api.updateEnvironment(env.id, { revoke: true }))
  revoking.value = null
})

async function copy() {
  if (!fresh.value) return
  await navigator.clipboard.writeText(fresh.value.key)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}
</script>

<template>
  <div class="conn">
    <Message v-if="refused" severity="info" :closable="false">{{ refused }}</Message>
    <ProgressSpinner v-else-if="!state" style="width: 2rem; height: 2rem" />
    <template v-else>
      <Message v-if="error" severity="error" closable @close="error = ''">{{ error }}</Message>

      <fieldset class="modes" :disabled="state.locked.mode || busy">
        <label v-for="m in MODES" :key="m.value" class="mode" :class="{ on: form.mode === m.value }">
          <RadioButton v-model="form.mode" :value="m.value" name="dt-mode" />
          <span><strong>{{ m.label }}</strong><small>{{ m.text }}</small></span>
        </label>
      </fieldset>
      <p v-if="state.locked.mode" class="locked"><i class="pi pi-lock" /> The mode is set in this app's settings (DEV_TICKETS).</p>

      <div v-if="form.mode === 'client'" class="fields">
        <label for="dt-hub">Hub address</label>
        <InputText id="dt-hub" v-model="form.hubUrl" placeholder="https://hub.example.com" :disabled="state.locked.hubUrl || busy" fluid />
        <label for="dt-key">This environment's key</label>
        <Password
          v-model="form.hubApiKey" input-id="dt-key" :feedback="false" toggle-mask fluid
          :placeholder="state.hasKey ? `Saved${state.keyHint ? ` (${state.keyHint}…)` : ''}; leave blank to keep it` : 'dt_… from the hub\'s Settings → Connection'"
          :disabled="state.locked.hubApiKey || busy"
        />
        <label for="dt-source">This environment's name</label>
        <InputText id="dt-source" v-model="form.source" placeholder="staging" maxlength="60" :disabled="state.locked.source || busy" fluid />
        <small class="help">The hub shows it on everything done from here ("from staging").</small>
        <Message v-if="tested" :severity="tested.ok ? 'success' : 'error'" :closable="false">
          <template v-if="tested.ok">Connected to {{ tested.team || 'the hub' }}{{ tested.prefix ? ` (${tested.prefix}-…)` : '' }}.</template>
          <template v-else>{{ tested.message }}</template>
        </Message>
      </div>

      <Message v-if="warning" severity="warn" :closable="false">{{ warning }}</Message>
      <div v-if="!state?.locked.mode || form.mode === 'client'" class="actions">
        <Button v-if="form.mode === 'client'" label="Test connection" icon="pi pi-bolt" severity="secondary" outlined :loading="busy" @click="test" />
        <Button label="Save" icon="pi pi-check" :disabled="!changed || busy" @click="save" />
      </div>

      <section v-if="state?.mode === 'hub'" class="hub">
        <h3>Environments using this hub</h3>
        <p class="help">
          On each, open Settings → Connection, choose <strong>Client</strong>, and enter this hub's
          address, <code>{{ backendOrigin() }}</code>, with the key made for it here.
        </p>
        <Message v-if="fresh" severity="success" closable @close="fresh = null">
          <div class="fresh">
            <span>Key for <strong>{{ fresh.name }}</strong>. Copy it now: it is not shown again.</span>
            <code>{{ fresh.key }}</code>
            <Button :label="copied ? 'Copied' : 'Copy'" :icon="copied ? 'pi pi-check' : 'pi pi-copy'" size="small" text @click="copy" />
          </div>
        </Message>
        <p v-if="!state?.clients.length" class="help">None yet.</p>
        <ul class="envs">
          <li v-for="env in state?.clients ?? []" :key="env.id" :class="{ revoked: env.revokedAt }">
            <span class="env-main">
              <strong>{{ env.name }}</strong>
              <small>
                <code>{{ env.keyPrefix }}…</code> ·
                {{ env.revokedAt ? `revoked ${dateTime(env.revokedAt)}` : env.lastUsedAt ? `last used ${dateTime(env.lastUsedAt)}` : 'never used' }}
              </small>
            </span>
            <span class="board">
              <ToggleSwitch :model-value="env.readOnly" :disabled="busy || !!env.revokedAt" :input-id="`env-${env.id}`" @update:model-value="setReadOnly(env, $event)" />
              <label :for="`env-${env.id}`">Read-only</label>
            </span>
            <Button :label="env.revokedAt ? 'New key' : 'Rotate'" icon="pi pi-refresh" size="small" text :disabled="busy" @click="rotate(env)" />
            <template v-if="!env.revokedAt">
              <Button v-if="revoking !== env.id" label="Revoke" size="small" text severity="danger" :disabled="busy" @click="revoking = env.id" />
              <span v-else class="confirm">
                Stops it at once.
                <Button label="Revoke" size="small" severity="danger" :disabled="busy" @click="revoke(env)" />
                <Button label="Keep" size="small" text @click="revoking = null" />
              </span>
            </template>
          </li>
        </ul>
        <form class="add" @submit.prevent="addEnv">
          <InputText v-model="newEnv.name" size="small" maxlength="100" placeholder="Environment, e.g. staging" :disabled="busy" class="grow" />
          <Checkbox v-model="newEnv.readOnly" binary input-id="dt-ro" :disabled="busy" />
          <label for="dt-ro" class="small">Read-only</label>
          <Button type="submit" label="Make a key" icon="pi pi-key" size="small" :disabled="busy || !newEnv.name.trim()" />
        </form>
      </section>
    </template>
  </div>
</template>

<style scoped>
.conn {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.modes {
  border: 0;
  display: grid;
  gap: 0.5rem;
  grid-template-columns: repeat(3, 1fr);
  margin: 0;
  padding: 0;
}
.mode {
  align-items: flex-start;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  cursor: pointer;
  display: flex;
  gap: 0.5rem;
  padding: 0.6rem 0.7rem;
}
.mode.on {
  border-color: var(--p-primary-color);
}
.mode span {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.mode small,
.help,
.locked {
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
}
.locked,
.help {
  margin: 0;
}
.fields {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.fields label {
  font-size: 0.875rem;
  font-weight: 600;
  margin-top: 0.4rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.hub {
  border-top: 1px solid var(--p-content-border-color);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding-top: 0.75rem;
}
.hub h3 {
  font-size: 1rem;
  margin: 0;
}
.fresh {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.fresh code {
  word-break: break-all;
}
.envs {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.envs li,
.add,
.board,
.confirm {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}
.envs li.revoked .env-main {
  opacity: 0.6;
}
.env-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}
.env-main small,
.board,
.small,
.confirm {
  font-size: 0.85rem;
}
.grow {
  flex: 1;
}
@media (max-width: 640px) {
  .modes {
    grid-template-columns: 1fr;
  }
}
</style>
