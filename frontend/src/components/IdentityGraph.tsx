import { useRef, useEffect, useState } from 'react'
import { Network, AlertTriangle } from 'lucide-react'
import type { GraphData, GraphNode, GraphLink } from '../types'

interface Props {
  graphData: GraphData
}

// Colors
const NODE_CURRENT = '#3b82f6'
const NODE_FRAUD   = '#ef4444'
const NODE_NORMAL  = '#475569'
const LINK_COLOR   = '#334155'
const LINK_FRAUD   = '#dc2626'

interface ForceNode extends GraphNode {
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

interface ForceLink {
  source: ForceNode
  target: ForceNode
  link_type: string
}

function useForceGraph(nodes: GraphNode[], links: GraphLink[]) {
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(new Map())

  useEffect(() => {
    if (nodes.length === 0) return

    const WIDTH = 700, HEIGHT = 400
    const forceNodes: ForceNode[] = nodes.map(n => ({
      ...n,
      x: WIDTH / 2 + (Math.random() - 0.5) * 200,
      y: HEIGHT / 2 + (Math.random() - 0.5) * 200,
      vx: 0, vy: 0,
    }))
    const nodeById = new Map(forceNodes.map(n => [n.id, n]))

    const forceLinks: ForceLink[] = links.map(l => ({
      source: nodeById.get(l.source)!,
      target: nodeById.get(l.target)!,
      link_type: l.link_type,
    })).filter(l => l.source && l.target)

    // Simple force simulation
    let frame: number
    const tick = (iter: number) => {
      const alpha = Math.max(0.01, 1 - iter / 150)

      // Repulsion
      for (let i = 0; i < forceNodes.length; i++) {
        for (let j = i + 1; j < forceNodes.length; j++) {
          const a = forceNodes[i], b = forceNodes[j]
          const dx = (b.x ?? 0) - (a.x ?? 0)
          const dy = (b.y ?? 0) - (a.y ?? 0)
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (3000 / (dist * dist)) * alpha
          a.vx! -= (dx / dist) * force
          a.vy! -= (dy / dist) * force
          b.vx! += (dx / dist) * force
          b.vy! += (dy / dist) * force
        }
      }

      // Attraction (links)
      for (const link of forceLinks) {
        const dx = (link.target.x ?? 0) - (link.source.x ?? 0)
        const dy = (link.target.y ?? 0) - (link.source.y ?? 0)
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - 80) * 0.05 * alpha
        link.source.vx! += (dx / dist) * force
        link.source.vy! += (dy / dist) * force
        link.target.vx! -= (dx / dist) * force
        link.target.vy! -= (dy / dist) * force
      }

      // Center gravity
      for (const n of forceNodes) {
        n.vx! += (WIDTH / 2 - (n.x ?? WIDTH / 2)) * 0.01 * alpha
        n.vy! += (HEIGHT / 2 - (n.y ?? HEIGHT / 2)) * 0.01 * alpha
        n.vx! *= 0.7
        n.vy! *= 0.7
        n.x = (n.x ?? WIDTH / 2) + n.vx!
        n.y = (n.y ?? HEIGHT / 2) + n.vy!
        // Clamp
        n.x = Math.max(20, Math.min(WIDTH - 20, n.x))
        n.y = Math.max(20, Math.min(HEIGHT - 20, n.y))
      }

      if (iter % 10 === 0) {
        const map = new Map<string, { x: number; y: number }>()
        forceNodes.forEach(n => map.set(n.id, { x: n.x!, y: n.y! }))
        setPositions(new Map(map))
      }

      if (iter < 150) {
        frame = requestAnimationFrame(() => tick(iter + 1))
      }
    }

    frame = requestAnimationFrame(() => tick(0))
    return () => cancelAnimationFrame(frame)
  }, [nodes, links])

  return positions
}

