<script setup lang="ts">
// A small rich-text editor whose value is *markdown*, for a dev ticket's
// description or a comment on it.
//
// Markdown in and markdown out, deliberately: tickets store markdown, so the
// editor is a way of typing it, not a different format that has to be converted
// on the way to the API. What is typed here is what is stored and what
// `DevTicketMarkdownBody` renders back.
//
// Underline is switched off in StarterKit because markdown cannot express it --
// keeping it would offer a button whose formatting silently disappeared on
// send. There is no link button either: StarterKit autolinks a pasted or typed
// URL, which is what people actually do, and `[text](url)` still works.
import { Placeholder } from '@tiptap/extensions'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import TurndownService from 'turndown'
import { renderMarkdown } from '../lib/markdown'

const markdown = defineModel<string>({ required: true })
const props = withDefaults(
  defineProps<{ placeholder?: string, rows?: number }>(),
  { placeholder: '', rows: 3 },
)

const turndown = new TurndownService({
  headingStyle: 'atx',
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
  hr: '---',
  emDelimiter: '*',
  strongDelimiter: '**',
})
// Turndown drops unknown inline tags to their text; strikethrough is GFM and
// round-trips, so it is worth teaching.
turndown.addRule('strikethrough', {
  filter: ['s', 'del'],
  replacement: content => `~~${content}~~`,
})

const editor = useEditor({
  content: markdown.value ? renderMarkdown(markdown.value) : '',
  extensions: [
    StarterKit.configure({ underline: false, link: { openOnClick: false } }),
    // Tiptap's own placeholder rather than an absolutely-positioned overlay:
    // it sits on the first line wherever the toolbar happens to leave it.
    Placeholder.configure({ placeholder: () => props.placeholder }),
  ],
  editorProps: { attributes: { class: 'editor-surface' } },
  onUpdate: ({ editor }) => {
    markdown.value = editor.isEmpty ? '' : turndown.turndown(editor.getHTML()).trim()
  },
})

// The parent clears the box after a successful send, so an external change has
// to reach the editor -- but only a genuine one: writing the value back on
// every keystroke would reset the cursor to the start of the document.
watch(markdown, (value) => {
  if (!editor.value) return
  const current = editor.value.isEmpty ? '' : turndown.turndown(editor.value.getHTML()).trim()
  // `emitUpdate: false`, or writing the value in would immediately echo a
  // re-serialised copy of it back out.
  if (value !== current) {
    editor.value.commands.setContent(value ? renderMarkdown(value) : '', { emitUpdate: false })
  }
})

interface Tool {
  key: string
  label: string
  title: string
  icon?: string
  run: () => void
  active: () => boolean
}

const tools = computed<Tool[]>(() => {
  const e = editor.value
  if (!e) return []
  return [
    { key: 'bold', label: 'B', title: 'Bold', run: () => e.chain().focus().toggleBold().run(), active: () => e.isActive('bold') },
    { key: 'italic', label: 'I', title: 'Italic', run: () => e.chain().focus().toggleItalic().run(), active: () => e.isActive('italic') },
    { key: 'strike', label: 'S', title: 'Strikethrough', run: () => e.chain().focus().toggleStrike().run(), active: () => e.isActive('strike') },
    { key: 'code', label: '', icon: 'pi pi-code', title: 'Inline code', run: () => e.chain().focus().toggleCode().run(), active: () => e.isActive('code') },
    { key: 'heading', label: 'H', title: 'Heading', run: () => e.chain().focus().toggleHeading({ level: 3 }).run(), active: () => e.isActive('heading', { level: 3 }) },
    { key: 'bullet', label: '', icon: 'pi pi-list', title: 'Bullet list', run: () => e.chain().focus().toggleBulletList().run(), active: () => e.isActive('bulletList') },
    { key: 'ordered', label: '1.', title: 'Numbered list', run: () => e.chain().focus().toggleOrderedList().run(), active: () => e.isActive('orderedList') },
    { key: 'quote', label: '"', title: 'Quote', run: () => e.chain().focus().toggleBlockquote().run(), active: () => e.isActive('blockquote') },
    { key: 'codeblock', label: '', icon: 'pi pi-server', title: 'Code block', run: () => e.chain().focus().toggleCodeBlock().run(), active: () => e.isActive('codeBlock') },
  ]
})

