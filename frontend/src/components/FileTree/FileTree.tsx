import { useState } from 'react';
import './FileTree.css';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FileNode {
  type: 'file';
  name: string;
  hash: string;
  size: number;
  extension: string;
}

export interface DirNode {
  type: 'dir';
  name: string;
  children: TreeNode[];
}

export type TreeNode = FileNode | DirNode;

export interface TreeData {
  commit_id: string;
  pushed_at: string;
  total_files: number;
  tree: DirNode;
}

// ─── Extension → colour mapping ──────────────────────────────────────────────

const EXT_COLORS: Record<string, string> = {
  '.ts': '#3178c6', '.tsx': '#3178c6',
  '.js': '#f7df1e', '.jsx': '#f7df1e',
  '.py': '#3572a5',
  '.rs': '#dea584',
  '.go': '#00add8',
  '.css': '#563d7c',
  '.html': '#e34c26',
  '.json': '#8bc34a',
  '.md': '#ffffff',
  '.yaml': '#cb171e', '.yml': '#cb171e',
  '.env': '#39d353',
  '.sh': '#89e051',
  '.txt': '#8b949e',
  '.toml': '#9c4121',
};

function extColor(ext: string): string {
  return EXT_COLORS[ext.toLowerCase()] ?? '#8b949e';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

// ─── Individual tree nodes ────────────────────────────────────────────────────

function FileRow({ node }: { node: FileNode }) {
  return (
    <div className="ft-row ft-file">
      <span className="ft-indent-line" />
      <span className="ft-icon file-icon">
        <span className="ft-ext-dot" style={{ background: extColor(node.extension) }} />
      </span>
      <span className="ft-name">{node.name}</span>
      <span className="ft-size">{formatSize(node.size)}</span>
      <span className="ft-hash" title={node.hash}>{node.hash.slice(0, 7)}</span>
    </div>
  );
}

function DirRow({ node, depth }: { node: DirNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2); // expand first 2 levels by default

  return (
    <div className="ft-dir-wrap">
      <button className="ft-row ft-dir" onClick={() => setOpen(o => !o)}>
        <span className="ft-icon dir-icon">{open ? '▾' : '▸'}</span>
        <span className="ft-name dir-name">{node.name}</span>
        <span className="ft-count">{node.children.length}</span>
      </button>
      {open && (
        <div className="ft-children" style={{ '--depth': depth } as React.CSSProperties}>
          {node.children.map((child, i) =>
            child.type === 'dir'
              ? <DirRow key={i} node={child} depth={depth + 1} />
              : <FileRow key={i} node={child} />
          )}
        </div>
      )}
    </div>
  );
}

// ─── Root component ───────────────────────────────────────────────────────────

interface FileTreeProps {
  data: TreeData | null;
  loading: boolean;
  noPush: boolean;
}

export default function FileTree({ data, loading, noPush }: FileTreeProps) {
  if (loading) {
    return (
      <div className="ft-state">
        <div className="ft-spinner" />
        <span>Loading file tree…</span>
      </div>
    );
  }

  if (noPush) {
    return (
      <div className="ft-state ft-no-push">
        <span className="ft-state-icon">⬡</span>
        <span>No push yet.</span>
        <span className="ft-state-sub">Run <code>nexus push</code> to populate the graph.</span>
      </div>
    );
  }

  if (!data) return null;

  const pushed = new Date(data.pushed_at).toLocaleString('en-IN', {
    dateStyle: 'medium', timeStyle: 'short'
  });

  return (
    <div className="ft-root">
      <div className="ft-header">
        <div className="ft-header-left">
          <span className="ft-header-title">File Tree</span>
          <span className="ft-badge">{data.total_files} files</span>
        </div>
        <span className="ft-pushed">pushed {pushed}</span>
      </div>
      <div className="ft-body">
        {data.tree.children.map((child, i) =>
          child.type === 'dir'
            ? <DirRow key={i} node={child} depth={0} />
            : <FileRow key={i} node={child} />
        )}
      </div>
    </div>
  );
}
