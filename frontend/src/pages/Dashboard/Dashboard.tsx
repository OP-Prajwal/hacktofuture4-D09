import { useState, useEffect, useCallback, useRef } from 'react';
import './Dashboard.css';
import type { UserSession } from '../../App';
import FileTree, { type TreeData, type FileNode } from '../../components/FileTree/FileTree';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import LiveTerminal from '../../components/LiveTerminal/LiveTerminal';
import CIGraph from '../../components/CIGraph/CIGraph';

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
  contextNodes?: { name: string; type: string }[];
}

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export interface GraphNodeData {
  type: string;
  label: string;
  file: string;
  status: string;
  summary: string;
  tags: string[];
  security_score: number;
  reliability_score: number;
  scalability_score: number;
  blast_radius: number;
  last_commit: string;
}

export interface GraphNode {
  id: string;
  name?: string;
  data: GraphNodeData;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  weight?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface QueryResult {
  answer: string;
  graph_context?: {
    nodes: GraphNode[];
  };
}

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
  const [activeProject, setActiveProject] = useState<string | null>(localStorage.getItem(`activeProject_${session.workspace}`));

  // Create Project State
  const [showNewProj, setShowNewProj] = useState(false);
  const [newProj, setNewProj] = useState({ name: '', description: '' });
  const [createdProject, setCreatedProject] = useState<Project | null>(null);

  // Add Member State
  const [newMem, setNewMem] = useState({ name: '', email: '', role: 'developer' });

  // File tree state
  const [treeData, setTreeData] = useState<TreeData | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [noPush, setNoPush] = useState(false);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [viewingIncident, setViewingIncident] = useState<any>(null);

  // File Viewer state
  const [viewingFile, setViewingFile] = useState<{ node: FileNode, content: string | null, loading: boolean } | null>(null);

