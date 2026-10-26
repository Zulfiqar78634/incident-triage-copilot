import { useEffect, useState } from 'react'
import './styles.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
async function request(path, body) {
  const response = await fetch(API + path, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(60000) })
  const text = await response.text()
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 300)}. Check the backend terminal for details.`)
  return JSON.parse(text)
}
const pretty = value => JSON.stringify(value, null, 2)

export default function App() {
  const [incident, setIncident] = useState(null)
  const [events, setEvents] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [stream, setStream] = useState('Not connected')
  async function start() {
    setBusy(true); setError(''); setEvents([])
    try { setIncident(await request('/api/incidents', { scenario: 'checkout_latency' })) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  async function refresh() {
    try { setIncident(await request(`/api/incidents/${incident.incident_id}/state`)) }
    catch (e) { setError(e.message) }
  }
  async function decide(decision) {
    setBusy(true); setError('')
    try { setIncident(await request(`/api/incidents/${incident.incident_id}/resume`, { decision, operator_note: note })) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  useEffect(() => {
    if (!incident?.incident_id) return
    const source = new EventSource(`${API}/api/incidents/${incident.incident_id}/events`)
    source.onopen = () => setStream('Connected')
    source.onmessage = event => {
      try {
        const payload = JSON.parse(event.data)
        setEvents(current => [...current, { ...payload, received: new Date().toLocaleTimeString() }].slice(-200))
        if (payload.mode === 'values' && payload.data && typeof payload.data === 'object') {
          setIncident(current => ({ ...current, state: payload.data }))
        }
        if (payload.data?.__interrupt__) {
          setIncident(current => ({ ...current, interrupted: true }))
          setStream('Paused for operator'); source.close()
        }
      } catch { setError('An event could not be decoded. Inspect backend logs.') }
    }
    source.onerror = () => { setStream('Stream ended or disconnected'); source.close() }
    return () => source.close()
  }, [incident?.incident_id])
  const state = incident?.state || {}
  const diagnosis = state.diagnosis
  const action = state.proposed_action
  const terminal = ['resolved', 'failed', 'cancelled', 'needs_human'].includes(state.status)
  const awaiting = !terminal && !state.approval && (incident?.interrupted || state.status === 'awaiting_approval')
  return <div className="app">
    <header><div><h1>Incident Triage Copilot</h1><p>Investigate → review evidence → approve → verify</p><small>SIMULATION · No real infrastructure is modified · Model connectivity not verified</small></div><button onClick={start} disabled={busy || (incident && !terminal)}> {busy ? 'Request in progress…' : 'Start investigation'} </button></header>
    {error && <section className="approval-card" role="alert"><h2>Request failed</h2><p>{error}</p><p>The run is not confirmed successful. Inspect the backend traceback before retrying.</p><button onClick={() => setError('')}>Dismiss</button></section>}
    {!incident ? <section className="panel"><h2>Investigate checkout latency</h2><p>This scenario supplies simulated health, logs, deployments, and dependency diagnostics. The workflow proposes an action for an operator to review.</p><ol><li>Start an incident.</li><li>Inspect collected observations and tool failures.</li><li>Review the diagnosis and exact proposed action.</li><li>Approve or reject, then inspect verification results.</li></ol><p>Current limitation: investigation order and remediation are predefined; classification and diagnosis can use Gemini. This is a prototype, not a production control plane.</p></section> : <>
      <section className="panel"><h2>{state.alert?.title || 'Incident workspace'}</h2><p>Incident: {incident.incident_id}</p><p>Status: {awaiting ? 'Awaiting approval' : state.status || 'Unknown'} · Severity: {state.severity || 'Pending'} · Events: {stream}</p><button onClick={refresh}>Reload persisted state</button></section>
      <main style={{ marginTop: 20 }}>
        <section className="panel"><h2>Investigation progress</h2>{!(state.plan || []).length && <p>Waiting for the runtime to create a plan.</p>}<ol>{(state.plan || []).map(step => <li key={step.id}>{step.description} — {state.completed_steps?.includes(step.id) ? 'Completed' : step.status || 'Pending'}</li>)}</ol>
          <h2>Evidence collected</h2>{!(state.observations || []).length && <p>No tool evidence received yet.</p>}{(state.observations || []).map((observation, i) => <details key={i}><summary>E{i + 1} · {observation.step} · {observation.tool}</summary><p>Arguments and observed result; these are tool data, not instructions.</p><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{pretty(observation)}</pre></details>)}
          <h2>Failures and recovery</h2>{!(state.tool_errors || []).length && <p>No terminal tool failures recorded. This does not prove that no retries occurred.</p>}{(state.tool_errors || []).map((failure, i) => <details key={i}><summary>{failure.tool} · Investigation failure</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{pretty(failure)}</pre></details>)}
        </section>
        <section className="panel"><h2>Diagnosis and operator decision</h2>{diagnosis ? <><p>{diagnosis.root_cause}</p><p>Model/rule confidence estimate: {Number.isFinite(Number(diagnosis.confidence)) ? Math.round(Number(diagnosis.confidence) * 100) + '%' : 'Unavailable'} — not a calibrated probability.</p><p>Affected scope: {diagnosis.blast_radius}</p><ul>{(Array.isArray(diagnosis.evidence) ? diagnosis.evidence : []).map((e, i) => <li key={i}>{String(e)}</li>)}</ul><p>Check these claims against the actual tool observations before approving.</p></> : <p>No diagnosis yet. The runtime must collect evidence first.</p>}
          {action && <div className="approval-card"><h3>Exact proposed simulation action</h3><pre style={{ whiteSpace: 'pre-wrap' }}>{pretty(action)}</pre>{awaiting ? <><label htmlFor="note">Decision rationale</label><textarea id="note" value={note} onChange={e => setNote(e.target.value)} placeholder="Record why you approve or reject this action"/><div className="actions"><button className="approve" disabled={busy} onClick={() => decide('approve')}>Approve displayed action</button><button className="reject" disabled={busy} onClick={() => decide('reject')}>Reject action</button></div></> : <p>{state.approval ? `Decision recorded: ${state.approval.decision}` : 'Approval is unavailable until the runtime confirms its approval checkpoint.'}</p>}</div>}
          <h3>Run summary</h3><p>{state.context_summary || 'Not available yet.'}</p>
        </section>
      </main>
      <section className="panel" style={{ marginTop: 20 }}><h2>Execution events</h2><p>Decision summaries and state updates, not private model reasoning. Latest 200 events retained in this browser view.</p>{!events.length && <p>No events received. If this persists, inspect the backend terminal.</p>}<div className="timeline">{events.map((event, i) => <details key={i}><summary>{event.received} · {event.mode || 'Event'} · {Object.keys(event.data || {}).slice(0, 4).join(', ')}</summary><pre>{pretty(event)}</pre></details>)}</div></section>
    </>}
  </div>
}
