import { useState } from 'react';
import './Dashboard.css';
import type { UserSession } from '../../App';

interface Member {
  name: string;
  email: string;
  role: string;
}

interface Project {
  id: string;
  name: string;
  description: string;
  cloneCode: string;
  members: Member[];
}

interface DashboardProps {
  session: UserSession;
  onLogout: () => void;
}

const Dashboard = ({ session, onLogout }: DashboardProps) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  
  // Create Project State
  const [showNewProj, setShowNewProj] = useState(false);
  const [newProj, setNewProj] = useState({ name: '', description: '' });

  // Add Member State
  const [newMem, setNewMem] = useState({ name: '', email: '', role: 'developer' });

  const isEnterprise = session.type === 'enterprise';
  const orgName = isEnterprise ? session.company : `${session.name}'s Workspace`;

  const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const genHex = () => Math.random().toString(16).slice(2, 8);

  const handleCreateProject = () => {
    if (!newProj.name.trim()) return;
    const slug = `${slugify(orgName)}/${slugify(newProj.name)}-${genHex()}`;
    const project: Project = {
      id: Date.now().toString(),
      name: newProj.name,
      description: newProj.description,
      cloneCode: slug,
      members: []
    };
    setProjects([...projects, project]);
    setNewProj({ name: '', description: '' });
    setShowNewProj(false);
  };

  const handleAddMember = (projectId: string) => {
    if (!newMem.name.trim() || !newMem.email.trim()) return;
    setProjects(projects.map(p => {
      if (p.id === projectId) {
        return { ...p, members: [...p.members, { ...newMem }] };
      }
      return p;
    }));
    setNewMem({ name: '', email: '', role: 'developer' });
  };

  const removeMember = (projectId: string, memberIndex: number) => {
    setProjects(projects.map(p => {
      if (p.id === projectId) {
        const updatedMembers = [...p.members];
        updatedMembers.splice(memberIndex, 1);
        return { ...p, members: updatedMembers };
      }
      return p;
    }));
  };

  return (
    <div className="dash-root">
      {/* Top Navbar */}
      <nav className="dash-nav">
        <div className="nav-left">
          <div className="dash-logo">NEXUS<span>-X</span></div>
          <div className="nav-divider">/</div>
          <div className="org-name">{orgName}</div>
        </div>
        <div className="nav-right">
          <div className="user-badge">
            <span className="u-dot"></span>
            {session.name} <span className="u-role">({session.role})</span>
          </div>
          <button className="btn-logout" onClick={onLogout}>logout</button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="dash-main">
        <div className="dash-sidebar">
          <div className="sidebar-header">
            <h3>Projects</h3>
            <button className="btn-icon" onClick={() => setShowNewProj(!showNewProj)}>+</button>
          </div>
          <div className="sidebar-list">
            {projects.length === 0 ? (
              <div className="empty-state-small">No projects yet.</div>
            ) : (
              projects.map(p => (
                <button 
                  key={p.id} 
                  className={`proj-link ${activeProject === p.id ? 'active' : ''}`}
                  onClick={() => setActiveProject(p.id)}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                  {p.name}
                </button>
              ))
            )}
          </div>
        </div>

        <div className="dash-content">
          {showNewProj ? (
            <div className="proj-form-card">
              <h2>Deploy New Project</h2>
              <p>Initialize a new project environment under <strong>{orgName}</strong>.</p>
              
              <div className="form-group mt-4">
                <label>PROJECT_NAME</label>
                <input 
                  type="text" 
                  className="dash-input" 
                  placeholder="e.g. Core API Service" 
                  value={newProj.name} 
                  onChange={e => setNewProj({...newProj, name: e.target.value})} 
                />
              </div>
              <div className="form-group mt-3">
                <label>DESCRIPTION_TAG</label>
                <input 
                  type="text" 
                  className="dash-input" 
                  placeholder="e.g. backend graph processing" 
                  value={newProj.description} 
                  onChange={e => setNewProj({...newProj, description: e.target.value})} 
                />
              </div>
              <div className="form-actions mt-4">
                <button className="btn-dash-primary" onClick={handleCreateProject} disabled={!newProj.name}>deploy project</button>
                <button className="btn-dash-secondary" onClick={() => setShowNewProj(false)}>cancel</button>
              </div>
            </div>
          ) : activeProject ? (
            (() => {
              const p = projects.find(x => x.id === activeProject)!;
              return (
                <div className="project-view">
                  <div className="proj-header">
                    <h2>{p.name}</h2>
                    <p>{p.description || '// no description provided'}</p>
                  </div>

                  <div className="setup-documentation-wrapper">
                    <div className="setup-header">
                      <h3>📚 Quick Setup Guide</h3>
                      <p>To integrate your local repository with this NEXUS-X workspace and unlock structural code intelligence, follow the steps below.</p>
                    </div>
                    
                    <div className="doc-grid">
                      <div className="doc-card">
                        <div className="doc-step-badge">1</div>
                        <h4>Install Global CLI</h4>
                        <p>NEXUS-X uses a seamless local CLI agent to parse your graph.</p>
                        <div className="terminal-block">
                          <div className="term-line"><span className="term-prompt">$</span> npm i -g nexus-x-cli</div>
                        </div>
                      </div>

                      <div className="doc-card">
                        <div className="doc-step-badge">2</div>
                        <h4>Initialize Workspace</h4>
                        <p>Run these inside your codebase to bootstrap the platform.</p>
                        <div className="terminal-block">
                          <div className="term-line"><span className="term-prompt">$</span> nexus init</div>
                        </div>
                      </div>

                      <div className="doc-card full-span">
                        <div className="doc-step-badge">3</div>
                        <h4>Connect Origin & Push Knowledge Graph</h4>
                        <p>Link your local setup directly to this remote workspace identity and sync the data.</p>
                        <div className="terminal-block">
                          <div className="term-line term-line-interactive">
                            <span><span className="term-prompt">$</span> nexus remote {p.cloneCode}</span>
                            <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText(`nexus remote ${p.cloneCode}`)} title="Copy remote command">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            </button>
                          </div>
                          <div className="term-line"><span className="term-prompt">$</span> nexus push</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="proj-members-section">
                    <div className="section-title">
                      <h3>Team Members</h3>
                      <span className="badge">{p.members.length}</span>
                    </div>

                    <div className="add-member-widget">
                      <div className="widget-label">&rarr; ATTACH_MEMBER</div>
                      <div className="widget-row">
                        <input className="dash-input w-name" placeholder="Full name" value={newMem.name} onChange={e => setNewMem({...newMem, name: e.target.value})} />
                        <input className="dash-input w-email" placeholder="Email contact" value={newMem.email} onChange={e => setNewMem({...newMem, email: e.target.value})} />
                        <select className="dash-select w-role" value={newMem.role} onChange={e => setNewMem({...newMem, role: e.target.value})}>
                          <option value="developer">developer</option>
                          <option value="admin">admin</option>
                          <option value="viewer">viewer</option>
                        </select>
                        <button className="btn-dash-primary w-btn" onClick={() => handleAddMember(p.id)} disabled={!newMem.name || !newMem.email}>attach</button>
                      </div>
                    </div>

                    <div className="members-grid">
                      {p.members.length === 0 ? (
                        <div className="empty-state">No members attached to this project.</div>
                      ) : (
                        p.members.map((m, idx) => (
                          <div className="member-card" key={idx}>
                            <div className="m-av">{m.name.charAt(0).toUpperCase()}</div>
                            <div className="m-details">
                              <div className="m-n">{m.name}</div>
                              <div className="m-e">{m.email}</div>
                            </div>
                            <div className={`m-badge r-${m.role}`}>{m.role}</div>
                            <button className="m-del" onClick={() => removeMember(p.id, idx)}>✕</button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="empty-dashboard">
              <span className="empty-icon">⌘</span>
              <h2>{orgName} Workspace</h2>
              <p>Select a project from the sidebar to view its resources, or initialize a new project to get started.</p>
              <button className="btn-dash-primary mt-4" onClick={() => setShowNewProj(true)}>initialize project</button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
