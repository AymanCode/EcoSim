import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const root = createRoot(document.getElementById('root'))

// ?view=next opens the new Run screen. It loads on demand, so the classic
// dashboard never pulls in its code, styles or fonts.
if (new URLSearchParams(window.location.search).get('view') === 'next') {
  import('./next/NextApp.jsx').then(({ default: NextApp }) => root.render(<StrictMode><NextApp /></StrictMode>))
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
