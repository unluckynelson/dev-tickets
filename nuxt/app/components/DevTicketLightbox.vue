<script setup lang="ts">
// A ticket's screenshots, full size over the page. Arrows (or the keys) step
// through them; the corner buttons open the one shown in a new tab or save it.

const props = defineProps<{ images: { id: string, name: string }[] }>()
const index = defineModel<number | null>('index', { required: true })
const { attachmentUrl } = useDevTickets()

const current = computed(() => (index.value === null ? null : props.images[index.value] ?? null))

function step(by: number) {
  if (index.value === null || props.images.length < 2) return
  index.value = (index.value + by + props.images.length) % props.images.length
}
function close() {
  index.value = null
}

function key(e: KeyboardEvent) {
  if (!current.value) return
  if (e.key === 'Escape') {
    // Only the lightbox closes, not the ticket dialog under it.
    e.stopImmediatePropagation()
    close()
  }
  else if (e.key === 'ArrowRight') step(1)
  else if (e.key === 'ArrowLeft') step(-1)
}
onMounted(() => window.addEventListener('keydown', key, true))
onBeforeUnmount(() => window.removeEventListener('keydown', key, true))
</script>

<template>
  <Teleport to="body">
    <div v-if="current" class="lightbox" @click.self="close">
      <div class="top">
        <span class="name">{{ current.name }}<template v-if="images.length > 1"> · {{ index! + 1 }} of {{ images.length }}</template></span>
        <a
          v-tooltip.bottom="'Open in a new window'" :href="attachmentUrl(current.id)" target="_blank" rel="noopener"
          class="tool" aria-label="Open in a new window"
        ><i class="pi pi-external-link" /></a>
        <a
          v-tooltip.bottom="'Download'" :href="attachmentUrl(current.id, true)" class="tool" aria-label="Download"
        ><i class="pi pi-download" /></a>
        <button type="button" class="tool" aria-label="Close" @click="close"><i class="pi pi-times" /></button>
      </div>
      <button v-if="images.length > 1" type="button" class="nav prev" aria-label="Previous" @click="step(-1)">
        <i class="pi pi-chevron-left" />
      </button>
      <img :key="current.id" :src="attachmentUrl(current.id)" :alt="current.name" class="shot" @click.self="close">
      <button v-if="images.length > 1" type="button" class="nav next" aria-label="Next" @click="step(1)">
        <i class="pi pi-chevron-right" />
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
/* Above PrimeVue's dialogs (z ~1100). */
.lightbox {
  align-items: center;
  background: rgb(10 14 22 / 88%);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 3.5rem 4rem 1.5rem;
  position: fixed;
  z-index: 2000;
}
.shot {
  border-radius: 4px;
  box-shadow: 0 10px 40px rgb(0 0 0 / 50%);
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
.top {
  align-items: center;
  color: #e5e7eb;
  display: flex;
  gap: 0.25rem;
  left: 0;
  padding: 0.6rem 0.8rem;
  position: absolute;
  right: 0;
  top: 0;
}
.name {
  flex: 1;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool,
.nav {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 50%;
  color: #e5e7eb;
  cursor: pointer;
  display: inline-flex;
  height: 2.4rem;
  justify-content: center;
  text-decoration: none;
  width: 2.4rem;
}
.tool:hover,
.nav:hover {
  background: rgb(255 255 255 / 12%);
}
.nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
}
.nav .pi {
  font-size: 1.4rem;
}
.prev { left: 0.8rem; }
.next { right: 0.8rem; }
</style>
