import { useState } from 'react';
import './Onboarding.css';

import type { UserSession } from '../../App';

interface OnboardingProps {
  onLaunch: (data: UserSession) => void;
}

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

const Onboarding = ({ onLaunch }: OnboardingProps) => {
  const [theme, setTheme] = useState('dark');
  const [mode, setMode] = useState<'intro' | 'register' | 'login'>('intro');
  const [step, setStep] = useState(0);
  const [type, setType] = useState<string | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Data stores
  const [ind, setInd] = useState({ name: '', email: '', role: '', password: '' });
  const [ent, setEnt] = useState({ company: '', name: '', email: '', role: 'admin', password: '' });
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  const doRegister = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const payload = type === 'enterprise' ? {
        type: 'enterprise',
        name: ent.name,
        email: ent.email,
        password: ent.password,
        company: ent.company,
        role: ent.role
      } : {
        type: 'individual',
        name: ind.name,
        email: ind.email,
        password: ind.password,
        company: '',
        role: ind.role
      };

      const res = await fetch(`${BACKEND}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      
      onLaunch({ ...data.user, token: data.access_token });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('An unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const doLogin = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch(`${BACKEND}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      onLaunch({ ...data.user, token: data.access_token });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('An unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const next = () => {
    if (step === 0 && !type) return;
    if (step === 1 && type === 'individual' && !(ind.name && ind.email && ind.role && ind.password)) return;
    if (step === 1 && type === 'enterprise' && !(ent.company && ent.name && ent.email && ent.password)) return;
    
    if (step === 1) {
      doRegister();
      return;
    }
    setStep(step + 1);
  };

  const back = () => {
    if (step > 0) setStep(step - 1);
    else setMode('intro');
  };

  const renderDots = () => {
    if (mode === 'login' || mode === 'intro') return null;
    const total = 2;
    return (
      <div className="dots" style={{ marginBottom: 20 }}>
        {Array.from({ length: total }).map((_, i) => (
          <div key={i} className={`dot-step ${i < step ? 'done' : i === step ? 'active' : ''}`}></div>
        ))}
      </div>
    );
  };

  return (
    <div className={`nx-root ${theme}`}>
      <div className="nx-bg"></div>

      <div className="nx-wrap">
        <button className="theme-toggle" onClick={toggleTheme}>
          <div className="theme-toggle-track"><div className="theme-toggle-thumb"></div></div>
          <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{theme}</span>
        </button>

        <div className="logo-area">
          <div className="logo-row">
            <span className="logo-bracket">[</span>
            <span className="logo-text">NEXUS<span>-X</span></span>
            <span className="logo-bracket">]</span>
          </div>
          <div className="logo-tagline">developer intelligence platform <em>v1.0</em></div>
        </div>

        {renderDots()}

        <div style={{ width: '100%', maxWidth: '480px' }}>
          <div className="card">
            
            {mode === 'intro' && (
              <>
                <div className="prompt-line"><span className="ps">nexus@system:~$</span> <span className="cmd">auth --init</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Welcome to <em>NEXUS-X</em></div>
                <div className="card-sub">// Identify yourself to access the platform</div>
                
                <div style={{ height: '20px' }}></div>
                
                <button className="btn-primary" onClick={() => { setMode('login'); setErrorMsg(''); }}>
                  Login to existing Workspace
                </button>
                <div style={{ textAlign: 'center', margin: '15px 0', color: 'var(--text3)' }}>— or —</div>
                <button className="btn-secondary" onClick={() => { setMode('register'); setStep(0); setErrorMsg(''); }}>
                  Create new Workspace
                </button>
              </>
            )}

            {mode === 'login' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@auth:~$</span> <span className="cmd">login</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Authenticate</div>
                <div className="card-sub">// Enter your credentials</div>
                
                {errorMsg && <div className="error-banner">{errorMsg}</div>}

                <div className="field-group mt-4">
                  <div className="field-label"><span className="req">→</span> EMAIL</div>
                  <input type="email" className="field-input" placeholder="you@domain.com" value={loginForm.email} onChange={e => setLoginForm({...loginForm, email: e.target.value})} />
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> PASSWORD</div>
                  <input type="password" className="field-input" placeholder="••••••••" value={loginForm.password} onChange={e => setLoginForm({...loginForm, password: e.target.value})} />
                </div>
                
                <button className="btn-primary mt-4" onClick={doLogin} disabled={!loginForm.email || !loginForm.password || loading}>
                  {loading ? 'Authenticating...' : 'Login'}
                </button>
              </>
            )}

            {mode === 'register' && step === 0 && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@init:~$</span> <span className="cmd">select --workspace-type</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Who's <em>building</em>?</div>
                <div className="card-sub">// choose your environment type to continue</div>
                
                <div className="type-grid">
                  <button className={`type-btn t-ind ${type === 'individual' ? 'sel' : ''}`} onClick={() => setType('individual')}>
                    <div className="sel-dot">✓</div>
                    <div className="type-icon-wrap"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg></div>
                    <div className="type-name">Individual</div>
                    <div className="type-hint">Solo dev.<br />Personal repos.</div>
                  </button>
                  <button className={`type-btn t-ent ${type === 'enterprise' ? 'sel' : ''}`} onClick={() => setType('enterprise')}>
                    <div className="sel-dot">✓</div>
                    <div className="type-icon-wrap"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="2" strokeLinecap="round"><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" /></svg></div>
                    <div className="type-name">Enterprise</div>
                    <div className="type-hint">Team workspace.<br />Nested projects.</div>
                  </button>
                </div>
                <div style={{ height: '20px' }}></div>
                <button className="btn-primary" onClick={next} disabled={!type}>
                  continue
                </button>
              </>
            )}

            {mode === 'register' && step === 1 && type === 'individual' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@setup:~$</span> <span className="cmd">config --user</span></div>
                <div className="card-title">Your <em>profile</em></div>
                <div className="card-sub">// identity used across sessions</div>
                
                {errorMsg && <div className="error-banner">{errorMsg}</div>}

                <div className="field-group mt-3">
                  <div className="field-label"><span className="req">→</span> FULL_NAME</div>
                  <input className="field-input" placeholder="e.g. Arjun Mehta" value={ind.name} onChange={e => setInd({...ind, name: e.target.value})} />
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> EMAIL</div>
                  <input type="email" className="field-input" placeholder="you@domain.com" value={ind.email} onChange={e => setInd({...ind, email: e.target.value})} />
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> ROLE</div>
                  <select className="field-select" value={ind.role} onChange={e => setInd({...ind, role: e.target.value})}>
                    <option value="">-- select role --</option>
                    {['full-stack engineer', 'backend engineer', 'frontend engineer', 'devops / SRE', 'security engineer', 'indie hacker'].map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> PASSWORD</div>
                  <input type="password" className="field-input" placeholder="••••••••" value={ind.password} onChange={e => setInd({...ind, password: e.target.value})} />
                </div>
                
                <button className="btn-primary" onClick={next} disabled={!(ind.name && ind.email && ind.role && ind.password) || loading}>
                  {loading ? 'Registering...' : 'finalize setup'}
                </button>
              </>
            )}

            {mode === 'register' && step === 1 && type === 'enterprise' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@setup:~$</span> <span className="cmd">config --org</span></div>
                <div className="card-title">Enterprise <em>setup</em></div>
                <div className="card-sub">// configure company domain and identity</div>
                
                {errorMsg && <div className="error-banner">{errorMsg}</div>}

                <div className="field-group mt-3">
                  <div className="field-label"><span className="req">→</span> COMPANY_NAME</div>
                  <input className="field-input" placeholder="e.g. Acme Corp" value={ent.company} onChange={e => setEnt({...ent, company: e.target.value})} />
                </div>
                <div className="two-col">
                  <div className="field-group">
                    <div className="field-label"><span className="req">→</span> YOUR_NAME</div>
                    <input className="field-input" placeholder="Priya K." value={ent.name} onChange={e => setEnt({...ent, name: e.target.value})} />
                  </div>
                  <div className="field-group">
                    <div className="field-label"><span className="req">→</span> YOUR_EMAIL</div>
                    <input type="email" className="field-input" placeholder="priya@acme.com" value={ent.email} onChange={e => setEnt({...ent, email: e.target.value})} />
                  </div>
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> PASSWORD</div>
                  <input type="password" className="field-input" placeholder="••••••••" value={ent.password} onChange={e => setEnt({...ent, password: e.target.value})} />
                </div>
                
                <button className="btn-primary" onClick={next} disabled={!(ent.company && ent.name && ent.email && ent.password) || loading}>
                  {loading ? 'Deploying...' : 'deploy workspace'}
                </button>
              </>
            )}
            
          </div>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
