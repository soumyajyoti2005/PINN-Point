import { useState } from 'react'
import Landing from './Landing'
import Dashboard from './Dashboard'

function App() {
  const [route, setRoute] = useState('landing')

  return (
    <>
      {route === 'landing' && <Landing onStart={() => setRoute('dashboard')} />}
      {route === 'dashboard' && <Dashboard onBack={() => setRoute('landing')} />}
    </>
  )
}

export default App
