import { useState, useEffect, useCallback } from 'react';
import './Dashboard.css';
import type { UserSession } from '../../App';
import FileTree, { type TreeData, type FileNode } from '../../components/FileTree/FileTree';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

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

const getLanguage = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx': return 'javascript';
    case 'ts':
    case 'tsx': return 'typescript';
    case 'py': return 'python';
    case 'css': return 'css';
    case 'html': return 'markup';
    case 'json': return 'json';
    case 'md': return 'markdown';
    case 'yml':
    case 'yaml': return 'yaml';
    case 'sh': return 'bash';
    case 'go': return 'go';
    case 'rs': return 'rust';
    default: return 'text';
  }
};

const Dashboard = ({ session, onLogout }: DashboardProps) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);

  // Create Project State
  const [showNewProj, setShowNewProj] = useState(false);
  const [newProj, setNewProj] = useState({ name: '', description: '' });

  // Add Member State
  const [newMem, setNewMem] = useState({ name: '', email: '', role: 'developer' });

  // File tree state
  const [treeData, setTreeData] = useState<TreeData | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [noPush, setNoPush] = useState(false);

  // File Viewer state
  const [viewingFile, setViewingFile] = useState<{ node: FileNode, content: string | null, loading: boolean } | null>(null);

  const isEnterprise = session.type === 'enterprise';
  const orgName = isEnterprise ? session.company : `${session.name}'s Workspace`;

  // Fetch file tree when project is selected
  const fetchTree = useCallback(async (cloneCode: string) => {
    setTreeLoading(true);
    setTreeData(null);
    setNoPush(false);
    const [workspace, project] = cloneCode.split('/');
    try {
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/tree`);
      const json = await res.json();
      if (json.status === 'no_push' || !json.tree) {
        setNoPush(true);
      } else {
        setTreeData(json as TreeData);
      }
    } catch {
      setNoPush(true);
    } finally {
      setTreeLoading(false);
    }
  }, []);

  const handleFileClick = useCallback(async (node: FileNode) => {
    setViewingFile({ node, content: null, loading: true });
    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/blob/${node.hash}/content`);
      if (res.ok) {
        const text = await res.text();
        setViewingFile({ node, content: text, loading: false });
      } else {
        setViewingFile({ node, content: "// Failed to fetch file content", loading: false });
      }
    } catch {
      setViewingFile({ node, content: "// Failed to fetch file content", loading: false });
    }
  }, [activeProject, projects]);

  // Fetch projects initially
  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/workspaces/${session.workspace}/projects`, {
        headers: { 'Authorization': `Bearer ${session.token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
      }
    } catch (e) {
      console.error("Failed to load projects", e);
    }
  }, [session.workspace, session.token]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // When active project changes, load tree
  useEffect(() => {
    if (!activeProject) return;
    const p = projects.find(x => x.id === activeProject);
    if (p) fetchTree(p.cloneCode);
  }, [activeProject, projects, fetchTree]);

  const handleCreateProject = async () => {
    if (!newProj.name.trim()) return;
    try {
      const res = await fetch(`${BACKEND}/api/workspaces/${session.workspace}/projects`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.token}` 
        },
        body: JSON.stringify({ name: newProj.name, description: newProj.description })
      });
      if (res.ok) {
        const createdProject = await res.json();
        setProjects([createdProject, ...projects]);
        setNewProj({ name: '', description: '' });
        setShowNewProj(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddMember = async (projectId: string) => {
    if (!newMem.name.trim() || !newMem.email.trim()) return;
    try {
      const res = await fetch(`${BACKEND}/api/workspaces/${session.workspace}/projects/${projectId}/members`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.token}` 
        },
        body: JSON.stringify(newMem)
      });
      if (res.ok) {
        setProjects(projects.map(p => {
          if (p.id === projectId) return { ...p, members: [...p.members, { ...newMem }] };
          return p;
        }));
        setNewMem({ name: '', email: '', role: 'developer' });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const removeMember = async (projectId: string, memberEmail: string) => {
    try {
      const res = await fetch(`${BACKEND}/api/workspaces/${session.workspace}/projects/${projectId}/members/${memberEmail}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${session.token}` }
      });
      if (res.ok) {
        setProjects(projects.map(p => {
          if (p.id === projectId) {
            return { ...p, members: p.members.filter(m => m.email !== memberEmail) };
          }
          return p;
        }));
      }
    } catch (e) {
      console.error(e);
    }
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
                <input type="text" className="dash-input" placeholder="e.g. Core API Service"
                  value={newProj.name} onChange={e => setNewProj({...newProj, name: e.target.value})} />
              </div>
              <div className="form-group mt-3">
                <label>DESCRIPTION_TAG</label>
                <input type="text" className="dash-input" placeholder="e.g. backend graph processing"
                  value={newProj.description} onChange={e => setNewProj({...newProj, description: e.target.value})} />
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

                  {/* ── File Tree from DB ── */}
                  <FileTree
                    data={treeData}
                    loading={treeLoading}
                    noPush={noPush}
                    onFileClick={handleFileClick}
                  />

                  {/* ── Setup Guide ── */}
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
                        <h4>Connect Origin &amp; Push</h4>
                        <p>Link your local setup to this remote and sync the file graph.</p>
                        <div className="terminal-block">
                          <div className="term-line term-line-interactive">
                            <span><span className="term-prompt">$</span> nexus remote {p.cloneCode}</span>
                            <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText(`nexus remote ${p.cloneCode}`)} title="Copy">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            </button>
                          </div>
                          <div className="term-line"><span className="term-prompt">$</span> nexus push</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* ── Team Members ── */}
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
                            <button className="m-del" onClick={() => removeMember(p.id, m.email)}>✕</button>
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

      {/* ── File Viewer Modal ── */}
      {viewingFile && (
        <div className="file-viewer-modal">
          <div className="fvm-content">
            <div className="fvm-header">
              <span className="fvm-title">{viewingFile.node.name}</span>
              <button className="fvm-close" onClick={() => setViewingFile(null)}>✕</button>
            </div>
            <div className="fvm-body">
              {viewingFile.loading ? (
                <div className="fvm-loading">Loading content...</div>
              ) : (
                <SyntaxHighlighter
                  language={getLanguage(viewingFile.node.name)}
                  style={vscDarkPlus}
                  customStyle={{ margin: 0, padding: 0, background: 'transparent', fontSize: '13px' }}
                  showLineNumbers={true}
                  wrapLines={true}
                  lineProps={{ style: { display: 'block' } }}
                >
                  {viewingFile.content || ''}
                </SyntaxHighlighter>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
