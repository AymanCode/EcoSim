import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { pickView } from './next/pickView.js'

const root = createRoot(document.getElementById('root'))

// ?view=next opens the new Run screen; anything else the classic dashboard.
// Each loads on demand, so neither pulls in the other's code, styles or fonts.
const load = pickView(window.location.search) === 'next'
  ? import('./next/NextApp.jsx')
  : Promise.all([import('./index.css'), import('./App.jsx')]).then(([, app]) => app)

load
  .then(({ default: View }) => root.render(<StrictMode><View /></StrictMode>))
  .catch(error => {
    console.error(error)
    root.render(<p style={{ font: '15px system-ui, sans-serif', padding: 24 }}>EcoSim could not load. Reload the page to try again.</p>)
  })
