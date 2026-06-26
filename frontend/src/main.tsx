import { createRoot } from 'react-dom/client'
import App from '@/App.tsx'
import './styles.css'

// No StrictMode: this app sets up real intervals / audio nodes in effects, and
// StrictMode's double-invoke in dev would spawn duplicates.
createRoot(document.getElementById('root')!).render(<App />)
