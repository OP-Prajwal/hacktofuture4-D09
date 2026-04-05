import { useState } from 'react';
import Onboarding from './Onboarding';
import Dashboard from './Dashboard';

export interface UserSession {
  type: 'individual' | 'enterprise';
  name: string;
  email: string;
  phone?: string;
  company: string;
  role: string;
}

const App = () => {
  const [view, setView] = useState<'onboarding' | 'dashboard'>('onboarding');
  const [session, setSession] = useState<UserSession | null>(null);

  const handleLaunch = (data: UserSession) => {
    setSession(data);
    setView('dashboard');
  };

  return (
    <>
      {view === 'onboarding' && <Onboarding onLaunch={handleLaunch} />}
      {view === 'dashboard' && session && (
        <Dashboard 
          session={session} 
          onLogout={() => { setView('onboarding'); setSession(null); }} 
        />
      )}
    </>
  );
}

export default App;