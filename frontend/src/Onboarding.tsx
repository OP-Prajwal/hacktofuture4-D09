import { useState } from 'react';
import './Onboarding.css';

const Onboarding = () => {
  const [theme, setTheme] = useState('dark');
  const [step, setStep] = useState(0);
  const [type, setType] = useState<string | null>(null);
  const [ind, setInd] = useState({ name: '', phone: '', role: '' });
  const [ent, setEnt] = useState({ name: '', job: '', ws: '', members: [] as any[] });
  const [nm, setNm] = useState({ name: '', email: '', role: 'developer' });

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  const ini = (n: string) => (n || '??').split(' ').map(w => w[0] || '').join('').toUpperCase().slice(0, 2);
  const rClass = (r: string) => {
    if (r === 'admin') return 'r-admin';
    if (r === 'viewer') return 'r-viewer';
    if (r === 'devops') return 'r-devops';
    if (r === 'security') return 'r-security';
    return 'r-dev';
  };

  const addMember = () => {
    if (!nm.name.trim() || !nm.email.trim()) return;
    setEnt({ ...ent, members: [...ent.members, { ...nm }] });
    setNm({ name: '', email: '', role: 'developer' });
  };

  const rmMember = (i: number) => {
    const newMembers = [...ent.members];
    newMembers.splice(i, 1);
    setEnt({ ...ent, members: newMembers });
  };

  const next = () => {
    if (step === 0 && !type) return;
    if (step === 1 && type === 'individual' && !(ind.name && ind.phone && ind.role)) return;
    if (step === 1 && type === 'enterprise' && !(ent.name && ent.job && ent.ws)) return;
    if (step === 1 && type === 'individual') { setStep(2); }
    else { setStep(step + 1); }
  };

  const back = () => {
    if (step === 2 && type === 'enterprise') setStep(1);
    else if (step === 2) setStep(0);
    else setStep(step - 1);
  };

  const restart = () => {
    setStep(0); setType(null);
    setInd({ name: '', phone: '', role: '' });
    setEnt({ name: '', job: '', ws: '', members: [] });
    setNm({ name: '', email: '', role: 'developer' });
  };

  const renderDots = () => {
    const total = step === 0 ? 3 : (type === 'enterprise' ? 3 : 2);
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
                    <div className="type-hint">Team workspace.<br />Multi-member.</div>
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
                  <div className="field-label"><span className="req">→</span> PHONE_NUMBER</div>
                  <input className="field-input" placeholder="+91 98765 43210" value={ind.phone} onChange={e => setInd({...ind, phone: e.target.value})} />
                </div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> ROLE</div>
                  <select className="field-select" value={ind.role} onChange={e => setInd({...ind, role: e.target.value})}>
                    <option value="">-- select role --</option>
                    {['full-stack engineer', 'backend engineer', 'frontend engineer', 'devops / SRE', 'security engineer', 'software architect', 'indie hacker'].map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <button className="btn-primary" onClick={next} disabled={!(ind.name && ind.phone && ind.role)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  launch nexus-x
                </button>
              </>
            )}

            {step === 1 && type === 'enterprise' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@setup:~$</span> <span className="cmd">config --workspace</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Workspace <em>config</em></div>
                <div className="card-sub">// configure your org before adding members</div>
                <div className="field-group">
                  <div className="field-label"><span className="req">→</span> ADMIN_NAME</div>
                  <input className="field-input" placeholder="e.g. Priya Kapoor" value={ent.name} onChange={e => setEnt({...ent, name: e.target.value})} />
                </div>
                <div className="two-col">
                  <div className="field-group">
                    <div className="field-label"><span className="req">→</span> JOB_ROLE</div>
                    <select className="field-select" value={ent.job} onChange={e => setEnt({...ent, job: e.target.value})}>
                      <option value="">-- select --</option>
                      {['CTO', 'VP Engineering', 'Engineering Manager', 'Tech Lead', 'Staff Engineer', 'Principal Engineer'].map(r => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field-group">
                    <div className="field-label"><span className="req">→</span> WORKSPACE</div>
                    <input className="field-input" placeholder="e.g. Acme Corp" value={ent.ws} onChange={e => setEnt({...ent, ws: e.target.value})} />
                  </div>
                </div>
                <button className="btn-primary" onClick={next} disabled={!(ent.name && ent.job && ent.ws)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  add team members
                </button>
              </>
            )}

            {step === 2 && type === 'enterprise' && (
              <>
                <button className="back-btn" onClick={back}>← cd ..</button>
                <div className="prompt-line"><span className="ps">nexus@{ent.ws || 'workspace'}:~$</span> <span className="cmd">team --add-members</span><span className="terminal-cursor"></span></div>
                <div className="card-title">Team <em>members</em></div>
                <div className="card-sub">// {ent.members.length} member{ent.members.length !== 1 ? 's' : ''} added · workspace: {ent.ws}</div>
                {ent.members.map((m, i) => (
                  <div className="member-item" key={i}>
                    <div className="m-avatar">{ini(m.name)}</div>
                    <div className="m-info">
                      <div className="m-name">{m.name}</div>
                      <div className="m-email">{m.email}</div>
                    </div>
                    <span className={`m-role ${rClass(m.role)}`}>{m.role}</span>
                    <button className="m-rm" onClick={() => rmMember(i)}>✕</button>
                  </div>
                ))}
                <div className="add-zone">
                  <div className="add-zone-label">// ADD_MEMBER</div>
                  <div className="field-group" style={{ marginBottom: '10px' }}>
                    <input className="field-input" placeholder="Full name" value={nm.name} onChange={e => setNm({...nm, name: e.target.value})} />
                  </div>
                  <div className="two-col" style={{ marginBottom: '10px' }}>
                    <input className="field-input" placeholder="Email address" value={nm.email} onChange={e => setNm({...nm, email: e.target.value})} />
                    <select className="field-select" value={nm.role} onChange={e => setNm({...nm, role: e.target.value})}>
                      {['developer', 'admin', 'viewer', 'devops', 'security'].map(r => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </div>
                  <button className="btn-add" onClick={addMember}>+ add member</button>
                </div>
                <button className="btn-primary" onClick={next}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  {ent.members.length > 0 ? `launch workspace (${ent.members.length})` : ' skip & launch'}
                </button>
              </>
            )}

            {step === 2 && type === 'individual' && (
              <SuccessBox name={ind.name} isEnt={false} restart={restart} />
            )}

            {step === 3 && type === 'enterprise' && (
              <SuccessBox name={ent.name} isEnt={true} memberCount={ent.members.length} restart={restart} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const SuccessBox = ({ name, isEnt, restart, memberCount = 0 }: any) => {
  const firstName = name.split(' ')[0] || 'developer';
  const mods = ['graph-engine', 'ai-scoring', 'sentry-link', 'lang-agents', isEnt ? 'team-sync' : 'solo-mode', 'mcp-tools'];

  return (
    <div className="success-box">
      <span className="s-glyph">▶_</span>
      <div className="s-title">system <em>online</em>, {firstName}.</div>
      <div className="s-sub">// initializing nexus-x runtime...<br />// all systems nominal. welcome.</div>
      <div className="module-tags">
        {mods.map(m => <span key={m} className="mod-tag on">{m}</span>)}
      </div>
      {isEnt && memberCount > 0 ? (
        <div style={{ fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text2)', marginBottom: '16px' }}>
          ✓ invites queued for {memberCount} member{memberCount > 1 ? 's' : ''}
        </div>
      ) : ''}
      <button className="btn-secondary" onClick={restart}>← restart.sh</button>
    </div>
  );
};

export default Onboarding;
