import { useState, useEffect, useRef, useMemo } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import EdgeCurveProgram from '@sigma/edge-curve';
import forceAtlas2 from 'graphology-layout-forceatlas2';

const STATUS_COLOR = {
  SAFE: '#3fb950',
  WARNING: '#d29922',
  CRITICAL: '#f85149',
  PENDING: '#388bfd',
};

export function CIGraph({ graphData }: { graphData: any }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph>(new Graph());

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId || !graphData?.nodes) return null;
    return graphData.nodes.find((n: any) => n.id === selectedNodeId);
  }, [selectedNodeId, graphData]);

  // Sync data to Graph
  const syncGraphData = () => {
    const graph = graphRef.current;
    if (!graphData?.nodes) return;
    graph.clear();
    const nodeCount = graphData.nodes.length;
    const spread = Math.sqrt(nodeCount) * 160;

    graphData.nodes.forEach((n: any, i: number) => {
      const angle = i * (Math.PI * (3 - Math.sqrt(5)));
      const radius = spread * Math.sqrt((i + 1) / Math.max(nodeCount, 1));
      const status = n.data?.status || 'PENDING';
      const color = STATUS_COLOR[status as keyof typeof STATUS_COLOR] || STATUS_COLOR.PENDING;
      
      let displayLabel = n.data?.label || n.id;
      if (n.data?.type === 'Function') displayLabel = `ƒ ${displayLabel}`;
      else if (n.data?.type === 'Module' && !displayLabel.includes('Cluster')) displayLabel = `📁 ${displayLabel}`;

      graph.addNode(n.id, {
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
        size: 8 + Math.min(n.data?.blast_radius || 0, 15),
        color: color,
        label: displayLabel,
        data: n.data,
        zIndex: 0
      });
    });

    (graphData.edges || []).forEach((e: any) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
        graph.addEdge(e.source, e.target, { size: 1, color: 'rgba(61,68,77,0.3)', type: 'curved' });
      }
    });

    forceAtlas2.assign(graph, {
      iterations: 200,
      settings: { ...forceAtlas2.inferSettings(graph), adjustSizes: true, scalingRatio: 30 }
    });
  };

  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    if (graphRef.current.order === 0) syncGraphData();

    if (!sigmaRef.current) {
      const sigma = new Sigma(graphRef.current, containerRef.current, {
        defaultNodeType: 'circle',
        defaultEdgeType: 'curved',
        edgeProgramClasses: { curved: EdgeCurveProgram },
        labelFont: "'JetBrains Mono', monospace",
        labelColor: { color: '#8b949e' },
        labelSize: 11,
        allowInvalidContainer: true,
        renderLabels: true,
        zIndex: true
      });

      sigmaRef.current = sigma;

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // CLEAN ROOM INTERACTION LOGIC
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      let draggedNode: string | null = null;

      sigma.on("downNode", (e) => {
        draggedNode = e.node;
        graphRef.current.setNodeAttribute(draggedNode, "zIndex", 10);
        
        // KILL SIGMA'S CAMERA IMMEDIATELY
        sigma.getMouseCaptor().enabled = false;
        
        // STOP propagation to prevent camera from starting a pan
        if (e.event && e.event.originalEvent) {
          e.event.originalEvent.stopPropagation();
          e.event.originalEvent.stopImmediatePropagation();
        }
      });

      const onMouseMove = (e: MouseEvent) => {
        if (!draggedNode || !containerRef.current) return;
        
        const rect = containerRef.current.getBoundingClientRect();
        const pos = sigma.viewportToGraph({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });

        graphRef.current.setNodeAttribute(draggedNode, "x", pos.x);
        graphRef.current.setNodeAttribute(draggedNode, "y", pos.y);
        
        // Force refresh for smooth movement
        sigma.refresh();
      };

      const onMouseUp = () => {
        if (draggedNode) {
          graphRef.current.setNodeAttribute(draggedNode, "zIndex", 0);
          draggedNode = null;
          // Re-enable camera only after interaction is finished
          sigma.getMouseCaptor().enabled = true;
          sigma.refresh();
        }
      };

      // Use window listeners for "capture-all" dragging
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);

      sigma.on("clickNode", (e) => setSelectedNodeId(e.node));
      sigma.on("clickStage", () => setSelectedNodeId(null));
      sigma.on("enterNode", (e) => {
        setHoveredNode(e.node);
        if (containerRef.current) containerRef.current.style.cursor = "pointer";
      });
      sigma.on("leaveNode", () => {
        setHoveredNode(null);
        if (containerRef.current) containerRef.current.style.cursor = "grab";
      });

      sigma.getCamera().animatedZoom({ factor: 1.2, duration: 600 });

      return () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
        sigma.kill();
        sigmaRef.current = null;
      };
    } else {
      syncGraphData();
      sigmaRef.current.refresh();
    }
  }, [graphData]);

  // WebGL Reducers for Highlighting
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const graph = graphRef.current;

    sigma.setSetting("nodeReducer", (node, data) => {
      const res: any = { ...data };
      const matchesSearch = !search || (res.label && res.label.toLowerCase().includes(search.toLowerCase()));
      if (!matchesSearch) { res.hidden = true; res.label = ""; }

      if (hoveredNode) {
        if (node === hoveredNode || graph.areNeighbors(hoveredNode, node)) {
          res.zIndex = 1;
        } else {
          res.label = "";
          res.color = "#21262d";
          res.opacity = 0.2;
        }
      }
      return res;
    });

    sigma.setSetting("edgeReducer", (edge, data) => {
      const res: any = { ...data };
      if (hoveredNode && !graph.hasExtremity(edge, hoveredNode)) res.hidden = true;
      return res;
    });

    sigma.refresh();
  }, [search, hoveredNode]);

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
          <span style={{ color: '#f85149', fontSize: 10 }}>● Critical</span>
          <span style={{ color: '#d29922', fontSize: 10 }}>● Warning</span>
          <span style={{ color: '#3fb950', fontSize: 10 }}>● Safe</span>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', minHeight: 0, userSelect: 'none', overflow: 'hidden' }}>
        <div 
          ref={containerRef} 
          style={{ width: '100%', height: '100%', background: '#0d1117', touchAction: 'none' }} 
        />
        
        {selectedNodeData && (
          <div style={{ position: 'absolute', top: 0, right: 0, width: 320, height: '100%', background: 'rgba(22, 27, 34, 0.98)', borderLeft: '1px solid #30363d', padding: 24, zIndex: 20, boxShadow: '-8px 0 30px rgba(0,0,0,0.6)', overflowY: 'auto', fontFamily: "'JetBrains Mono', monospace", userSelect: 'text' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <span style={{ color: '#e6edf3', fontSize: 14, fontWeight: 'bold' }}>{selectedNodeData.data?.label || selectedNodeId}</span>
              <button onClick={() => setSelectedNodeId(null)} style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: 18 }}>✕</button>
            </div>
            <div style={{ fontSize: 11, color: '#8b949e' }}>
               <p>File: <span style={{ color: '#c9d1d9' }}>{selectedNodeData.data?.file}</span></p>
               <p>Type: <span style={{ color: '#58a6ff' }}>{selectedNodeData.data?.type}</span></p>
               <p>Blast: <span style={{ color: '#f85149' }}>{selectedNodeData.data?.blast_radius}</span></p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CIGraph;
