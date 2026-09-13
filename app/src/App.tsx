import { HashRouter, Route, Routes } from 'react-router-dom'
import { Flux } from './pages/Flux'
import { FicheAnnonce } from './pages/FicheAnnonce'

// HashRouter (pas BrowserRouter) : compatible sans configuration serveur
// particulière, et fonctionne tel quel dans une webview Capacitor/file://
// le jour où l'app bascule en natif — voir CAPACITOR.md.
export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Flux />} />
        <Route path="/annonce/:id" element={<FicheAnnonce />} />
      </Routes>
    </HashRouter>
  )
}
