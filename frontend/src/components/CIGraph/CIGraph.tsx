import { useState, useEffect, useRef, useMemo } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import EdgeCurveProgram from '@sigma/edge-curve';
import forceAtlas2 from 'graphology-layout-forceatlas2';

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CONSTANTS & TYPES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const STATUS_COLOR = {
  SAFE: '#3fb950',
  WARNING: '#d29922',
  CRITICAL: '#f85149',
  PENDING: '#388bfd',
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MAIN COMPONENT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export function CIGraph({ graphData }: { graphData: any }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const layoutTimeoutRef = useRef<any>(null);

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Retrieve actual data backing the currently selected node
  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId || !graphData?.nodes) return null;
    return graphData.nodes.find((n: any) => n.id === selectedNodeId);
  }, [selectedNodeId, graphData]);

  // Core initialization: Graphology + Sigma.js
  useEffect(() => {
    if (!containerRef.current || !graphData?.nodes) return;

    // 1. Build the math model (Graphology)
    const graph = new Graph();
    
    // Golden angle placement mathematics specific to GitNexus clusters
    const nodeCount = graphData.nodes.length;
    const structuralSpread = Math.sqrt(nodeCount) * 80;

    // Filter nodes down manually to ignore unconnected/deleted UI states 
    // Usually Sigma prefers we just load everything and use `hidden` property on nodes.
    const fNodes = graphData.nodes.map((n: any) => ({ ...n }));
    const fNodeIds = new Set(fNodes.map((n: any) => n.id));
    
    fNodes.forEach((n: any, index: number) => {
      // Golden angle orbital placement
      const goldenAngle = Math.PI * (3 - Math.sqrt(5));
      const angle = index * goldenAngle;
      const radius = structuralSpread * Math.sqrt((index + 1) / Math.max(nodeCount, 1));
      
      const x = radius * Math.cos(angle);
      const y = radius * Math.sin(angle);

      const status = n.data?.status || 'PENDING';
      const color = STATUS_COLOR[status as keyof typeof STATUS_COLOR] || STATUS_COLOR.PENDING;
      const blastRadius = n.data?.blast_radius || 1;
      
      const isLogic = n.data?.type === 'Function' || n.data?.type === 'Class';
      const mass = isLogic ? 2 : 15; // Files/Modules repulse hard, functions stick near them

      let displayLabel = n.data?.label || n.id;
      if (n.data?.type === 'Function') displayLabel = `ƒ ${displayLabel}`;
      else if (n.data?.type === 'Class') displayLabel = `© ${displayLabel}`;
      else if (n.data?.type === 'Module' && !displayLabel.includes('Cluster')) displayLabel = `📁 ${displayLabel}`;

      graph.addNode(n.id, {
        x: x,
        y: y,
        size: 3 + Math.min(blastRadius, 10), // Base Sigma WebGL node size
        color: color,
        label: displayLabel,
        mass: mass, // Specific param used natively by FA2
        
        // Stashed nexus-X custom properties
        originalColor: color,
        data: n.data,
        hidden: false
      });
    });

    (graphData.edges || []).forEach((e: any) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target)) {
        
        // Fetch target info to colorize the edge appropriately
        const targetNode = graphData.nodes.find((n: any) => n.id === e.target);
        const targetStatus = targetNode?.data?.status || 'SAFE';
        let edgeColor = 'rgba(61,68,77,0.3)';
        if (targetStatus === 'CRITICAL') edgeColor = 'rgba(248,81,73,0.5)';
        else if (targetStatus === 'WARNING') edgeColor = 'rgba(210,153,34,0.4)';

        graph.addEdge(e.source, e.target, {
          size: targetStatus === 'CRITICAL' ? 2 : 1,
          color: edgeColor,
          type: 'curved' // Native GitNexus @sigma/edge-curve integration
        });
      }
    });

    // 2. Explicitly compute ForceAtlas2 physics positions into the math model 
    // GitNexus uses forceAtlas2.assign to physically lock the clustering math down instantly
    forceAtlas2.assign(graph, {
      iterations: Math.min(Math.max(nodeCount * 3, 300), 1000), // Scale iterations precisely to graph size
      settings: forceAtlas2.inferSettings(graph),
    });

    // 3. Mount Sigma WebGL renderer
    const sigma = new Sigma(graph, containerRef.current, {
      defaultNodeType: 'circle',
      defaultEdgeType: 'curved',
      edgeProgramClasses: {
        curved: EdgeCurveProgram,
      },
      labelFont: "'JetBrains Mono', monospace",
      labelColor: { color: '#8b949e' },
      labelSize: 11,
      labelWeight: '600'
    });
    
    sigmaRef.current = sigma;

    // View initialization
    sigma.getCamera().animatedZoom({ factor: 1.2, duration: 600 });

    // Interaction Overrides
    sigma.on("clickNode", (event) => {
       const clickedId = event.node;
       setSelectedNodeId(clickedId);
       
       // Explicitly NO CAMERA ZOOM: Keep graph perfectly steady when user clicks
    });

    sigma.on("clickStage", () => {
       setSelectedNodeId(null);
    });

    // Hover dynamics to dim non-connected lines
    let hoveredNode: string | null = null;
    sigma.on("enterNode", (event) => {
      hoveredNode = event.node;
      sigma.refresh();
    });
    sigma.on("leaveNode", () => {
      hoveredNode = null;
      sigma.refresh();
    });

    // WebGL Custom shader filter pipeline
    sigma.setSetting("nodeReducer", (node, data) => {
      const res: any = { ...data };
      
      // If we are searching, dim non-matching nodes
      if (hoveredNode && hoveredNode !== node && !graph.areNeighbors(hoveredNode, node)) {
        res.label = "";
        res.color = "#30363d";
      }

      // Hide nodes completely if they don't match the active search input
      if (res.hidden) {
         res.hidden = true;
         res.size = 0;
      }
      return res;
    });

    sigma.setSetting("edgeReducer", (edge, data) => {
      const res: any = { ...data };
      if (hoveredNode && !graph.hasExtremity(edge, hoveredNode)) {
        res.hidden = true; // GitNexus hides non-relevant edges on hover!
      }
      return res;
    });

    return () => {
      sigma.kill();
    };
  }, [graphData]); // Re-mount entirely when raw backend data drops in.

  // Real-time client-side filters (Search / Status dropdowns)
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    
    const graph = sigma.getGraph();
    
    // Iterate over everything actively tracked in WebGL and hide/show
    graph.forEachNode((nodeId, attributes: any) => {
      const rawData = attributes.data;
      const matchesSearch = !search || rawData?.label?.toLowerCase().includes(search.toLowerCase());
      
      let matchesFilter = true;
      if (filter === 'functions') matchesFilter = rawData?.type === 'Function';
      else if (filter === 'critical') matchesFilter = rawData?.status === 'CRITICAL';
      else if (filter === 'warning') matchesFilter = ['WARNING', 'CRITICAL'].includes(rawData?.status);
      
      graph.setNodeAttribute(nodeId, 'hidden', !(matchesSearch && matchesFilter));
    });

    sigma.refresh();
  }, [search, filter]);
  

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#0d1117',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* TOOLBAR */}
      <div
        style={{
          height: 44,
          background: '#161b22',
          borderBottom: '1px solid #21262d',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 12,
          flexShrink: 0,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          zIndex: 10
        }}
      >
        <span style={{ color: '#f85149' }}>
          ● {graphData?.nodes?.filter((n: any) => n.data?.status === 'CRITICAL').length || 0} critical
        </span>
        <span style={{ color: '#d29922' }}>
          ● {graphData?.nodes?.filter((n: any) => n.data?.status === 'WARNING').length || 0} warning
        </span>
        <span style={{ color: '#3fb950' }}>
          ● {graphData?.nodes?.filter((n: any) => n.data?.status === 'SAFE').length || 0} safe
        </span>

        <div style={{ flex: 1 }} />

        {/* Search */}
        <input
          placeholder="Search items..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: '#0d1117',
            border: '1px solid #30363d',
            borderRadius: 6,
            padding: '4px 10px',
            color: '#e6edf3',
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
            width: 180,
            outline: 'none',
          }}
        />

        {/* Filter Dropdown */}
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: 6,
            padding: '4px 10px',
            color: '#8b949e',
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="all">All nodes</option>
          <option value="functions">Functions only</option>
          <option value="critical">Critical only</option>
          <option value="warning">Warning +</option>
        </select>
      </div>

      {/* WEBGL SIGMA.JS CANVAS BOUNDING BOX */}
      <div style={{ flex: 1, position: 'relative' }}>
        {/* SIGMA CONTROLLED DOM - MUST BE EMPTY FOR REACT */}
        <div ref={containerRef} style={{ width: '100%', height: '100%', cursor: 'grab', outline: 'none' }} />
        
        {/* DETAIL SIDEBAR — OVERLAY ON CLICK */}
        {selectedNodeData && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              right: 0,
              width: 320,
              height: '100%',
              background: 'rgba(22, 27, 34, 0.95)',
              borderLeft: '1px solid #30363d',
              padding: 20,
              overflowY: 'auto',
              fontFamily: "'JetBrains Mono', monospace",
              zIndex: 20,
              boxShadow: '-4px 0 20px rgba(0,0,0,0.5)'
            }}
          >
            {/* Close Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 16,
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 700, color: '#e6edf3', wordBreak: 'break-all' }}>
                {selectedNodeData.data?.label || selectedNodeId}
              </span>
              <button
                onClick={() => setSelectedNodeId(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#8b949e',
                  cursor: 'pointer',
                  fontSize: 18,
                  padding: 4
                }}
              >
                ✕
              </button>
            </div>

            {/* Sub Labels */}
            <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 6 }}>
              <strong style={{ color: '#c9d1d9' }}>Type:</strong> {selectedNodeData.data?.type || 'Unknown'}
            </div>
            <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 20 }}>
              <strong style={{ color: '#c9d1d9' }}>File:</strong> {selectedNodeData.data?.file || 'N/A'}
            </div>

            {/* Score Meters */}
            {[
              ['Security', selectedNodeData.data?.security_score ?? 100, '#f85149'],
              ['Reliability', selectedNodeData.data?.reliability_score ?? 100, '#3fb950'],
              ['Scalability', selectedNodeData.data?.scalability_score ?? 100, '#388bfd'],
            ].map(([label, score, color]) => (
              <div key={label as string} style={{ marginBottom: 16 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 10,
                    color: '#8b949e',
                    marginBottom: 6,
                    fontWeight: 600
                  }}
                >
                  <span style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
                  <span style={{ color: '#e6edf3' }}>{score}</span>
                </div>
                <div style={{ height: 5, background: '#21262d', borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      borderRadius: 3,
                      width: `${Math.min(100, Math.max(0, Number(score)))}%`,
                      background: color as string,
                    }}
                  />
                </div>
              </div>
            ))}

            <div style={{ height: 1, background: '#30363d', margin: '20px 0' }} />

            {/* Metadata Table */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                ['Connections (Blast)', selectedNodeData.data?.blast_radius ?? 0],
                ['Status', selectedNodeData.data?.status ?? 'SAFE'],
              ].map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 11,
                  }}
                >
                  <span style={{ color: '#8b949e' }}>{k}</span>
                  <span style={{ 
                    color: k === 'Status' ? STATUS_COLOR[(v as string) as keyof typeof STATUS_COLOR] : '#e6edf3',
                    fontWeight: k === 'Status' ? 700 : 400
                  }}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
            
            <div style={{ height: 1, background: '#30363d', margin: '20px 0' }} />

            {/* CLI Commands */}
            {['nexus context', 'nexus impact', 'nexus flow'].map((cmd) => (
              <button
                key={cmd}
                style={{
                  width: '100%',
                  marginBottom: 8,
                  background: '#21262d',
                  border: '1px solid #30363d',
                  borderRadius: 6,
                  padding: '8px 12px',
                  color: '#8b949e',
                  fontSize: 11,
                  fontFamily: "'JetBrains Mono', monospace",
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: '0.2s ease',
                }}
                onMouseOver={(e) => e.currentTarget.style.background = '#30363d'}
                onMouseOut={(e) => e.currentTarget.style.background = '#21262d'}
              >
                <span style={{ color: '#58a6ff' }}>$</span> {cmd} {selectedNodeData.data?.label || selectedNodeId}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default CIGraph;
