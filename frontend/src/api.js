const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function startIncident(scenario = 'checkout_latency') {
  const response = await fetch(`${API}/api/incidents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  })
  return response.json()
}

export async function getIncidentState(incidentId) {
  const response = await fetch(`${API}/api/incidents/${incidentId}/state`)
  return response.json()
}

export async function resumeIncident(incidentId, decision, operatorNote) {
  const response = await fetch(`${API}/api/incidents/${incidentId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      decision,
      operator_note: operatorNote,
    }),
  })
  return response.json()
}

export function connectToEvents(incidentId, onEvent) {
  const source = new EventSource(`${API}/api/incidents/${incidentId}/events`)

  source.onmessage = (event) => {
    try {
      onEvent(JSON.parse(event.data))
    } catch {
      // Ignore malformed keepalive events.
    }
  }

  return source
}
