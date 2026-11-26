<script setup lang="ts">
// "Highlight on page" for a new dev ticket: the ticket dialog steps aside, the
// cursor becomes a pen, and the reporter draws arrows, boxes, circles or freehand
// marks over the page itself. Done captures what is on screen with the marks on top
// and hands it back as a PNG attachment.
//
// The page is captured as the browser shows it: Chrome's tab capture
// (getDisplayMedia, preferring this tab) is one "share this tab" click and takes
// the real pixels at once. Copying the DOM instead (modern-screenshot) needs no
// prompt but re-derives every element's style, 20 s and more on a full page, so
// it is only the fallback when the prompt is refused or not offered. The layer
// is hidden while the picture is taken and the marks are drawn on afterwards.
import { domToCanvas } from 'modern-screenshot'

const emit = defineEmits<{ done: [file: File], cancel: [] }>()

type Tool = 'arrow' | 'rect' | 'ellipse' | 'pen'
interface Point { x: number, y: number }
interface Mark { tool: Tool, points: Point[] }

const TOOLS: { value: Tool, label: string, icon: string }[] = [
  { value: 'arrow', label: 'Arrow', icon: 'pi pi-arrow-up-right' },
  { value: 'rect', label: 'Box', icon: 'pi pi-stop' },
  { value: 'ellipse', label: 'Circle', icon: 'pi pi-circle' },
  { value: 'pen', label: 'Draw', icon: 'pi pi-pencil' },
]
const RED = '#ef4444'
// A pen, its tip at the hotspot (bottom-left).
const PEN_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
  + '<path d="M3 21l1.5-5.5L16 4l4 4L8.5 19.5z" fill="#ef4444" stroke="#fff" stroke-width="1.5"/>'
  + '<path d="M3 21l1.5-5.5 4 4z" fill="#111827"/></svg>',
)}") 2 22, crosshair`

const tool = ref<Tool>('arrow')
const marks = ref<Mark[]>([])
const drawing = ref<Mark | null>(null)
const capturing = ref(false)
const slow = ref(false) // the DOM fallback is running; say so
const failed = ref('')
const canvas = ref<HTMLCanvasElement | null>(null)
const dpr = window.devicePixelRatio || 1

function size() {
  const c = canvas.value
  if (!c) return
  c.width = Math.round(window.innerWidth * dpr)
  c.height = Math.round(window.innerHeight * dpr)
  redraw()
}

function stroke(ctx: CanvasRenderingContext2D, path: () => void) {
  // White under red, so a mark reads on dark and light parts of the page alike.
  for (const [colour, width] of [['#ffffff', 7], [RED, 4]] as const) {
    ctx.strokeStyle = colour
    ctx.lineWidth = width * dpr
    ctx.beginPath()
    path()
    ctx.stroke()
  }
}

function paint(ctx: CanvasRenderingContext2D, mark: Mark) {
  const pts = mark.points.map(p => ({ x: p.x * dpr, y: p.y * dpr }))
  const a = pts[0]!
  const b = pts.at(-1)!
  if (mark.tool === 'pen') {
    stroke(ctx, () => pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))))
  }
  else if (mark.tool === 'rect') {
    if (Math.abs(b.x - a.x) < 4 || Math.abs(b.y - a.y) < 4) return
    stroke(ctx, () => ctx.rect(a.x, a.y, b.x - a.x, b.y - a.y))
  }
  else if (mark.tool === 'ellipse') {
    const rx = Math.abs(b.x - a.x) / 2
    const ry = Math.abs(b.y - a.y) / 2
    if (rx < 2 || ry < 2) return
    stroke(ctx, () => ctx.ellipse((a.x + b.x) / 2, (a.y + b.y) / 2, rx, ry, 0, 0, Math.PI * 2))
  }
  else {
    const angle = Math.atan2(b.y - a.y, b.x - a.x)
    const head = 16 * dpr
    if (Math.hypot(b.x - a.x, b.y - a.y) < 4) return
    stroke(ctx, () => {
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.moveTo(b.x - head * Math.cos(angle - 0.45), b.y - head * Math.sin(angle - 0.45))
      ctx.lineTo(b.x, b.y)
      ctx.lineTo(b.x - head * Math.cos(angle + 0.45), b.y - head * Math.sin(angle + 0.45))
    })
  }
}

function redraw() {
  const c = canvas.value
  const ctx = c?.getContext('2d')
  if (!c || !ctx) return
  ctx.clearRect(0, 0, c.width, c.height)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const m of drawing.value ? [...marks.value, drawing.value] : marks.value) paint(ctx, m)
}

