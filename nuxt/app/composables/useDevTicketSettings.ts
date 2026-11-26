/**
 * The Settings dialog's calls: lanes over GraphQL (so in client mode they edit the
 * hub's lanes, which are the board's), and this install's own mode and hub
 * connection over `/devtickets/settings/` (never forwarded).
 *
 * Every lane change reloads the shared config, which the ticket dialog's status
 * picker and the board read.
 */
import type { ConnectionState, ConnectionTest, Lane, TrackerMode } from '../lib/types'

const LANE = 'id name type onBoard tickets'

export function useDevTicketSettings() {
  const { graphql, settingsCall } = useDevTicketsApi()
  const { loadConfig } = useDevTickets()

  async function fetchLanes(): Promise<Lane[]> {
    const data = await graphql<{ devTicketLanes: Lane[] }>(`{ devTicketLanes { ${LANE} } }`)
    return data.devTicketLanes
  }

  async function saveLane(lane: { id: string | null, name: string, type: string, onBoard: boolean }) {
    await graphql(`
      mutation($id: String, $n: String!, $t: String!, $b: Boolean!) {
        saveDevTicketLane(id: $id, name: $n, type: $t, onBoard: $b) { id }
      }`, { id: lane.id, n: lane.name, t: lane.type, b: lane.onBoard })
    await loadConfig(true)
  }

  async function reorderLanes(ids: string[]) {
    await graphql('mutation($ids: [String!]!) { reorderDevTicketLanes(ids: $ids) { id } }', { ids })
    await loadConfig(true)
  }

  /** Returns how many tickets moved to `moveTo`. */
  async function deleteLane(id: string, moveTo: string | null): Promise<number> {
    const data = await graphql<{ deleteDevTicketLane: number }>(
      'mutation($id: String!, $to: String) { deleteDevTicketLane(id: $id, moveTo: $to) }',
      { id, to: moveTo },
    )
    await loadConfig(true)
    return data.deleteDevTicketLane
  }

  const loadConnection = () => settingsCall<ConnectionState>('')

  interface ConnectionInput { mode: TrackerMode, hubUrl?: string, hubApiKey?: string, source?: string }

  const testConnection = (input: ConnectionInput) =>
    settingsCall<ConnectionTest>('connection/test/', { ...input })

  const saveConnection = (input: ConnectionInput) =>
    settingsCall<ConnectionState>('connection/', { ...input })

  const addEnvironment = (name: string, readOnly: boolean) =>
    settingsCall<ConnectionState>('clients/', { name, readOnly })

  const rotateEnvironment = (id: string) =>
    settingsCall<ConnectionState>(`clients/${encodeURIComponent(id)}/rotate/`, {})

  const updateEnvironment = (id: string, changes: { readOnly?: boolean, revoke?: boolean }) =>
    settingsCall<ConnectionState>(`clients/${encodeURIComponent(id)}/`, changes)

  return {
    fetchLanes, saveLane, reorderLanes, deleteLane,
    loadConnection, testConnection, saveConnection,
    addEnvironment, rotateEnvironment, updateEnvironment,
  }
}
