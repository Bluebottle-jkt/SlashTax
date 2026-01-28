'use client';

import { useEffect, useRef, useCallback, useMemo } from 'react';
import dynamic from 'next/dynamic';
import type { GraphData, GraphNode } from '@/types';

// Dynamically import force-graph to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), { ssr: false });

interface GraphVisualizationProps {
  data: GraphData;
  mode?: '2d' | '3d';
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
  width?: number;
  height?: number;
}

const NODE_COLORS: Record<string, string> = {
  Person: '#ef4444',
  Post: '#3b82f6',
  Location: '#22c55e',
  Account: '#a855f7',
  Hashtag: '#f97316',
};

const NODE_SIZES: Record<string, number> = {
  Person: 8,
  Post: 6,
  Location: 7,
  Account: 7,
  Hashtag: 5,
};

export default function GraphVisualization({
  data,
  mode = '2d',
  onNodeClick,
  onNodeHover,
  width,
  height,
}: GraphVisualizationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);

  // Transform data for force-graph format
  const graphData = useMemo(() => {
    const nodeMap = new Map<string, GraphNode>();
    data.nodes.forEach((node) => nodeMap.set(node.id, node));

    return {
      nodes: data.nodes.map((node) => ({
        id: node.id,
        name: node.label,
        type: node.type,
        properties: node.properties,
        val: NODE_SIZES[node.type] || 5,
        color: NODE_COLORS[node.type] || '#888',
      })),
      links: data.edges
        .filter((edge) => nodeMap.has(edge.source) && nodeMap.has(edge.target))
        .map((edge) => ({
          source: edge.source,
          target: edge.target,
          type: edge.type,
        })),
    };
  }, [data]);

  // Handle node click
  const handleNodeClick = useCallback(
    (node: any) => {
      if (onNodeClick) {
        onNodeClick({
          id: node.id,
          label: node.name,
          type: node.type,
          properties: node.properties,
        });
      }

      // Zoom to node
      if (fgRef.current && mode === '2d') {
        fgRef.current.centerAt(node.x, node.y, 1000);
        fgRef.current.zoom(3, 1000);
      }
    },
    [onNodeClick, mode]
  );

  // Handle node hover
  const handleNodeHover = useCallback(
    (node: any) => {
      if (onNodeHover) {
        onNodeHover(
          node
            ? {
                id: node.id,
                label: node.name,
                type: node.type,
                properties: node.properties,
              }
            : null
        );
      }
    },
    [onNodeHover]
  );

  // Custom node canvas rendering for 2D
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name || node.id;
      const fontSize = 12 / globalScale;
      ctx.font = `${fontSize}px Sans-Serif`;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI);
      ctx.fillStyle = node.color;
      ctx.fill();

      // Draw border
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1 / globalScale;
      ctx.stroke();

      // Draw label if zoomed in enough
      if (globalScale > 1.5) {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#333';
        ctx.fillText(label, node.x, node.y + node.val + fontSize);
      }
    },
    []
  );

  // Link styling
  const linkColor = useCallback((link: any) => {
    const colors: Record<string, string> = {
      APPEARS_IN: '#ef4444',
      POSTED: '#a855f7',
      AT_LOCATION: '#22c55e',
      HAS_HASHTAG: '#f97316',
    };
    return colors[link.type] || '#999';
  }, []);

  // Get dimensions
  const dimensions = useMemo(() => {
    if (width && height) return { width, height };
    return { width: 800, height: 600 };
  }, [width, height]);

  // Update dimensions on resize
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver(() => {
      if (fgRef.current) {
        fgRef.current.width(containerRef.current?.clientWidth);
        fgRef.current.height(containerRef.current?.clientHeight);
      }
    });

    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="graph-container w-full h-full">
      {mode === '2d' ? (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeLabel="name"
          nodeColor="color"
          nodeVal="val"
          linkColor={linkColor}
          linkWidth={1}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          nodeCanvasObject={nodeCanvasObject}
          width={dimensions.width}
          height={dimensions.height}
          cooldownTicks={100}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
        />
      ) : (
        <ForceGraph3D
          ref={fgRef}
          graphData={graphData}
          nodeLabel="name"
          nodeColor="color"
          nodeVal="val"
          linkColor={linkColor}
          linkWidth={1}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          width={dimensions.width}
          height={dimensions.height}
        />
      )}
    </div>
  );
}
