import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const STATUS_COLOR = {
  SAFE: '#3fb950',
  WARNING: '#d29922',
  CRITICAL: '#f85149',
  PENDING: '#388bfd',
};

export function CIGraph({ graphData }: { graphData: any }) {
  const [search, setSearch] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<any | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Tweak physics values to spread nodes out neatly
  useEffect(() => {
    if (fgRef.current) {
      // Stronger repulsion keeps nodes away from each other
      fgRef.current.d3Force('charge').strength(-800).distanceMax(1000);
      // Give links more room to breathe
      fgRef.current.d3Force('link').distance(120);
      // Weaker center gravity lets the graph expand highly flexibly
      fgRef.current.d3Force('center', null);
    }
  }, [graphData]);

  // Filter nodes based on search
  const filteredData = useMemo(() => {
    if (!graphData?.nodes) return { nodes: [], links: [] };

    const nodes = graphData.nodes.map((n: any) => ({
      ...n,
      id: n.id,
      name: n.data?.label || n.id,
      color: STATUS_COLOR[n.data?.status as keyof typeof STATUS_COLOR] || STATUS_COLOR.PENDING,
      val: 5 + Math.min(n.data?.blast_radius || 0, 20),
      hidden: search && !(n.data?.label?.toLowerCase().includes(search.toLowerCase()))
    }));

    // Find all links between visible nodes
    const links = (graphData.edges || []).map((e: any) => ({
      source: e.source,
      target: e.target,
      color: 'rgba(61, 68, 77, 0.3)'
    }));

    return { nodes, links };
  }, [graphData, search]);

  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId || !graphData?.nodes) return null;
    return graphData.nodes.find((n: any) => n.id === selectedNodeId);
  }, [selectedNodeId, graphData]);

  // Highlighting logic
  const highlightNodes = useMemo(() => {
    const set = new Set();
    if (hoveredNode) {
      set.add(hoveredNode);
      // Add neighbors
      (graphData.edges || []).forEach((e: any) => {
        if (e.source === hoveredNode) set.add(e.target);
        if (e.target === hoveredNode) set.add(e.source);
      });
    }
    return set;
  }, [hoveredNode, graphData.edges]);

  const highlightLinks = useMemo(() => {
    const set = new Set();
    if (hoveredNode) {
      (graphData.edges || []).forEach((e: any) => {
        if (e.source === hoveredNode || e.target === hoveredNode) {
          // In react-force-graph, links are objects, but we can match by source/target
          // However, it's better to match the actual link objects if possible.
        }
      });
    }
    return set;
  }, [hoveredNode, graphData.edges]);

  // Fallback for empty/black screen
  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <div style={{ width: '100%', height: '100%', background: '#0d1117', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', fontFamily: "'JetBrains Mono', monospace" }}>
          <div style={{ fontSize: '40px', marginBottom: '16px', opacity: 0.2 }}>🕸️</div>
          <h3 style={{ color: '#8b949e', fontSize: '14px', margin: 0 }}>No Graph Snapshot Found</h3>
          <p style={{ color: '#484f58', fontSize: '11px', marginTop: '8px' }}>Run the analysis to build your code intelligence graph.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', background: '#0d1117', display: 'flex', flexDirection: 'column' }}>
      <div style={{ height: 44, background: '#161b22', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 12, flexShrink: 0, zIndex: 10 }}>
        <input
          placeholder="Search components..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 6, padding: '4px 10px', color: '#e6edf3', fontSize: 11, width: 180, outline: 'none' }}
        />
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 10 }}>
          <span style={{ color: '#f85149', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>● Critical</span>
          <span style={{ color: '#d29922', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>● Warning</span>
          <span style={{ color: '#3fb950', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>● Safe</span>
        </div>
      </div>

      <div ref={containerRef} style={{ flex: 1, position: 'relative', minHeight: 0, userSelect: 'none', overflow: 'hidden' }}>
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width || 800}
          height={dimensions.height || 600}
          graphData={filteredData}
          backgroundColor="#0d1117"
          nodeLabel={(n: any) => n.name}
          nodeRelSize={1}
          nodeVal={(n: any) => n.val}
          nodeColor={(n: any) => {
            if (n.hidden) return 'transparent';
            if (hoveredNode && !highlightNodes.has(n.id)) return '#21262d';
            return n.color;
          }}
          linkColor={(l: any) => {
            if (hoveredNode) {
              const isConnected = l.source.id === hoveredNode || l.target.id === hoveredNode;
              return isConnected ? '#58a6ff' : 'rgba(33, 38, 45, 0.2)';
            }
            return 'rgba(230, 237, 243, 0.4)'; // highly visible light connections
          }}
          linkWidth={(l: any) => {
            if (hoveredNode) {
              const isConnected = l.source.id === hoveredNode || l.target.id === hoveredNode;
              return isConnected ? 3 : 1;
            }
            return 2; // thicker base string
          }}
          linkDirectionalParticles={(l: any) => {
            if (hoveredNode) {
              return (l.source.id === hoveredNode || l.target.id === hoveredNode) ? 6 : 0;
            }
            if (hoveredLink && l === hoveredLink) {
              return 6;
            }
            return 0; // only visible when hovered!
          }}
          linkDirectionalParticleWidth={4}
          linkDirectionalParticleSpeed={0.008}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          cooldownTicks={200}
          onNodeClick={(node: any) => setSelectedNodeId(node.id)}
          onNodeHover={(node: any) => setHoveredNode(node ? node.id : null)}
          onLinkHover={(link: any) => setHoveredLink(link)}
          onBackgroundClick={() => setSelectedNodeId(null)}
          onNodeDragEnd={(node: any) => {
            // Pin the node in place after dragging to allow stretching lines indefinitely
            node.fx = node.x;
            node.fy = node.y;
          }}
          onEngineStop={() => {
            // Once the initial layout finishes, permanently FREEZE every single node in place!
            // This ensures pulling one node will NEVER move the rest of the graph.
            if (filteredData && filteredData.nodes) {
              filteredData.nodes.forEach((n: any) => {
                n.fx = n.x;
                n.fy = n.y;
              });
            }
          }}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            if (node.hidden) return;
            const label = node.name;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px 'JetBrains Mono', monospace`;
            
            // Draw circle
            const r = Math.sqrt(node.val) * 2;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
            ctx.fillStyle = (hoveredNode && !highlightNodes.has(node.id)) ? '#21262d' : node.color;
            ctx.fill();

            // Draw label if zoomed in or hovered
            if (globalScale > 1.5 || (hoveredNode && highlightNodes.has(node.id))) {
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = (hoveredNode && highlightNodes.has(node.id)) ? '#e6edf3' : '#8b949e';
              ctx.fillText(label, node.x, node.y + r + fontSize);
            }
          }}
        />
        
        {selectedNodeData && (
          <div style={{ position: 'absolute', top: 0, right: 0, width: 320, height: '100%', background: 'rgba(22, 27, 34, 0.98)', borderLeft: '1px solid #30363d', padding: 24, zIndex: 20, boxSizing: 'border-box', boxShadow: '-8px 0 30px rgba(0,0,0,0.6)', overflowY: 'auto', fontFamily: "'JetBrains Mono', monospace", userSelect: 'text' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <span style={{ color: '#e6edf3', fontSize: 14, fontWeight: 'bold' }}>{selectedNodeData.data?.label || selectedNodeId}</span>
              <button onClick={() => setSelectedNodeId(null)} style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: 18 }}>✕</button>
            </div>
            <div style={{ fontSize: 11, color: '#8b949e' }}>
               <p style={{ marginBottom: '12px', lineHeight: '1.4', color: '#c9d1d9', fontSize: '12px' }}>
                 {selectedNodeData.data?.summary || 'No description available.'}
               </p>
               
               {selectedNodeData.data?.tags && selectedNodeData.data.tags.length > 0 && (
                 <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                   {selectedNodeData.data.tags.map((tag: string) => (
                     <span key={tag} style={{ background: 'rgba(56, 139, 253, 0.1)', color: '#388bfd', padding: '2px 8px', borderRadius: '10px', fontSize: '9px', border: '1px solid rgba(56, 139, 253, 0.2)' }}>
                       {tag}
                     </span>
                   ))}
                 </div>
               )}

               <div style={{ height: '1px', background: '#30363d', margin: '16px 0' }} />

               <p style={{ marginBottom: '8px' }}>File: <span style={{ color: '#c9d1d9' }}>{selectedNodeData.data?.file}</span></p>
               <p style={{ marginBottom: '8px' }}>Type: <span style={{ color: '#58a6ff' }}>{selectedNodeData.data?.type}</span></p>
               <p style={{ marginBottom: '8px' }}>Blast: <span style={{ color: '#f85149' }}>{selectedNodeData.data?.blast_radius}</span></p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CIGraph;
