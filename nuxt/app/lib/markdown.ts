/**
 * Ticket descriptions and comments are markdown, so they are rendered rather than
 * printed -- and rendering means sanitising: a description is free text written by
 * whoever filed it, and markdown lets raw HTML through by design, so an unsanitised
 * `v-html` would be a stored-XSS hole. Every string goes marked -> DOMPurify.
 */
import DOMPurify from 'dompurify'
import { Marked } from 'marked'

// An instance of our own, so the host's `marked` settings are never touched.
const marked = new Marked({
  gfm: true,
  // A single newline is a line break, as people type in a ticket.
  breaks: true,
})

let hooked = false

/** Links in a ticket point at PRs, logs, other pages: none of them belong in this tab. */
function addLinkHooks() {
  if (hooked) return
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A' && node.hasAttribute('href')) {
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noopener noreferrer')
    }
  })
  hooked = true
}

/**
 * Markdown to sanitised HTML, safe to hand to `v-html`.
 *
 * Where DOMPurify cannot run (no DOM, e.g. a server-rendered pass) the escaped
 * source comes back instead: a worse read, but it can never inject.
 */
export function renderMarkdown(source: string): string {
  if (!source) return ''
  if (!DOMPurify.isSupported) {
    return `<pre>${source.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]!))}</pre>`
  }
  addLinkHooks()
  return DOMPurify.sanitize(marked.parse(source, { async: false }))
}