/** Put text at the cursor. */
function insertText(text: string) {
  editor.value?.chain().focus().insertContent(text).run()
}
defineExpose({ insertText })

onBeforeUnmount(() => editor.value?.destroy())
</script>

<template>
  <div class="editor" :class="{ focused: editor?.isFocused }">
    <div class="toolbar">
      <button
        v-for="tool in tools"
        :key="tool.key"
        type="button"
        class="tool"
        :class="{ on: tool.active(), [tool.key]: true }"
        :title="tool.title"
        :aria-label="tool.title"
        :aria-pressed="tool.active()"
        @click="tool.run()"
      >
        <i v-if="tool.icon" :class="tool.icon" />
        <template v-else>{{ tool.label }}</template>
      </button>
    </div>

    <EditorContent
      :editor="editor"
      class="content"
      :style="{ minHeight: `${props.rows * 1.5}rem` }"
    />
  </div>
</template>

<style scoped>
/* The frame is the editor's, not the ProseMirror node's, so the toolbar sits
   inside the same box a PrimeVue input would draw. */
.editor {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  position: relative;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.editor.focused {
  border-color: var(--p-primary-color);
  box-shadow: 0 0 0 1px var(--p-primary-color);
}
.toolbar {
  border-bottom: 1px solid var(--p-content-border-color);
  display: flex;
  flex-wrap: wrap;
  gap: 0.15rem;
  padding: 0.3rem;
}
.tool {
  align-items: center;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--p-text-muted-color);
  cursor: pointer;
  display: flex;
  font-size: 0.8rem;
  height: 1.75rem;
  justify-content: center;
  line-height: 1;
  min-width: 1.75rem;
  padding: 0 0.35rem;
}
.tool:hover {
  background: var(--p-content-hover-background);
  color: var(--p-text-color);
}
.tool.on {
  background: var(--p-highlight-background);
  color: var(--p-highlight-color);
}
.tool.bold {
  font-weight: 800;
}
.tool.italic {
  font-family: serif;
  font-style: italic;
}
.tool.strike {
  text-decoration: line-through;
}
.tool.quote {
  font-family: serif;
  font-size: 1.1rem;
}
.content :deep(p.is-editor-empty:first-child::before) {
  color: var(--p-text-muted-color);
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
.content {
  font-size: 0.86rem;
  line-height: 1.55;
}
.content :deep(.editor-surface) {
  min-height: inherit;
  outline: none;
  padding: 0.55rem 0.75rem;
}
.content :deep(p),
.content :deep(ul),
.content :deep(ol),
.content :deep(blockquote),
.content :deep(pre) {
  margin: 0 0 0.5rem;
}
.content :deep(> * > *:last-child) {
  margin-bottom: 0;
}
.content :deep(h3) {
  font-size: 0.95rem;
  font-weight: 700;
  margin: 0.5rem 0 0.35rem;
}
.content :deep(ul),
.content :deep(ol) {
  padding-left: 1.25rem;
}
.content :deep(a) {
  color: var(--p-primary-color);
}
.content :deep(code) {
  background: var(--p-content-hover-background);
  border-radius: 4px;
  font-size: 0.82em;
  padding: 0.1em 0.35em;
}
.content :deep(pre) {
  background: var(--p-content-hover-background);
  border-radius: 6px;
  overflow-x: auto;
  padding: 0.5rem 0.65rem;
}
.content :deep(pre code) {
  background: none;
  padding: 0;
}
.content :deep(blockquote) {
  border-left: 3px solid var(--p-content-border-color);
  color: var(--p-text-muted-color);
  padding-left: 0.75rem;
}
</style>