  // Intelligence state
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeStep, setAnalyzeStep] = useState("");
  const [queryText, setQueryText] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [fullScreenGraph, setFullScreenGraph] = useState(false);

  // AI Chat state
  const [fgViewMode, setFgViewMode] = useState<'graph' | 'chat' | 'terminal'>('graph');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<'repo' | 'agent' | 'functions' | 'server' | 'team'>('repo');

  // Blast Radius state
  const [blastFiles, setBlastFiles] = useState('');
  const [blastResult, setBlastResult] = useState<Record<string, unknown> | null>(null);
  const [blastLoading, setBlastLoading] = useState(false);

  // Toast notification state
  const [toast, setToast] = useState<string | null>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const isEnterprise = session.type === 'enterprise';
  const orgName = isEnterprise ? session.company : `${session.name}'s Workspace`;

  // Persist active project and reset view states
  useEffect(() => {
    if (activeProject) {
      localStorage.setItem(`activeProject_${session.workspace}`, activeProject);
      setChatMessages([]);
      setFgViewMode('graph');
      setFullScreenGraph(false);
    }
  }, [activeProject, session.workspace]);

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
      if (res.status === 401 || res.status === 403) {
        onLogout();
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        
        // Auto-select if nothing active or stored
        if (!activeProject && data.length > 0) {
          const stored = localStorage.getItem(`activeProject_${session.workspace}`);
          if (stored && data.find((p: Project) => p.id === stored)) {
            setActiveProject(stored);
          } else {
            setActiveProject(data[0].id);
          }
        }
      }
    } catch (e) {
      console.error("Failed to load projects", e);
    }
  }, [session.workspace, session.token, activeProject]);

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
        const data = await res.json();
        setProjects([data, ...projects]);
        setNewProj({ name: '', description: '' });
        setCreatedProject(data);
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
    setAnalyzing(true);
    setAnalyzeProgress(0);
    setAnalyzeStep("Starting analysis...");

    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');

      // 1. Start async analysis — returns instantly with job_id
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ local_path: null, force: true })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        alert(`Analysis failed: ${err?.detail || 'Unknown error'}`);
        setAnalyzing(false);
        return;
      }

      const { job_id } = await res.json();
      if (!job_id) { alert('No job_id returned'); setAnalyzing(false); return; }

      // 2. Poll for progress every 1.5s
      const poll = async () => {
        try {
          const statusRes = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/analyze/status/${job_id}`);
          if (!statusRes.ok) return;
          const status = await statusRes.json();

          setAnalyzeProgress(status.progress || 0);
          setAnalyzeStep(status.step || "");

          if (status.status === 'success') {
            // Done! Fetch the graph
            await fetchGraph(p.cloneCode);
            setFullScreenGraph(true);
            setAnalyzing(false);
            setAnalyzeStep("");
            return;
          } else if (status.status === 'error') {
            alert(`Analysis failed: ${status.message || status.result?.message || 'Unknown error'}`);
            setAnalyzing(false);
            setAnalyzeStep("");
            return;
          }

          // Still running — poll again
          setTimeout(poll, 1500);
        } catch {
          setTimeout(poll, 2000);
        }
      };

      // Start polling after a short delay
      setTimeout(poll, 1000);

    } catch {
      alert("Knowledge Graph analysis failed.");
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

  useEffect(() => {
    let incidentInterval: number;
    
    if (activeProject && session) {
      const p = projects.find(x => x.id === activeProject);
      if (p) {
        const [ws, pn] = p.cloneCode.split('/');
        
        const fetchIncidents = async () => {
          try {
            const res = await fetch(`${BACKEND}/api/repo/${ws}/${pn}/incidents`);
            if (res.ok) {
              const data = await res.json();
              setIncidents(data.incidents || []);
            }
          } catch (e) {
            console.error("Failed to fetch incidents", e);
          }
        };
        
        fetchIncidents();
        incidentInterval = window.setInterval(fetchIncidents, 5000);
      }
    }
    
    return () => {
      if (incidentInterval) window.clearInterval(incidentInterval);
    };
  }, [activeProject, session, projects]);

  const handleBlastRadius = async () => {
    const files = blastFiles.split(',').map(f => f.trim()).filter(Boolean);
    if (files.length === 0) return;
    setBlastLoading(true);
    setBlastResult(null);
    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/blast-radius`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changed_files: files })
      });
      if (res.ok) {
        const data = await res.json();
        setBlastResult(data);
      } else {
        setBlastResult({ error: 'Blast radius query failed' });
      }
    } catch {
      setBlastResult({ error: 'Could not reach the backend' });
    } finally {
      setBlastLoading(false);
    }
  };

  const handleChatSend = async () => {
    const text = chatInput.trim();
    if (!text || chatSending) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date()
    };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatSending(true);

    try {
      const p = projects.find(x => x.id === activeProject);
      if (!p) return;
      const [workspace, project] = p.cloneCode.split('/');
      const res = await fetch(`${BACKEND}/api/repo/${workspace}/${project}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
      });

      let answer = 'Sorry, I could not reach the intelligence layer.';
      let contextNodes: { name: string; type: string }[] = [];

      if (res.ok) {
        const data = await res.json();
        answer = data.answer || 'No response from the AI.';
        contextNodes = (data.graph_context?.nodes || []).map((n: GraphNode) => ({
          name: n.name || n.data?.label || 'Unknown',
          type: n.data?.type || 'Unknown'
        }));
      }

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'ai',
        content: answer,
        timestamp: new Date(),
        contextNodes
      };
      setChatMessages(prev => [...prev, aiMsg]);
    } catch {
      setChatMessages(prev => [...prev, {
        id: `ai-err-${Date.now()}`,
        role: 'ai',
        content: 'Error: Could not connect to the backend. Make sure the server is running.',
        timestamp: new Date()
      }]);
    } finally {
      setChatSending(false);
      chatInputRef.current?.focus();
    }
  };

  // Format AI responses into clean, ChatGPT-style HTML
  const formatAIResponse = (text: string): string => {
    // Escape HTML
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Bold: **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code class="nx-inline-code">$1</code>');

    // Split into lines for block processing
    const lines = html.split('\n');
    const result: string[] = [];
    let inList = false;
    let listType = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // Bullet list: - item or • item or * item
      if (/^[-•\*]\s+/.test(line)) {
        if (!inList || listType !== 'ul') {
          if (inList) result.push(`</${listType}>`);
          result.push('<ul class="nx-ai-list">');
          inList = true;
          listType = 'ul';
        }
        result.push(`<li>${line.replace(/^[-•\*]\s+/, '')}</li>`);
        continue;
      }

      // Numbered list: 1. item or 1) item
      if (/^\d+[.)\s]+/.test(line)) {
        if (!inList || listType !== 'ol') {
          if (inList) result.push(`</${listType}>`);
          result.push('<ol class="nx-ai-list">');
          inList = true;
          listType = 'ol';
        }
        result.push(`<li>${line.replace(/^\d+[.)\s]+/, '')}</li>`);
        continue;
      }

      // Close list if we're in one
      if (inList) {
        result.push(`</${listType}>`);
        inList = false;
        listType = '';
      }

      // Empty line = paragraph break
      if (line === '') {
        continue;
      }

      // Regular paragraph
      result.push(`<p>${line}</p>`);
    }

    if (inList) result.push(`</${listType}>`);

    return result.join('');
  };

  return (
    <div className="dash-root">
      {/* Fullscreen Graph Overlay */}
      {fullScreenGraph && graphData && activeProject && (() => {
        const topFunctions = graphData.nodes
          .filter((n: GraphNode) => n.data.type === 'Function')
          .sort((a: GraphNode, b: GraphNode) => b.data.blast_radius - a.data.blast_radius)
          .slice(0, 10);

        const welcomeMsg = `Repo indexed. I know your ${graphData.nodes.length} nodes and ${graphData.edges.length} edges. Ask me anything — trace a call chain, find all callers of a function, detect dead code, or explain a module.`;

        const smartSuggestions = topFunctions.length > 0 ? [
          `Trace ${topFunctions[0]?.data.label} ↗`,
          `Dead code in ${topFunctions[0]?.data.file?.split('/').pop() || 'main.py'} ↗`,
          `Explain ${topFunctions.find((f: GraphNode) => f.data.type === 'Class')?.data.label || topFunctions[1]?.data.label || 'module'} ↗`,
        ] : ['How many functions are there? ↗', 'Explain the architecture ↗', 'Find dead code ↗'];

        return (
        <div className="fullscreen-graph-overlay">
          <div className="nx-panel">
            {/* ═══ LEFT SIDEBAR ═══ */}
            <aside className="nx-sidebar">
              <div className="nx-brand" onClick={() => setFullScreenGraph(false)} style={{cursor: 'pointer'}}>
                NEXUS<span>-X</span>
              </div>

              {/* Stats */}
              <div className="nx-stats-row">
                <div className="nx-stat-box">
                  <div className="nx-stat-num">{graphData.nodes.length}</div>
                  <div className="nx-stat-label">Nodes</div>
                </div>
                <div className="nx-stat-box">
                  <div className="nx-stat-num">{graphData.edges.length}</div>
                  <div className="nx-stat-label">Edges</div>
                </div>
              </div>

              {/* Top Functions */}
              <div className="nx-fn-title">TOP FUNCTIONS</div>
              <div className="nx-fn-list">
                {topFunctions.length === 0 ? (
                  <div className="nx-fn-empty">No functions discovered yet.</div>
                ) : (
                  topFunctions.map((fn: GraphNode) => (
                    <div key={fn.id} className="nx-fn-item">
                      <div className="nx-fn-info">
                        <span className="nx-fn-name">{fn.data.label}</span>
                        <span className="nx-fn-file">{fn.data.file?.split('/').pop()}</span>
                      </div>
                      <span className="nx-fn-badge">{fn.data.blast_radius}</span>
                    </div>
                  ))
                )}
              </div>

              {/* View Mode Tabs */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <button className={`nx-graph-toggle ${fgViewMode === 'graph' ? 'active' : ''}`} onClick={() => setFgViewMode('graph')} style={fgViewMode === 'graph' ? { borderColor: 'var(--accent2)', color: 'var(--accent2)', background: 'rgba(var(--accent2-rgb), 0.05)' } : {}}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                  </svg>
                  Graph
                </button>
                <button className={`nx-graph-toggle ${fgViewMode === 'chat' ? 'active' : ''}`} onClick={() => setFgViewMode('chat')} style={fgViewMode === 'chat' ? { borderColor: 'var(--accent2)', color: 'var(--accent2)', background: 'rgba(var(--accent2-rgb), 0.05)' } : {}}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                  </svg>
                  AI Agent
                </button>
                <button className={`nx-graph-toggle ${fgViewMode === 'terminal' ? 'active' : ''}`} onClick={() => setFgViewMode('terminal')} style={fgViewMode === 'terminal' ? { borderColor: '#3fb950', color: '#3fb950', background: 'rgba(63,185,80,0.05)' } : {}}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
                  </svg>
                  Terminal
                </button>
              </div>

              {/* Exit Dashboard Button */}
              <button className="nx-exit-btn" onClick={() => setFullScreenGraph(false)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="19" y1="12" x2="5" y2="12"></line>
                  <polyline points="12 19 5 12 12 5"></polyline>
                </svg>
                Exit to Dashboard
              </button>
            </aside>

            {/* ═══ MAIN AREA ═══ */}
            <div className="nx-main">
              {fgViewMode === 'graph' && (
                <>
                  <div className="nx-chat-header">
                    <div>
                      <h2>Knowledge Graph</h2>
                      <p>Visual dependency map of your codebase</p>
                    </div>
                  </div>
                  <div className="nx-graph-area">
                    <CIGraph graphData={graphData} />
                  </div>
                </>
              )}

              {fgViewMode === 'chat' && (
                <>
                  {/* Chat Header */}
                  <div className="nx-chat-header">
                    <div>
                      <h2>Agent</h2>
                      <p>Ask anything about your repo</p>
                    </div>
                  </div>

                  {/* Chat Body */}
                  <div className="nx-chat-body">
                    {chatMessages.length === 0 && (
                      <div className="nx-ai-card">
                        <div className="nx-ai-label">NEXUS</div>
                        <div className="nx-ai-text" dangerouslySetInnerHTML={{ __html: formatAIResponse(welcomeMsg) }} />
                        <div className="nx-suggestion-row">
                          {smartSuggestions.map(s => (
                            <button key={s} className="nx-suggestion-chip" onClick={() => {
                              setChatInput(s.replace(' ↗', ''));
                              chatInputRef.current?.focus();
                            }}>
                              {s}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {chatMessages.map(msg => (
                      msg.role === 'user' ? (
                        <div key={msg.id} className="nx-user-bubble">
                          {msg.content}
                        </div>
                      ) : (
                        <div key={msg.id} className="nx-ai-card">
                          <div className="nx-ai-label">NEXUS</div>
                          <div className="nx-ai-text" dangerouslySetInnerHTML={{ __html: formatAIResponse(msg.content) }} />
                          {msg.contextNodes && msg.contextNodes.length > 0 && (
                            <div className="nx-ai-context">
                              {msg.contextNodes.slice(0, 6).map((n, i) => (
                                <span key={i} className="nx-code-pill">{n.name}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    ))}

                    {chatSending && (
                      <div className="nx-ai-card">
                        <div className="nx-ai-label">NEXUS</div>
                        <div className="chat-typing-indicator">
                          <span></span><span></span><span></span>
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Input Bar */}
                  <div className="nx-chat-input-bar">
                    <input
                      ref={chatInputRef}
                      type="text"
                      className="nx-chat-input"
                      placeholder="Ask about your codebase..."
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleChatSend()}
                      disabled={chatSending}
                    />
                    <button
                      className="nx-send-btn"
                      onClick={handleChatSend}
                      disabled={chatSending || !chatInput.trim()}
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                      </svg>
                    </button>
                  </div>
                </>
              )}

              {fgViewMode === 'terminal' && (() => {
                const p = projects.find(x => x.id === activeProject);
                if (!p) return null;
                const [ws, proj] = p.cloneCode.split('/');
                return (
                  <>
                    <div className="nx-chat-header">
                      <div>
                        <h2>CI/CD Terminal</h2>
                        <p>Live logs from your production runner</p>
                      </div>
                    </div>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <LiveTerminal workspace={ws} project={proj} />
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
        );
      })()}

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
          {createdProject ? (
            <div className="proj-form-card" style={{ maxWidth: '600px' }}>
              <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                <div style={{ width: '48px', height: '48px', background: 'rgba(57, 211, 83, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </div>
                <h2 style={{ margin: 0 }}>Project Deployed!</h2>
                <p style={{ marginTop: '8px' }}>Your environment for <strong>{createdProject.name}</strong> is ready.</p>
              </div>

              <div className="clone-box" style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', textAlign: 'left', padding: '16px' }}>
                <p style={{ fontSize: '13px', color: '#8b949e', marginBottom: '8px', fontWeight: 600 }}>…or connect an existing repository from the command line</p>
                <div className="clone-cmd" style={{ background: '#010409', border: '1px solid #30363d', borderRadius: '6px', display: 'flex', alignItems: 'flex-start' }}>
                  <pre style={{ margin: 0, padding: '16px', fontSize: '12px', color: '#e6edf3', fontFamily: 'monospace', lineHeight: '1.6', overflowX: 'auto', flex: 1 }}>
                    <span style={{color: '#8b949e'}}># Link the local CLI (package not published to npm yet)</span>{'\n'}
                    cd C:\nexus-X\cli && npm link{'\n\n'}
                    <span style={{color: '#8b949e'}}># Initialize and connect the repository</span>{'\n'}
                    nexus connect {BACKEND} {createdProject.cloneCode}{'\n\n'}
                    <span style={{color: '#8b949e'}}># Push codebase to the platform and analyze it</span>{'\n'}
                    nexus push{'\n'}
                    nexus analyze
                  </pre>
                  <button className="clone-copy" style={{ margin: '8px' }} onClick={() => {
                    navigator.clipboard.writeText(`cd C:\\nexus-X\\cli && npm link\nnexus connect ${BACKEND} ${createdProject.cloneCode}\nnexus push\nnexus analyze`);
                  }}>
                    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" fill="currentColor"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                <button className="btn-dash-primary" onClick={() => {
                  setActiveProject(createdProject.id);
                  setCreatedProject(null);
                  setShowNewProj(false);
                }}>
                  Go to Dashboard
                </button>
                <button className="btn-dash-secondary" onClick={() => {
                  setCreatedProject(null);
                  setShowNewProj(false);
                }}>
                  Dismiss
                </button>
              </div>
            </div>
          ) : showNewProj ? (
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
              const p = projects.find(x => x.id === activeProject);
              if (!p) {
                return (
                  <div className="empty-dashboard">
                    <div className="loading-spinner-container">
                      <div className="nexus-spinner"></div>
                      <p>Loading project environment...</p>
                    </div>
                  </div>
                );
              }
              return (
                <div className="project-view">
                  <div className="proj-header">
                    <h2>{p.name}</h2>
                    <p>{p.description || '// no description provided'}</p>
                  </div>

                  {treeLoading ? (
                    <div className="empty-dashboard" style={{ marginTop: '40px' }}>
                      <div className="loading-spinner-container">
                        <div className="nexus-spinner"></div>
                        <p>Scanning repository state...</p>
                      </div>
                    </div>
                  ) : noPush || !treeData ? (
                    <div className="empty-dashboard" style={{ marginTop: '40px', padding: '60px 20px' }}>
                      <div className="clone-box" style={{ background: '#000', border: '1px solid var(--accent2)', maxWidth: '600px', margin: '0 auto', textAlign: 'left' }}>
                        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                          <div style={{ width: '48px', height: '48px', background: 'rgba(88, 166, 255, 0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                             <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                          </div>
                          <h3 style={{ margin: 0, color: 'var(--text)' }}>Waiting for first code push...</h3>
                          <p style={{ marginTop: '8px', color: 'var(--text2)', fontSize: '14px' }}>Connect your local code to this workspace to unlock AI CI/CD and Graph Intelligence.</p>
                        </div>
                        
                        <div className="clone-label" style={{ color: 'var(--accent2)' }}>1. LINK LOCAL CLI</div>
                        <p style={{ fontSize: '12px', color: 'var(--text2)', marginBottom: '8px' }}>The package is not on npm yet. Link the local CLI directory.</p>
                        <div className="clone-cmd" style={{ background: 'rgba(88, 166, 255, 0.05)', borderColor: 'rgba(88, 166, 255, 0.2)', marginBottom: '16px' }}>
                          <code style={{ fontSize: '12px', color: '#a5d6ff' }}>cd C:\nexus-X\cli && npm link</code>
                        </div>

                        <div className="clone-label" style={{ color: 'var(--accent2)' }}>2. CONNECT & INITIALIZE</div>
                        <div className="clone-cmd" style={{ background: 'rgba(88, 166, 255, 0.05)', borderColor: 'rgba(88, 166, 255, 0.2)', marginBottom: '16px' }}>
                          <code style={{ fontSize: '12px', color: '#a5d6ff' }}>
                            nexus connect {BACKEND} {p.cloneCode}
                          </code>
                          <button className="clone-copy" onClick={() => navigator.clipboard.writeText(`nexus connect ${BACKEND} ${p.cloneCode}`)}>COPY</button>
                        </div>

                        <div className="clone-label" style={{ color: 'var(--accent2)' }}>3. PUSH & ANALYZE</div>
                        <div className="clone-cmd" style={{ background: 'rgba(88, 166, 255, 0.05)', borderColor: 'rgba(88, 166, 255, 0.2)' }}>
                          <code style={{ fontSize: '12px', color: '#a5d6ff' }}>
                            nexus push && nexus analyze
                          </code>
                          <button className="clone-copy" onClick={() => navigator.clipboard.writeText(`nexus push && nexus analyze`)}>COPY</button>
                        </div>
                        
                        <div style={{ textAlign: 'center', marginTop: '24px' }}>
                          <button className="btn-dash-primary" onClick={() => fetchTree(p.cloneCode)}>Refresh</button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* ── Metric Cards ── */}
                      <div className="metrics-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '30px' }}>
                        <div className="metric-card" onClick={() => setActiveTab('repo')} style={{ cursor: 'pointer', background: '#0d1117', border: activeTab === 'repo' ? '1px solid #58a6ff' : '1px solid #30363d', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '12px', color: activeTab === 'repo' ? '#58a6ff' : '#8b949e', fontWeight: 600 }}>REPOSITORY</span>
                          <span style={{ fontSize: '20px', color: '#e6edf3', fontWeight: 'bold', marginTop: '8px' }}>Synced</span>
                        </div>
                        <div className="metric-card" onClick={() => setActiveTab('agent')} style={{ cursor: 'pointer', background: '#0d1117', border: activeTab === 'agent' ? '1px solid #58a6ff' : '1px solid #30363d', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '12px', color: activeTab === 'agent' ? '#58a6ff' : '#8b949e', fontWeight: 600 }}>AUTO-HEALER AGENT</span>
                          <span style={{ fontSize: '20px', color: '#3fb950', fontWeight: 'bold', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{width: '8px', height: '8px', background: '#3fb950', borderRadius: '50%'}}></span>Active</span>
                        </div>
                        <div className="metric-card" onClick={() => setActiveTab('functions')} style={{ cursor: 'pointer', background: '#0d1117', border: activeTab === 'functions' ? '1px solid #58a6ff' : '1px solid #30363d', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '12px', color: activeTab === 'functions' ? '#58a6ff' : '#8b949e', fontWeight: 600 }}>FUNCTIONS</span>
                          <span style={{ fontSize: '20px', color: '#e6edf3', fontWeight: 'bold', marginTop: '8px' }}>{(graphData?.nodes || []).filter((n: GraphNode) => n.data.type === 'Function').length}</span>
                        </div>
                        <div className="metric-card" onClick={() => setActiveTab('server')} style={{ cursor: 'pointer', background: '#0d1117', border: activeTab === 'server' ? '1px solid #f85149' : '1px solid #30363d', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '12px', color: activeTab === 'server' ? '#f85149' : '#8b949e', fontWeight: 600 }}>LIVE SERVER</span>
                          <span style={{ fontSize: '20px', color: incidents.length > 0 ? '#f85149' : '#3fb950', fontWeight: 'bold', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{width: '8px', height: '8px', background: incidents.length > 0 ? '#f85149' : '#3fb950', borderRadius: '50%'}}></span>
                            {incidents.length > 0 ? 'Crash Detected' : 'Stable'}
                          </span>
                        </div>
                        <div className="metric-card" onClick={() => setActiveTab('team')} style={{ cursor: 'pointer', background: '#0d1117', border: activeTab === 'team' ? '1px solid #58a6ff' : '1px solid #30363d', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '12px', color: activeTab === 'team' ? '#58a6ff' : '#8b949e', fontWeight: 600 }}>TEAM MEMBERS</span>
                          <span style={{ fontSize: '20px', color: '#e6edf3', fontWeight: 'bold', marginTop: '8px' }}>{(p.members || []).length || 1}</span>
                        </div>
                      </div>

                      {/* ── Intelligence Center ── */}
                      {activeTab === 'repo' && (
                        <>
                      <div className="intelligence-center">
                    
                    <div className="ic-card">
                      <div className="ic-header">
                        <div>
                          <h4>Structural Analysis</h4>
                          <p>Analyze your repository to build a comprehensive knowledge graph of functions and dependencies.</p>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="btn-dash-primary" onClick={handleAnalyze} disabled={analyzing}>
                            {analyzing ? `Analyzing... ${analyzeProgress}%` : ((graphData?.nodes?.length || 0) > 0 ? 'Sync Updated Graph' : 'Create Graph')}
                          </button>
                          {(graphData?.nodes?.length || 0) > 0 && (
                            <button 
                              className="btn-dash-secondary" 
                              onClick={() => setFullScreenGraph(true)}
                              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                              </svg>
                              View Graph
                            </button>
                          )}
                        </div>
                        {analyzing && (
                          <div style={{width: '100%', marginTop: '12px'}}>
                            <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#8b949e', marginBottom: '6px'}}>
                              <span>{analyzeStep}</span>
                              <span>{analyzeProgress}%</span>
                            </div>
                            <div style={{height: '4px', background: '#21262d', borderRadius: '4px', overflow: 'hidden'}}>
                              <div style={{height: '100%', background: 'linear-gradient(90deg, #388bfd, #58a6ff)', width: `${analyzeProgress}%`, borderRadius: '4px', transition: 'width 0.5s ease'}} />
                            </div>
                          </div>
                        )}
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
                                {(queryResult.graph_context.nodes || []).map((n: GraphNode, i: number) => (
                                  <span key={i} className="ic-pill">{n.name || n.data?.label}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── Blast Radius CI Acceleration ── */}
                  {(graphData?.nodes?.length || 0) > 0 && (
                    <div className="blast-radius-card" style={{marginTop: '16px'}}>
                      <h4>⚡ Blast Radius — CI Acceleration</h4>
                      <p style={{fontSize: '11px', color: '#8b949e', marginBottom: '12px'}}>
                        Enter changed file names to calculate impact and skip unaffected tests.
                      </p>
                      <div className="blast-radius-input">
                        <input
                          type="text"
                          className="dash-input"
                          placeholder="e.g. auth.py, main.py"
                          value={blastFiles}
                          onChange={e => setBlastFiles(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleBlastRadius()}
                          style={{flex: 1}}
                        />
                        <button className="btn-dash-secondary" onClick={handleBlastRadius} disabled={blastLoading}>
                          {blastLoading ? 'Analyzing...' : 'Calculate'}
                        </button>
                      </div>

                      {blastResult && !blastResult.error && (
                        <div className="blast-radius-result">
                          <span className={`risk-badge ${(blastResult as Record<string, unknown>).risk_level}`}>
                            {(blastResult as Record<string, unknown>).risk_level as string} RISK
                          </span>
                          <div className="blast-files-grid">
                            <div className="blast-file-list">
                              <h5>🔴 Affected Files</h5>
                              {((blastResult as Record<string, unknown>).affected_files as string[] || []).map((f: string, i: number) => (
                                <div key={i} className="file-item affected">{f}</div>
                              ))}
                            </div>
                            <div className="blast-file-list">
                              <h5>🟢 Safe to Skip</h5>
                              {((blastResult as Record<string, unknown>).unaffected_files as string[] || []).map((f: string, i: number) => (
                                <div key={i} className="file-item safe">{f}</div>
                              ))}
                            </div>
                          </div>
                          <div className="blast-recommendation">
                            💡 {(blastResult as Record<string, unknown>).recommendation as string}
                          </div>
                        </div>
                      )}

                      {blastResult?.error && (
                        <div style={{color: '#f85149', fontSize: '12px', padding: '8px'}}>
                          {blastResult.error as string}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Setup Guide ── */}
                  <div className="setup-documentation-wrapper" style={{ marginTop: '30px' }}>
                    <div className="setup-header">
                      <h3>📚 Quick Setup Guide</h3>
                      <p>To integrate your local repository with this NEXUS-X workspace and unlock structural code intelligence, follow the steps below.</p>
                    </div>
                    <div className="doc-grid">
                      <div className="doc-card">
                        <div className="doc-step-badge">1</div>
                        <h4>Link Local CLI</h4>
                        <p>NEXUS-X uses a seamless local CLI agent. Link it locally since it's not on npm.</p>
                        <div className="terminal-block">
                          <div className="term-line"><span className="term-prompt">$</span> cd C:\nexus-X\cli && npm link</div>
                        </div>
                      </div>
                      <div className="doc-card">
                        <div className="doc-step-badge">2</div>
                        <h4>Initialize &amp; Connect</h4>
                        <p>Run the combined command inside your codebase to bootstrap the platform.</p>
                        <div className="terminal-block">
                          <div className="term-line term-line-interactive">
                            <span><span className="term-prompt">$</span> nexus connect {BACKEND} {p.cloneCode}</span>
                            <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText(`nexus connect ${BACKEND} ${p.cloneCode}`)} title="Copy">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="doc-card full-span">
                        <div className="doc-step-badge">3</div>
                        <h4>Sync &amp; Analyze</h4>
                        <p>Push your repository files and trigger the Code Intelligence Graph build.</p>
                        <div className="terminal-block">
                          <div className="term-line term-line-interactive">
                            <span><span className="term-prompt">$</span> nexus push && nexus analyze</span>
                            <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText(`nexus push && nexus analyze`)} title="Copy">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  </>
                  )}

                  {/* ── AI Incident Reports (Auto-Healer) ── */}
                  {activeTab === 'agent' && (
                  <div className="incident-reports-main" style={{ marginTop: '30px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '8px', padding: '24px' }}>
                    <div className="section-title" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
                      <h3 style={{ margin: 0, fontSize: '18px' }}>🚨 Production Incidents (Auto-Healer)</h3>
                      <span className="badge" style={{background: incidents.length > 0 ? '#f85149' : '#238636'}}>{incidents.length}</span>
                    </div>
                    {incidents.length === 0 ? (
                      <div className="empty-state" style={{ background: 'transparent', border: '1px dashed #30363d' }}>No production crashes detected. System is stable.</div>
                    ) : (
                      <div className="incidents-list" style={{display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px'}}>
                        {incidents.map((inc, idx) => (
                          <div key={idx} className="ic-card" style={{padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                            <div>
                              <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px'}}>
                                <span style={{
                                  background: 'rgba(248,81,73,0.1)', color: '#f85149', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold'
                                }}>EXIT {inc.exit_code}</span>
                                <strong style={{color: '#e6edf3', fontSize: '14px'}}>{inc.incident_id}</strong>
                                <span style={{color: '#8b949e', fontSize: '12px'}}>• {new Date(inc.created_at).toLocaleString()}</span>
                              </div>
                              <div style={{color: '#8b949e', fontSize: '12px'}}>{inc.summary}</div>
                            </div>
                            <button className="btn-dash-primary" onClick={async () => {
                              try {
                                const [ws, pn] = p.cloneCode.split('/');
                                const res = await fetch(`${BACKEND}/api/repo/${ws}/${pn}/incidents/${inc.incident_id}`);
                                if (res.ok) {
                                  const data = await res.json();
                                  setViewingIncident(data);
                                }
                              } catch (e) {}
                            }}>View AI Report</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  )}

                  {/* ── Functions Discovery (Middle Screen) ── */}
                  {activeTab === 'functions' && (
                  <div className="functions-discovery-main" style={{marginTop: '30px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '8px', padding: '24px'}}>
                    <div className="section-title" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
                      <h3 style={{ margin: 0, fontSize: '18px' }}>🛠️ Discovered Functions</h3>
                      <span className="badge">{graphData?.nodes.filter((n: GraphNode) => n.data.type === 'Function').length || 0}</span>
                    </div>
                    
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                      gap: '16px',
                      marginTop: '16px'
                    }}>
                      {graphData?.nodes
                        .filter((n: GraphNode) => n.data.type === 'Function')
                        .sort((a: GraphNode, b: GraphNode) => b.data.blast_radius - a.data.blast_radius)
                        .map((fn: GraphNode) => (
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
                      {(!graphData || graphData.nodes.filter((n: GraphNode) => n.data.type === 'Function').length === 0) && (
                        <div className="empty-state" style={{gridColumn: '1/-1'}}>
                          No functions discovered yet. Analyze the repository to build the graph.
                        </div>
                      )}
                    </div>
                  </div>
                  )}

                  {/* ── Live Production Telemetry ── */}
                  {activeTab === 'server' && (
                  <div style={{ marginTop: '30px' }}>
                    {/* Setup Guide for Server Connection */}
                    <div className="setup-documentation-wrapper" style={{ marginBottom: '24px' }}>
                      <div className="setup-header">
                        <h3>📡 Connect Your Production Server</h3>
                        <p>Stream live logs from any running process directly into this dashboard. Nexus-X will automatically detect crashes and trigger the AI forensic pipeline.</p>
                      </div>
                      <div className="doc-grid">
                        <div className="doc-card">
                          <div className="doc-step-badge">1</div>
                          <h4>Inject Monitoring (One-Time)</h4>
                          <p>Run <code style={{color: '#58a6ff'}}>nexus inject</code> in your project. It rewrites <code style={{color: '#58a6ff'}}>package.json</code> so <code style={{color: '#58a6ff'}}>npm start</code> automatically streams logs to Nexus-X.</p>
                          <div className="terminal-block">
                            <div className="term-line term-line-interactive">
                              <span><span className="term-prompt">$</span> cd /path/to/your-project</span>
                            </div>
                            <div className="term-line term-line-interactive">
                              <span><span className="term-prompt">$</span> nexus inject</span>
                              <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText('nexus inject')} title="Copy">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                              </button>
                            </div>
                          </div>
                          <p style={{fontSize: '11px', color: '#8b949e', marginTop: '8px'}}>This modifies <code>scripts.start</code> → <code>nexus attach {'<original>'}</code>. To undo: <code>nexus eject</code></p>
                        </div>
                        <div className="doc-card">
                          <div className="doc-step-badge">2</div>
                          <h4>Deploy Normally</h4>
                          <p>Now just run your app like you always do. Nexus-X monitoring is baked in.</p>
                          <div className="terminal-block">
                            <div className="term-line term-line-interactive">
                              <span><span className="term-prompt">$</span> npm start</span>
                              <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText('npm start')} title="Copy">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                              </button>
                            </div>
                          </div>
                          <p style={{fontSize: '11px', color: '#8b949e', marginTop: '8px'}}>All stdout/stderr will stream live to this terminal. Crashes auto-trigger the AI forensic pipeline.</p>
                        </div>
                        <div className="doc-card full-span">
                          <div className="doc-step-badge">⌥</div>
                          <h4>Manual Alternative</h4>
                          <p>If you don't want to modify <code style={{color: '#58a6ff'}}>package.json</code>, wrap any command manually:</p>
                          <div className="terminal-block">
                            <div className="term-line term-line-interactive">
                              <span><span className="term-prompt">$</span> nexus attach node server.js</span>
                              <button className="clone-copy inline-copy" onClick={() => navigator.clipboard.writeText('nexus attach node server.js')} title="Copy">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Live Terminal */}
                    <div className="production-telemetry" style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '8px', padding: '24px' }}>
                      <div className="section-title" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center' }}>
                        <h3 style={{ margin: 0, fontSize: '18px' }}>📡 Live Server Telemetry</h3>
                      </div>
                      <div style={{ height: '400px', width: '100%', border: '1px solid #30363d', borderRadius: '8px', overflow: 'hidden', background: '#010409' }}>
                        <LiveTerminal workspace={p.cloneCode.split('/')[0]} project={p.cloneCode.split('/')[1]} />
                      </div>
                    </div>
                  </div>
                  )}

                  {/* ── Team Members ── */}
                  {activeTab === 'team' && (
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
                  )}

                  </>
                  )}
                  <FileTree
                    data={treeData}
                    loading={treeLoading}
                    noPush={noPush}
                    onFileClick={handleFileClick}
                  />

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

      {/* ── Incident Report Modal ── */}
      {viewingIncident && (
        <div className="file-viewer-modal">
          <div className="fvm-content" style={{ maxWidth: '800px' }}>
            <div className="fvm-header" style={{ borderBottom: '1px solid #f85149', background: 'rgba(248,81,73,0.05)' }}>
              <span className="fvm-title" style={{ color: '#f85149' }}>🚨 AI Forensic Report: {viewingIncident.incident_id}</span>
              <button className="fvm-close" onClick={() => setViewingIncident(null)}>✕</button>
            </div>
            <div className="fvm-body" style={{ padding: '24px', background: '#0d1117' }}>
              <SyntaxHighlighter
                language="markdown"
                style={vscDarkPlus}
                customStyle={{ margin: 0, padding: 0, background: 'transparent', fontSize: '14px' }}
                wrapLines={true}
              >
                {viewingIncident.report_markdown || 'No markdown generated.'}
              </SyntaxHighlighter>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
