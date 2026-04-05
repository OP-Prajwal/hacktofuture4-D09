import { useState } from 'react';
import { Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import Onboarding from './pages/Onboarding/Onboarding';
import Dashboard from './pages/Dashboard/Dashboard';

export interface UserSession {
  type: 'individual' | 'enterprise';
  name: string;
  email: string;
  phone?: string;
  company: string;
  role: string;
}

const App = () => {
  const [session, setSession] = useState<UserSession | null>(null);
  const navigate = useNavigate();

  const handleLaunch = (data: UserSession) => {
    setSession(data);
    navigate('/dashboard');
  };

  const handleLogout = () => {
    setSession(null);
    navigate('/');
  };

  return (
    <Routes>
      <Route path="/" element={<Onboarding onLaunch={handleLaunch} />} />
      <Route 
        path="/dashboard" 
        element={
          session ? (
            <Dashboard session={session} onLogout={handleLogout} />
          ) : (
            <Navigate to="/" replace />
          )
        } 
      />
    </Routes>
  );
}

export default App;