/**
 * The layer's own client for the dev-tickets backend. It shares nothing with the
 * host app's API code: it reads `runtimeConfig.public.devTickets` and talks to that
 * endpoint only.
 *
 * Auth is Django's session cookie, so every request is credentialed, and Django's
 * CSRF check refuses every POST without a token -- GraphQL reads included, since
 * they are POSTs too. The token is fetched once from the csrf view and sent back as
 * `X-CSRFToken`; a 403 (a token rotated by a sign-in, say) fetches it again and
 * retries once.
 */

interface GraphQLResponse<T> {
  data?: T
  errors?: { message: string }[]
}

export class DevTicketsError extends Error {}

/** One token for the whole page, whichever component asks first. */
let token: string | null = null
let pending: Promise<string | null> | null = null

function cookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const hit = document.cookie.split('; ').find(row => row.startsWith(`${name}=`))
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null
}

function status(e: unknown): number | undefined {
  return (e as { status?: number, statusCode?: number })?.status
    ?? (e as { statusCode?: number })?.statusCode
}

export function useDevTicketsApi() {
  const settings = useRuntimeConfig().public.devTickets as {
    endpoint: string
    csrfUrl: string
    boardPath: string
  }
  const endpoint = settings.endpoint

  /** The backend's origin ('' when the endpoint is same-origin and relative). */
  function origin(): string {
    if (/^https?:\/\//.test(endpoint)) return new URL(endpoint).origin
    return ''
  }

  function csrfUrl(): string {
    return settings.csrfUrl || endpoint.replace(/graphql\/?$/, 'csrf/')
  }

  /** `/devtickets-files/...` on the backend that serves the endpoint. */
  function filesUrl(path: string): string {
    return `${origin()}/devtickets-files/${path.replace(/^\/+/, '')}`
  }

  /**
   * The CSRF token. The csrf view sets the `csrftoken` cookie; when it also answers
   * `{ csrfToken }` that is used, so a backend on another host (whose cookie this
   * page cannot read) still works.
   */
  async function csrfToken(refresh = false): Promise<string | null> {
    if (token && !refresh) return token
    if (!refresh) token = cookie('csrftoken')
    if (token && !refresh) return token
    pending ??= $fetch<{ csrfToken?: string } | string>(csrfUrl(), { credentials: 'include' })
      .then(body => (typeof body === 'object' && body?.csrfToken) || cookie('csrftoken'))
      .catch(() => cookie('csrftoken'))
      .finally(() => { pending = null })
    token = await pending
    return token
  }

  async function post<T>(url: string, body: FormData | Record<string, unknown>, json: boolean): Promise<T> {
    const send = async (refresh: boolean) => {
      const csrf = await csrfToken(refresh)
      return $fetch<T>(url, {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...(json ? { 'Content-Type': 'application/json' } : {}),
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
        },
        body,
      })
    }
    try {
      return await send(false)
    }
    catch (e) {
      if (status(e) !== 403) throw e
      return await send(true)
    }
  }

  async function graphql<T>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
    const response = await post<GraphQLResponse<T>>(endpoint, { query, variables }, true)
    if (response.errors?.length) {
      throw new DevTicketsError(response.errors.map(e => e.message).join('; '))
    }
    if (!response.data) throw new DevTicketsError('The dev-tickets server sent no data.')
    return response.data
  }

  /** Multipart POST under `/devtickets-files/`. */
  function upload<T = unknown>(path: string, body: FormData): Promise<T> {
    return post<T>(filesUrl(path), body, false)
  }

  return { graphql, upload, filesUrl, boardPath: settings.boardPath }
}
