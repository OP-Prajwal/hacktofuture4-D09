import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import './LiveTerminal.css';

const BACKEND_WS = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000')
  .replace('http://', 'ws://')
  .replace('https://', 'wss://');

interface DiagnosisHypothesis {
  title: string;
  confidence: number;
  evidence: string[];
  likely_locations: string[];
  next_steps: string[];
}

interface DiagnosisResult {
  status: string;
  summary: string;
  hypotheses: DiagnosisHypothesis[];
  code_locations: { path: string; line_hint: number | null; confidence: number; rationale: string }[];
}

interface LiveTerminalProps {
  workspace: string;
  project: string;
  onFileClick?: (filePath: string, line?: number) => void;
}

export default function LiveTerminal({ workspace, project, onFileClick }: LiveTerminalProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const termInstance = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);

  const writeToTerminal = useCallback((text: string, stream?: string) => {
    if (!termInstance.current) return;
    const color = stream === 'stderr' ? '\x1b[31m' : '\x1b[37m';
    const reset = '\x1b[0m';
    termInstance.current.writeln(`${color}${text}${reset}`);
  }, []);

  const writeWelcome = useCallback(() => {
    if (!termInstance.current) return;
    const term = termInstance.current;
    term.writeln('\x1b[36m╔══════════════════════════════════════╗\x1b[0m');
    term.writeln('\x1b[36m║   NEXUS-X Live CI/CD Terminal       ║\x1b[0m');
    term.writeln('\x1b[36m╚══════════════════════════════════════╝\x1b[0m');
    term.writeln('');
    term.writeln('\x1b[90mWaiting for runner connection...\x1b[0m');
    term.writeln(`\x1b[90mWatching ${workspace}/${project}\x1b[0m`);
    term.writeln('\x1b[90mConnect a runner: nexus run <command>\x1b[0m');
    term.writeln('');
  }, [workspace, project]);

  // Initialize xterm
  useEffect(() => {
    if (!termRef.current) return;

    const term = new Terminal({
      theme: {
        background: '#0d1117',
        foreground: '#e6edf3',
        cursor: '#58a6ff',
        cursorAccent: '#0d1117',
        selectionBackground: 'rgba(56, 139, 253, 0.3)',
        black: '#0d1117',
        red: '#f85149',
        green: '#3fb950',
        yellow: '#d29922',
        blue: '#58a6ff',
        magenta: '#bc8cff',
        cyan: '#39d353',
        white: '#e6edf3',
        brightBlack: '#484f58',
        brightRed: '#f85149',
        brightGreen: '#3fb950',
        brightYellow: '#d29922',
        brightBlue: '#58a6ff',
        brightMagenta: '#bc8cff',
        brightCyan: '#39d353',
        brightWhite: '#f0f6fc',
      },
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: 12,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: 'bar',
      scrollback: 5000,
      convertEol: true,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(termRef.current);
    fit.fit();

    termInstance.current = term;
    fitAddon.current = fit;

    setStatus('idle');
    setDiagnosis(null);
    writeWelcome();

    // Handle resize
    const handleResize = () => {
      try { fit.fit(); } catch { /* ignore */ }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      term.dispose();
      termInstance.current = null;
    };
  }, [workspace, project, writeWelcome]);

  // WebSocket connection
  useEffect(() => {
    setStatus('idle');
    setDiagnosis(null);

    const wsUrl = `${BACKEND_WS}/ws/viewer/${encodeURIComponent(workspace)}/${encodeURIComponent(project)}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      writeToTerminal('\x1b[32m● Connected to Nexus-X backend\x1b[0m');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
      } catch {
        writeToTerminal(event.data);
      }
    };

    ws.onclose = () => {
      writeToTerminal('\x1b[33m● Disconnected from backend\x1b[0m');
    };

    ws.onerror = () => {
      writeToTerminal('\x1b[31m● WebSocket error — retrying...\x1b[0m');
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [workspace, project, writeToTerminal]);

  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    const msgType = data.type as string;

    switch (msgType) {
      case 'session_info':
        setStatus(data.status as typeof status);
        if (data.has_runner) {
          writeToTerminal('\x1b[32m● Runner is connected. Streaming logs...\x1b[0m');
        }
        if ((data.log_count as number) > 0) {
          writeToTerminal(`\x1b[90m● Replaying ${(data.log_count as number)} buffered log entries\x1b[0m`);
        }
        break;

      case 'system':
        writeToTerminal(`\x1b[36m● ${data.message}\x1b[0m`);
        setStatus('running');
        break;

      case 'log':
        writeToTerminal(data.line as string, data.stream as string);
        break;

      case 'step':
        writeToTerminal(`\x1b[33m▶ Step: ${data.name} [${data.status}]\x1b[0m`);
        break;

      case 'exit': {
        const code = data.code as number;
        if (code === 0) {
          writeToTerminal('\x1b[32m\n✓ Pipeline completed successfully\x1b[0m');
          setStatus('success');
        } else {
          writeToTerminal(`\x1b[31m\n✗ Pipeline failed with exit code ${code}\x1b[0m`);
          setStatus('failed');
        }
        break;
      }

      case 'incident_analysis_start':
        writeToTerminal('\x1b[35m\n🔧 Auto-healing: Analyzing failure with AI...\x1b[0m');
        break;

      case 'incident_report':
        setDiagnosis((data.result as DiagnosisResult) || null);
        writeToTerminal('\x1b[35m✓ AI diagnosis ready — see panel below\x1b[0m');
        break;

      default:
        break;
    }
  }, [writeToTerminal]);

  // Resize the terminal when the container resizes
  useEffect(() => {
    const interval = setInterval(() => {
      try { fitAddon.current?.fit(); } catch { /* ignore */ }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="live-terminal-container">
      {/* Header */}
      <div className="live-terminal-header">
        <div className="terminal-title">
          <span className={`dot ${status}`} />
          <span>CI/CD Terminal</span>
          <span style={{ color: '#8b949e', fontSize: '10px' }}>
            {workspace}/{project}
          </span>
        </div>
        <span className={`terminal-status ${status}`}>
          {status.toUpperCase()}
        </span>
      </div>

      {/* Terminal */}
      <div className="live-terminal-body" ref={termRef} />

      {/* Diagnosis Panel — shown when CI fails and AI analyzes */}
      {diagnosis && diagnosis.hypotheses?.length > 0 && (
        <div className="diagnosis-panel">
          <h4>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f85149" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            AI Root-Cause Analysis
          </h4>

          {diagnosis.hypotheses.map((hypo, i) => (
            <div key={i} className="diagnosis-hypothesis">
              <div className="hypo-title">{i + 1}. {hypo.title}</div>
              <div className="hypo-confidence">
                Confidence: {(hypo.confidence * 100).toFixed(0)}%
              </div>

              {hypo.evidence?.map((ev, j) => (
                <div key={j} className="hypo-evidence">{ev}</div>
              ))}

              {hypo.likely_locations?.length > 0 && (
                <div className="hypo-locations">
                  {hypo.likely_locations.map((loc, k) => (
                    <span
                      key={k}
                      className="loc-pill"
                      onClick={() => onFileClick?.(loc)}
                    >
                      📄 {loc}
                    </span>
                  ))}
                </div>
              )}

              {hypo.next_steps?.length > 0 && (
                <ol className="hypo-steps">
                  {hypo.next_steps.map((step, k) => (
                    <li key={k}>{step}</li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
