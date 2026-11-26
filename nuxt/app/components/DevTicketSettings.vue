<script setup lang="ts">
// The board's Settings (the gear in its corner): lanes, labels, your notifications,
// and this install's connection (standalone, hub or client). Each tab saves as you
// go; `changed` tells the board to re-read itself.
import { errorText } from '../lib/helpers'
import type { SettingsTab } from '../lib/types'

const visible = defineModel<boolean>('visible', { required: true })
const tab = defineModel<SettingsTab>('tab', { default: 'lanes' })
const emit = defineEmits<{ changed: [] }>()
const { config, setEmailUpdates } = useDevTickets()

const emailError = ref('')
async function email(on: boolean) {
  emailError.value = ''
  try {
    await setEmailUpdates(on)
  }
  catch (e) {
    emailError.value = errorText(e)
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal header="Dev ticket settings" :style="{ width: '52rem' }" :breakpoints="{ '960px': '95vw' }">
    <Tabs v-if="visible" v-model:value="tab" lazy>
      <TabList>
        <Tab value="lanes"><i class="pi pi-objects-column" /> Lanes</Tab>
        <Tab value="labels"><i class="pi pi-tags" /> Labels</Tab>
        <Tab value="notifications"><i class="pi pi-bell" /> Notifications</Tab>
        <Tab value="connection"><i class="pi pi-server" /> Connection</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="lanes">
          <DevTicketLanesEditor @changed="emit('changed')" />
        </TabPanel>
        <TabPanel value="labels">
          <DevTicketLabelsEditor @changed="emit('changed')" />
        </TabPanel>
        <TabPanel value="notifications">
          <Message v-if="emailError" severity="error" closable @close="emailError = ''">{{ emailError }}</Message>
          <div class="row">
            <ToggleSwitch :model-value="config?.emailUpdates ?? false" input-id="dt-email" @update:model-value="email" />
            <label for="dt-email">Email me what I haven't seen in the bell</label>
          </div>
          <p class="hint">
            Anything still unread a couple of minutes after it happens comes as one email,
            so with the app open you get none. Only tickets you follow: ones you reported,
            hold, commented on or followed.
          </p>
        </TabPanel>
        <TabPanel value="connection">
          <DevTicketConnection @changed="emit('changed')" />
        </TabPanel>
      </TabPanels>
    </Tabs>
    <template #footer>
      <Button label="Done" @click="visible = false" />
    </template>
  </Dialog>
</template>

<style scoped>
.row {
  align-items: center;
  display: flex;
  gap: 0.6rem;
}
.hint {
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
  margin: 0.75rem 0 0;
}
.pi {
  margin-right: 0.3rem;
}
</style>
