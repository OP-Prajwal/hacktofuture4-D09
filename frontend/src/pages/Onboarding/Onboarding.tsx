import { useState } from 'react';
import './Onboarding.css';

interface OnboardingProps {
  onLaunch: (data: any) => void;
}

const Onboarding = ({ onLaunch }: OnboardingProps) => {
  const [theme, setTheme] = useState('dark');
  const [step, setStep] = useState(0);
  const [type, setType] = useState<string | null>(null);
  
  // Data stores
  const [ind, setInd] = useState({ name: '', email: '', role: '' });
  const [ent, setEnt] = useState({ company: '', name: '', email: '', phone: '' });

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  const next = () => {
    if (step === 0 && !type) return;
    if (step === 1 && type === 'individual' && !(ind.name && ind.email && ind.role)) return;
    if (step === 1 && type === 'enterprise' && !(ent.company && ent.name && ent.email && ent.phone)) return;
    // Enterprise: skip success screen, go straight to dashboard
    if (step === 1 && type === 'enterprise') {
      onLaunch({ type: 'enterprise', name: ent.name, email: ent.email, phone: ent.phone, company: ent.company, role: 'admin' });
      return;
    }
    setStep(step + 1);
  };

  const back = () => {
    if (step > 0) setStep(step - 1);
  };

  const restart = () => {
    setStep(0); setType(null);
    setInd({ name: '', email: '', role: '' });
    setEnt({ company: '', name: '', email: '', phone: '' });
  };

  const handleLaunchClick = () => {
    if (type === 'enterprise') {
      onLaunch({ type, name: ent.name, email: ent.email, company: ent.company, role: 'admin' });
    } else {
      onLaunch({ type, name: ind.name, email: ind.email, company: '', role: ind.role });
    }
  };

  const renderDots = () => {
    const total = 3; // (Type -> Details -> Success)
    return (
      <div className="dots">
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
            {step === 0 && (
              <>
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
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  continue
                </button>
              </>
            )}

            {step === 1 && type === 'individual' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@setup:~$</span> <span className="cmd">config --user</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Your <em>profile</em></div>
                <div className="card-sub">// identity used across sessions & reports</div>
                
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> FULL_NAME</div>
                  <input className="field-input" placeholder="e.g. Arjun Mehta" value={ind.name} onChange={e => setInd({...ind, name: e.target.value})} />
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> EMAIL</div>
                  <input className="field-input" placeholder="you@domain.com" value={ind.email} onChange={e => setInd({...ind, email: e.target.value})} />
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
                
                <button className="btn-primary" onClick={next} disabled={!(ind.name && ind.email && ind.role)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  finalize setup
                </button>
              </>
            )}

            {step === 1 && type === 'enterprise' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@setup:~$</span> <span className="cmd">config --org</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Enterprise <em>setup</em></div>
                <div className="card-sub">// configure company domain and identity</div>
                
                <div className="field-group">
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
                    <input className="field-input" placeholder="priya@acme.com" value={ent.email} onChange={e => setEnt({...ent, email: e.target.value})} />
                  </div>
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> PHONE_NUMBER</div>
                  <input className="field-input" placeholder="+91 98765 43210" value={ent.phone} onChange={e => setEnt({...ent, phone: e.target.value})} />
                </div>
                
                <button className="btn-primary" onClick={next} disabled={!(ent.company && ent.name && ent.email && ent.phone)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  launch dashboard
                </button>
              </>
            )}

            {step === 2 && (
              <div className="success-box">
                <span className="s-glyph">▶_</span>
                <div className="s-title">system <em>online</em>.</div>
                <div className="s-sub">// initializing nexus-x runtime...<br />// all systems nominal. ready to launch.</div>
                <div className="module-tags" style={{marginBottom: 32}}>
                  {['graph-engine', 'ai-scoring', type === 'enterprise' ? 'company-dashboard' : 'solo-dashboard', 'project-tree'].map(m => (
                    <span key={m} className="mod-tag on">{m}</span>
                  ))}
                </div>
                <button className="btn-primary" onClick={handleLaunchClick} style={{marginBottom: '10px'}}>
                  launch nexus dashboard
                </button>
                <button className="btn-secondary" onClick={restart}>← restart.sh</button>
              </div>
            )}
            
          </div>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