export default function IdentityGraph({ graphData }: Props) {
  const { nodes, links, rings } = graphData
  const [tooltip, setTooltip] = useState<{ node: GraphNode; x: number; y: number } | null>(null)
  const positions = useForceGraph(nodes, links)
  const svgRef = useRef<SVGSVGElement>(null)

  const ringMembers = new Set(rings.flat())

  if (nodes.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-[#151821] p-8 text-center text-slate-500 text-sm">
        <Network size={28} className="mx-auto mb-2 text-slate-600" />
        No graph data available for this assessment.
      </div>
    )
  }

  const WIDTH = 700, HEIGHT = 400

  const linkColor = (l: GraphLink) => {
    const sInRing = ringMembers.has(l.source)
    const tInRing = ringMembers.has(l.target)
    return sInRing && tInRing ? LINK_FRAUD : LINK_COLOR
  }

  const nodeColor = (n: GraphNode) => {
    if (n.is_current) return NODE_CURRENT
    if (n.in_fraud_ring || ringMembers.has(n.id)) return NODE_FRAUD
    return NODE_NORMAL
  }

  return (
    <div className="rounded-xl border border-slate-700/50 bg-[#151821] overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-3">
        <Network size={14} className="text-blue-400" />
        <span className="text-sm font-semibold text-slate-300">Identity Graph</span>
        <span className="text-xs text-slate-500">{nodes.length} nodes · {links.length} edges</span>
        {rings.length > 0 && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-red-400 font-medium">
            <AlertTriangle size={11} />
            {rings.length} fraud ring{rings.length > 1 ? 's' : ''} detected
          </span>
        )}
      </div>

      <div className="relative" style={{ height: HEIGHT }}>
        <svg ref={svgRef} width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="absolute inset-0"
          onMouseLeave={() => setTooltip(null)}
        >
          {/* Links */}
          {links.map((link, i) => {
            const s = positions.get(link.source)
            const t = positions.get(link.target)
            if (!s || !t) return null
            return (
              <line key={i}
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={linkColor(link)} strokeWidth={1.5}
                strokeOpacity={0.6}
              />
            )
          })}

          {/* Link type labels */}
          {links.slice(0, 8).map((link, i) => {
            const s = positions.get(link.source)
            const t = positions.get(link.target)
            if (!s || !t) return null
            const mx = (s.x + t.x) / 2
            const my = (s.y + t.y) / 2
            return (
              <text key={`lt-${i}`} x={mx} y={my} textAnchor="middle"
                fontSize={8} fill="#475569"
                style={{ pointerEvents: 'none', userSelect: 'none' }}>
                {link.link_type.replace('SHARED_', '')}
              </text>
            )
          })}

          {/* Nodes */}
          {nodes.map(node => {
            const pos = positions.get(node.id)
            if (!pos) return null
            const color = nodeColor(node)
            const r = node.is_current ? 12 : 8

            return (
              <g key={node.id}
                onMouseEnter={(e) => {
                  const rect = svgRef.current?.getBoundingClientRect()
                  if (rect) setTooltip({ node, x: pos.x, y: pos.y - r - 10 })
                }}
                style={{ cursor: 'pointer' }}
              >
                {(node.in_fraud_ring || ringMembers.has(node.id)) && (
                  <circle cx={pos.x} cy={pos.y} r={r + 6}
                    fill="none" stroke="#ef4444" strokeWidth={1}
                    strokeOpacity={0.35}
                    strokeDasharray="3,2"
                  />
                )}
                <circle cx={pos.x} cy={pos.y} r={r}
                  fill={color} fillOpacity={0.9}
                  stroke={node.is_current ? '#93c5fd' : color}
                  strokeWidth={node.is_current ? 2 : 1}
                />
                {node.is_current && (
                  <circle cx={pos.x} cy={pos.y} r={r + 10}
                    fill="none" stroke="#3b82f6" strokeWidth={1.5}
                    strokeOpacity={0.3}
                  />
                )}
                <text x={pos.x} y={pos.y + r + 12}
                  textAnchor="middle" fontSize={9} fill="#94a3b8"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}>
                  {node.label.split(' ')[0]}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Tooltip */}
        {tooltip && (() => {
          const pos = positions.get(tooltip.node.id)
          if (!pos) return null
          const pct = pos.x / WIDTH
          return (
            <div
              className="absolute z-10 bg-[#0f1117] border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl pointer-events-none"
              style={{
                left: `${pct < 0.7 ? pos.x + 15 : pos.x - 180}px`,
                top: `${pos.y - 10}px`,
              }}
            >
              <p className="font-semibold text-white mb-1">{tooltip.node.label}</p>
              {tooltip.node.is_current && <p className="text-blue-400">← Current applicant</p>}
              {(tooltip.node.in_fraud_ring || ringMembers.has(tooltip.node.id)) && (
                <p className="text-red-400">⚠ Fraud ring member</p>
              )}
              <p className="text-slate-500 font-mono mt-1">{tooltip.node.id.slice(0, 12)}…</p>
            </div>
          )
        })()}
      </div>

      {/* Legend */}
      <div className="px-5 py-3 border-t border-slate-800 flex items-center gap-6 text-xs text-slate-400">
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-blue-500" />Current applicant</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-red-500" />Fraud ring member</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-slate-500" />Prior applicant</div>
        <div className="flex items-center gap-1.5"><span className="w-4 h-px bg-red-700" />Ring edge</div>
      </div>
    </div>
  )
}
