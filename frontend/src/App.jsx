import { useEffect, useState } from 'react'
import { connectToEvents, getIncidentState, resumeIncident, startIncident } from './api.js'

export default function App() {
  const [incident, setIncident] = useState(null)
  const [events, setEvents] = useState([])
  const [operatorNote, setOperatorNote] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleStart() {
    setLoading(true)
    setEvents([])
    const result = await startIncident('checkout_latency')
    setIncident(result)
    setLoading(false)
  }

  useEffect(() => {
    if (!incident?.incident_id) return

    const source = connectToEvents(incident.incident_id, (event) => {
      setEvents((current) => [...current, event])
    })

    return () => source.close()
  }, [incident?.incident_id])

  async function handleDecision(decision) {
    if (!incident?.incident_id) return
    setLoading(true)
    const result = await resumeIncident(incident.incident_id, decision, operatorNote)
    setIncident(result)
    setLoading(false)
  }

  async function refreshState() {
    if (!incident?.incident_id) return
    const result = await getIncidentState(incident.incident_id)
    setIncident(result)
  }

  const state = incident?.state || {}
  const diagnosis = state.diagnosis
  const action = state.proposed_action
  const awaitingApproval = incident?.interrupted || state.status === 'awaiting_approval'

  return (
    <div className="app">
      <header>
        <div>
          <h1>Incident Triage Copilot</h1>
          <p>Operator-in-the-loop investigation and remediation</p>
        </div>
        <button onClick={handleStart} disabled={loading}>
          Start checkout latency incident
        </button>
      </header>

      {!incident && <p className="empty">Start an incident to begin the investigation.</p>}

      {incident && (
        <main>
          <section className="panel">
            <h2>Incident</h2>
            <p><strong>ID:</strong> {incident.incident_id}</p>
            <p><strong>Status:</strong> {state.status || 'investigating'}</p>
            <p><strong>Severity:</strong> {state.severity || 'unknown'}</p>

            <h3>Plan</h3>
            <ul>
              {(state.plan || []).map((step) => (
                <li key={step.id}>
                  <strong>{step.description}</strong> — {state.completed_steps?.includes(step.id) ? 'done' : step.status}
                </li>
              ))}
            </ul>

            <h3>Agent timeline</h3>
            <div className="timeline">
              {events.length === 0 && <p>Waiting for agent events...</p>}
              {events.map((event, index) => (
                <pre key={index}>{JSON.stringify(event, null, 2)}</pre>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Decision panel</h2>

            {diagnosis ? (
              <>
                <h3>Diagnosis</h3>
                <p>{diagnosis.root_cause}</p>
                <p><strong>Confidence:</strong> {Math.round(diagnosis.confidence * 100)}%</p>
                <p><strong>Blast radius:</strong> {diagnosis.blast_radius}</p>
                <ul>
                  {diagnosis.evidence.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p>The agent is still collecting evidence.</p>
            )}

            {action && (
              <div className="approval-card">
                <h3>Proposed remediation</h3>
                <p><strong>Action:</strong> {action.action_type}</p>
                <p><strong>Service:</strong> {action.service}</p>
                <p><strong>Target version:</strong> {action.target_version}</p>
                <p><strong>Risk:</strong> {action.risk}</p>
                <p><strong>Reason:</strong> {action.reason}</p>

                <textarea
                  value={operatorNote}
                  onChange={(event) => setOperatorNote(event.target.value)}
                  placeholder="Operator note / approval rationale"
                />

                <div className="actions">
                  <button className="approve" onClick={() => handleDecision('approve')} disabled={loading}>
                    Approve remediation
                  </button>
                  <button className="reject" onClick={() => handleDecision('reject')} disabled={loading}>
                    Reject
                  </button>
                  <button onClick={refreshState}>Refresh state</button>
                </div>
              </div>
            )}

            {awaitingApproval && !action && <p>Waiting for operator decision.</p>}
          </section>
        </main>
      )}
    </div>
  )
}