function down(e: PointerEvent) {
  ;(e.target as Element).setPointerCapture(e.pointerId)
  drawing.value = { tool: tool.value, points: [{ x: e.clientX, y: e.clientY }] }
}
function move(e: PointerEvent) {
  const m = drawing.value
  if (!m) return
  const p = { x: e.clientX, y: e.clientY }
  if (m.tool === 'pen') m.points.push(p)
  else m.points = [m.points[0]!, p]
  redraw()
}
function up() {
  if (drawing.value && drawing.value.points.length > 1) marks.value.push(drawing.value)
  drawing.value = null
  redraw()
}
function undo() {
  marks.value.pop()
  redraw()
}

function frames() {
  return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
}

/** One frame of this tab, as the screen shows it. Null when refused or not offered. */
async function grabTab(): Promise<HTMLCanvasElement | null> {
  if (!navigator.mediaDevices?.getDisplayMedia) return null
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: 'browser' }, audio: false,
      // Chrome: offer this tab first, and allow it to be chosen.
      preferCurrentTab: true, selfBrowserSurface: 'include',
    } as DisplayMediaStreamOptions)
  }
  catch {
    return null
  }
  try {
    const video = document.createElement('video')
    video.muted = true
    video.srcObject = stream
    await video.play()
    await frames() // the hidden toolbar has gone from what the stream sees
    const shot = document.createElement('canvas')
    shot.width = video.videoWidth
    shot.height = video.videoHeight
    shot.getContext('2d')!.drawImage(video, 0, 0)
    return shot
  }
  finally {
    stream.getTracks().forEach(t => t.stop())
  }
}

/** The fallback: the page rebuilt from the DOM. Slow, but needs no prompt. */
async function copyDom(): Promise<HTMLCanvasElement> {
  slow.value = true
  await frames()
  return domToCanvas(document.documentElement, {
    scale: dpr,
    width: window.innerWidth,
    height: window.innerHeight,
    // The visible part of a page scrolled down, not its top.
    style: { transform: `translate(${-window.scrollX}px, ${-window.scrollY}px)` },
    filter: node => !(node instanceof Element && node.classList.contains('dt-markup')),
  })
}

async function done() {
  capturing.value = true
  failed.value = ''
  await nextTick()
  try {
    const page = (await grabTab()) ?? (await copyDom())
    const out = document.createElement('canvas')
    out.width = page.width
    out.height = page.height
    const ctx = out.getContext('2d')!
    ctx.drawImage(page, 0, 0)
    ctx.drawImage(canvas.value!, 0, 0, out.width, out.height)
    const blob = await new Promise<Blob | null>(resolve => out.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('The picture could not be made.')
    const stamp = new Date().toTimeString().slice(0, 8).replace(/:/g, '')
    emit('done', new File([blob], `highlight-${stamp}.png`, { type: 'image/png' }))
  }
  catch (e) {
    failed.value = `Could not capture the page: ${e instanceof Error ? e.message : e}`
    capturing.value = false
    slow.value = false
  }
}

function key(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') undo()
}

onMounted(() => {
  size()
  window.addEventListener('resize', size)
  window.addEventListener('keydown', key)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', size)
  window.removeEventListener('keydown', key)
})
</script>

<template>
  <Teleport to="body">
    <div class="dt-markup">
      <canvas
        v-show="!capturing" ref="canvas" class="layer" :style="{ cursor: PEN_CURSOR }"
        @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up"
      />
      <div v-show="!capturing" class="bar" @pointerdown.stop>
        <span class="hint">Mark the problem on the page</span>
        <SelectButton
          v-model="tool" :options="TOOLS" option-value="value" option-label="label"
          :allow-empty="false" size="small"
        >
          <template #option="{ option }"><i :class="option.icon" /> {{ option.label }}</template>
        </SelectButton>
        <Button icon="pi pi-undo" text size="small" aria-label="Undo" :disabled="!marks.length" @click="undo" />
        <Button label="Cancel" severity="secondary" text size="small" @click="emit('cancel')" />
        <Button label="Done" icon="pi pi-check" size="small" @click="done" />
      </div>
      <div v-if="slow" class="bar">
        <ProgressSpinner style="width: 1.1rem; height: 1.1rem" stroke-width="5" /> Capturing the page…
      </div>
      <div v-if="failed" class="bar failed" @pointerdown.stop>
        {{ failed }} <Button label="Back" text size="small" @click="emit('cancel')" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dt-markup { inset: 0; position: fixed; z-index: 2100; }
.layer { display: block; height: 100vh; touch-action: none; width: 100vw; }
.bar {
  align-items: center;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  box-shadow: 0 6px 24px rgb(0 0 0 / 0.18);
  display: flex;
  gap: 0.5rem;
  left: 50%;
  padding: 0.4rem 0.6rem;
  position: fixed;
  top: 0.75rem;
  transform: translateX(-50%);
}
.bar.failed { color: var(--p-red-600); top: 4rem; }
.hint { color: var(--p-text-muted-color); font-size: 0.85rem; white-space: nowrap; }
</style>
