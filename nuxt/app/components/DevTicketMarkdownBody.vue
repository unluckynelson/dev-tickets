<script setup lang="ts">
// Rendered markdown -- a dev ticket's description or a comment.
//
// The HTML is sanitised in `renderMarkdown` before it gets here; `v-html` on
// anything that has not been through that is a stored-XSS hole.
import { renderMarkdown } from '../lib/markdown'

const props = defineProps<{ text: string }>()

const html = computed(() => renderMarkdown(props.text))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- sanitised by renderMarkdown -->
  <div class="md" v-html="html" />
</template>

<style scoped>
.md {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  font-size: 0.86rem;
  line-height: 1.55;
  overflow-wrap: anywhere;
  padding: 0.6rem 0.75rem;
}
.md :deep(> *:first-child) {
  margin-top: 0;
}
.md :deep(> *:last-child) {
  margin-bottom: 0;
}
.md :deep(p),
.md :deep(ul),
.md :deep(ol),
.md :deep(blockquote),
.md :deep(pre),
.md :deep(table) {
  margin: 0 0 0.6rem;
}
.md :deep(h1),
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.3;
  margin: 1rem 0 0.4rem;
}
.md :deep(ul),
.md :deep(ol) {
  padding-left: 1.25rem;
}
.md :deep(li) {
  margin: 0.15rem 0;
}
.md :deep(li > p) {
  margin: 0;
}
.md :deep(a) {
  color: var(--p-primary-color);
}
.md :deep(code) {
  background: var(--p-content-hover-background);
  border-radius: 4px;
  font-size: 0.82em;
  padding: 0.1em 0.35em;
}
/* Code blocks are the one thing that must not wrap -- a wrapped stack trace or
   log line is unreadable -- so they scroll inside their own box instead of
   widening the dialog. */
.md :deep(pre) {
  background: var(--p-content-hover-background);
  border-radius: 6px;
  overflow-x: auto;
  padding: 0.6rem 0.75rem;
}
.md :deep(pre code) {
  background: none;
  padding: 0;
  white-space: pre;
}
.md :deep(blockquote) {
  border-left: 3px solid var(--p-content-border-color);
  color: var(--p-text-muted-color);
  padding-left: 0.75rem;
}
.md :deep(hr) {
  border: none;
  border-top: 1px solid var(--p-content-border-color);
  margin: 0.8rem 0;
}
.md :deep(table) {
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}
.md :deep(th),
.md :deep(td) {
  border: 1px solid var(--p-content-border-color);
  padding: 0.3rem 0.5rem;
  text-align: left;
}
.md :deep(img) {
  max-width: 100%;
}
/* An image from behind someone else's sign-in shows broken; its alt text is the
   useful part. */
.md :deep(img[alt]) {
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
}
</style>
