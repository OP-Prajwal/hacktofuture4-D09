import { useState, useEffect, useCallback } from 'react';
import './Dashboard.css';
import type { UserSession } from '../../App';
import FileTree, { type TreeData, type FileNode } from '../../components/FileTree/FileTree';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CIGraph from '../../components/CIGraph/CIGraph';

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

  // Intelligence state
  const [analyzing, setAnalyzing] = useState(false);
  const [queryText, setQueryText] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] } | null>(null);
  const [fullScreenGraph, setFullScreenGraph] = useState(false);

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

  const fetchGraph = useCallback(async (cloneCode: string) => {
    const [workspace, project] = cloneCode.split('/');
    try {
      const graphRes = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/graph`);
      if (graphRes.ok) {
        const gData = await graphRes.json();
        if (gData.status === 'ok') {
          setGraphData({ nodes: gData.nodes || [], edges: gData.edges || [] });
        } else {
          setGraphData(null);
        }
      }
    } catch {
      setGraphData(null);
    }
  }, []);

  // When active project changes, load tree and graph
  useEffect(() => {
    if (!activeProject) return;
    const p = projects.find(x => x.id === activeProject);
    if (p) {
      fetchTree(p.cloneCode);
      fetchGraph(p.cloneCode);
    }
  }, [activeProject, projects, fetchTree, fetchGraph]);

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

  const handleAnalyze = async () => {
    const localPath = prompt(
      "Enter the local path to the repository:\n(e.g. C:\\Users\\me\\projects\\my-app)",
      ""
    );
    if (localPath === null) return; // user cancelled

    setAnalyzing(true);
    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ local_path: localPath || null })
      });
      if (res.ok) {
        await fetchGraph(p.cloneCode);
        setFullScreenGraph(true);
      } else {
        const err = await res.json().catch(() => null);
        alert(`Analysis failed: ${err?.detail || 'Unknown error'}`);
      }
    } catch {
      alert("Knowledge Graph analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    setQuerying(true);
    setQueryResult(null);
    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: queryText })
      });
      if (res.ok) {
        const data = await res.json();
        setQueryResult(data);
      } else {
        setQueryResult({ answer: "Query failed: See console for details." });
      }
    } catch {
      setQueryResult({ answer: "Error reaching the intelligence layer." });
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="dash-root">
      {/* Fullscreen Graph Overlay */}
      {fullScreenGraph && graphData && activeProject && (
        <div className="fullscreen-graph-overlay">
          <header className="fg-header">
            <div className="fg-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
              Knowledge Graph: <span>{projects.find(x => x.id === activeProject)?.name}</span>
            </div>
            <button className="btn-fg-close" onClick={() => setFullScreenGraph(false)} style={{background: 'var(--accent2)', color: '#fff', fontWeight: 'bold', border: 'none'}}>← Back to Dashboard</button>
          </header>
          <div className="fg-body">
            <aside className="fg-sidebar">
              <div className="fg-section">
                <h4>Graph Statistics</h4>
                <div className="fg-stats">
                  <div className="fg-stat-card">
                    <div className="fg-stat-val">{graphData.nodes.length}</div>
                    <div className="fg-stat-lbl">Nodes</div>
                  </div>
                  <div className="fg-stat-card">
                    <div className="fg-stat-val">{graphData.edges.length}</div>
                    <div className="fg-stat-lbl">Edges</div>
                  </div>
                </div>
              </div>
              
              <div className="fg-section">
                <h4>Quick Query</h4>
                <div className="fg-query-box">
                  <input 
                    type="text" 
                    className="dash-input" 
                    placeholder="Ask repository..." 
                    value={queryText}
                    onChange={e => setQueryText(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleQuery()}
                  />
                  <button className="btn-fg-ask" onClick={handleQuery} disabled={querying}>
                    {querying ? 'Thinking...' : 'Run Query'}
                  </button>
                </div>
              </div>

              {queryResult && (
                <div className="fg-section">
                  <h4>Query Result</h4>
                  <div className="ic-result" style={{marginTop: 0}}>
                    <div className="ic-answer">
                      <p style={{fontSize: '12px', margin: 0}}>{queryResult.answer}</p>
                    </div>
                  </div>
                </div>
              )}

              <div className="fg-section">
                <h4>Legend</h4>
                <div className="fg-legend">
                  <div className="lg-item"><span className="lg-dot" style={{background: '#39d353'}}></span> Module</div>
                  <div className="lg-item"><span className="lg-dot" style={{background: '#58a6ff'}}></span> File</div>
                  <div className="lg-item"><span className="lg-dot" style={{background: '#f78166'}}></span> Function</div>
                  <div className="lg-item"><span className="lg-dot" style={{background: '#e3b341'}}></span> Class</div>
                  <div className="lg-item"><span className="lg-line" style={{background: 'rgba(88, 166, 255, 0.6)'}}></span> Semantics (Imports/Calls)</div>
                </div>
              </div>

              <div className="fg-section">
                <h4>Functions Discovery</h4>
                <div style={{ maxHeight: '300px', overflowY: 'auto', background: '#0d1117', borderRadius: '6px', padding: '8px', border: '1px solid #21262d' }}>
                  {graphData.nodes.filter((n: any) => n.data.type === 'Function').length === 0 ? (
                    <div style={{ fontSize: '11px', color: '#8b949e', padding: '10px' }}>No functions found.</div>
                  ) : (
                    graphData.nodes
                      .filter((n: any) => n.data.type === 'Function')
                      .sort((a: any, b: any) => b.data.blast_radius - a.data.blast_radius)
                      .map((fn: any) => (
                        <div key={fn.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderBottom: '1px solid #21262d', fontSize: '11px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxWidth: '70%' }}>
                            <span style={{ color: '#e6edf3', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fn.data.label}</span>
                            <span style={{ color: '#8b949e', fontSize: '9px' }}>{fn.data.file}</span>
                          </div>
                          <span style={{ 
                            background: fn.data.status === 'CRITICAL' ? 'rgba(248,81,73,0.1)' : 'rgba(56,139,253,0.1)',
                            color: fn.data.status === 'CRITICAL' ? '#f85149' : '#388bfd',
                            padding: '2px 6px',
                            borderRadius: '10px',
                            fontSize: '9px',
                            fontWeight: 'bold'
                          }}>
                            {fn.data.blast_radius} conn
                          </span>
                        </div>
                      ))
                  )}
                </div>
              </div>
            </aside>
            <main className="fg-main">
              <CIGraph graphData={graphData} />
            </main>
          </div>
        </div>
      )}

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

                  {/* ── Intelligence Center ── */}
                  <div className="intelligence-center">
                    <div className="section-title">
                      <h3>🧠 Intelligence Layer</h3>
                    </div>
                    
                    <div className="ic-card">
                      <div className="ic-header">
                        <div>
                          <h4>Structural Analysis</h4>
                          <p>Analyze your repository to build a comprehensive knowledge graph of functions and dependencies.</p>
                        </div>
                        <button className="btn-dash-primary" onClick={handleAnalyze} disabled={analyzing}>
                          {analyzing ? 'Analyzing...' : 'Create Graph'}
                        </button>
                      </div>

                      <div className="ic-query">
                        <input
                          type="text"
                          className="dash-input"
                          placeholder="Ask a question about the codebase..."
                          value={queryText}
                          onChange={e => setQueryText(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleQuery()}
                        />
                        <button className="btn-dash-secondary ic-ask-btn" onClick={handleQuery} disabled={querying}>
                          {querying ? 'Thinking...' : 'Ask AI'}
                        </button>
                      </div>

                      {queryResult && (
                        <div className="ic-result">
                          <div className="ic-answer">
                            <strong>AI Response</strong>
                            <p>{queryResult.answer}</p>
                          </div>
                          {queryResult.graph_context && (
                            <div className="ic-context">
                              <strong>Context extracted from graph</strong>
                              <div className="ic-pills">
                                {(queryResult.graph_context.nodes || []).map((n: any, i: number) => (
                                  <span key={i} className="ic-pill">{n.name}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── Functions Discovery (Middle Screen) ── */}
                  <div className="functions-discovery-main" style={{marginTop: '30px'}}>
                    <div className="section-title">
                      <h3>🛠️ Discovered Functions</h3>
                      <span className="badge">{graphData?.nodes.filter((n: any) => n.data.type === 'Function').length || 0}</span>
                    </div>
                    
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                      gap: '16px',
                      marginTop: '16px'
                    }}>
                      {graphData?.nodes
                        .filter((n: any) => n.data.type === 'Function')
                        .sort((a: any, b: any) => b.data.blast_radius - a.data.blast_radius)
                        .map((fn: any) => (
                          <div key={fn.id} className="ic-card" style={{padding: '16px', marginBottom: 0, border: '1px solid #30363d'}}>
                            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px'}}>
                              <div style={{maxWidth: '70%'}}>
                                <h4 style={{margin: 0, fontSize: '14px', color: '#e6edf3', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                                  {fn.data.label}
                                </h4>
                                <code style={{fontSize: '10px', color: '#8b949e'}}>{fn.data.file}</code>
                              </div>
                              <span style={{
                                fontSize: '10px',
                                background: fn.data.status === 'CRITICAL' ? 'rgba(248,81,73,0.1)' : 'rgba(56,139,253,0.1)',
                                color: fn.data.status === 'CRITICAL' ? '#f85149' : '#3fb950',
                                border: `1px solid ${fn.data.status === 'CRITICAL' ? '#f85149' : '#3fb950'}44`,
                                padding: '2px 8px',
                                borderRadius: '12px',
                                fontWeight: 'bold'
                              }}>
                                {fn.data.status}
                              </span>
                            </div>
                            
                            <div style={{display: 'flex', gap: '12px', marginTop: '12px'}}>
                              <div style={{flex: 1}}>
                                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#8b949e', marginBottom: '4px'}}>
                                  <span>Security</span>
                                  <span>{fn.data.security_score}%</span>
                                </div>
                                <div style={{height: '3px', background: '#21262d', borderRadius: '2px'}}>
                                  <div style={{height: '100%', background: '#f85149', width: `${fn.data.security_score}%`, borderRadius: '2px'}} />
                                </div>
                              </div>
                              <div style={{flex: 1}}>
                                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#8b949e', marginBottom: '4px'}}>
                                  <span>Connections</span>
                                  <span>{fn.data.blast_radius}</span>
                                </div>
                                <div style={{height: '3px', background: '#21262d', borderRadius: '2px'}}>
                                  <div style={{height: '100%', background: '#388bfd', width: `${Math.min(100, fn.data.blast_radius * 10)}%`, borderRadius: '2px'}} />
                                </div>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                      {(!graphData || graphData.nodes.filter((n: any) => n.data.type === 'Function').length === 0) && (
                        <div className="empty-state" style={{gridColumn: '1/-1'}}>
                          No functions discovered yet. Analyze the repository to build the graph.
                        </div>
                      )}
                    </div>
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
