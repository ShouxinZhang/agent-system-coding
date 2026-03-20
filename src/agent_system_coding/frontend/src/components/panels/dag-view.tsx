import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  type NodeTypes,
  type NodeProps,
  Position,
  Handle,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import './dag-view.css'

// ===== Types =====
type NodeStatus = 'pending' | 'running' | 'accepted' | 'blocked'
type NodeKind = 'start' | 'end' | 'normal'

interface DagNodeData {
  label: string
  status: NodeStatus
  kind: NodeKind
  [key: string]: unknown
}

// ===== Mock data: only logical relationships =====
const RAW_NODES: { id: string; label: string; kind: NodeKind; status: NodeStatus }[] = [
  { id: 'start',            label: 'START',            kind: 'start',  status: 'accepted' },
  { id: 'plan',             label: 'plan',             kind: 'normal', status: 'accepted' },
  { id: 'dispatch',         label: 'dispatch',         kind: 'normal', status: 'accepted' },
  { id: 'execute_task_1',   label: 'execute_task_1',   kind: 'normal', status: 'accepted' },
  { id: 'execute_task_2',   label: 'execute_task_2',   kind: 'normal', status: 'running'  },
  { id: 'execute_task_3',   label: 'execute_task_3',   kind: 'normal', status: 'pending'  },
  { id: 'dispatch_reviews', label: 'dispatch_reviews', kind: 'normal', status: 'pending'  },
  { id: 'review_task_1',    label: 'review_task_1',    kind: 'normal', status: 'pending'  },
  { id: 'review_task_2',    label: 'review_task_2',    kind: 'normal', status: 'pending'  },
  { id: 'update',           label: 'update',           kind: 'normal', status: 'pending'  },
  { id: 'finalize',         label: 'finalize',         kind: 'normal', status: 'pending'  },
  { id: 'end',              label: 'END',              kind: 'end',    status: 'pending'  },
]

const RAW_EDGES: { from: string; to: string; conditional?: boolean }[] = [
  { from: 'start',            to: 'plan' },
  { from: 'plan',             to: 'dispatch' },
  { from: 'dispatch',         to: 'execute_task_1' },
  { from: 'dispatch',         to: 'execute_task_2' },
  { from: 'dispatch',         to: 'execute_task_3' },
  { from: 'dispatch',         to: 'finalize', conditional: true },
  { from: 'execute_task_1',   to: 'dispatch_reviews' },
  { from: 'execute_task_2',   to: 'dispatch_reviews' },
  { from: 'execute_task_3',   to: 'dispatch_reviews' },
  { from: 'dispatch_reviews', to: 'review_task_1' },
  { from: 'dispatch_reviews', to: 'review_task_2' },
  { from: 'review_task_1',    to: 'update' },
  { from: 'review_task_2',    to: 'update' },
  { from: 'update',           to: 'dispatch' },
  { from: 'finalize',         to: 'end' },
]

// ===== Dagre auto-layout =====
const NODE_WIDTH = 150
const NODE_HEIGHT = 40

function layoutWithDagre(
  rawNodes: typeof RAW_NODES,
  rawEdges: typeof RAW_EDGES,
): { nodes: Node<DagNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({
    rankdir: 'TB',
    nodesep: 40,
    ranksep: 60,
    marginx: 30,
    marginy: 30,
  })

  // Add nodes
  rawNodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  })

  // Add edges
  rawEdges.forEach((e) => {
    g.setEdge(e.from, e.to)
  })

  // Run layout
  dagre.layout(g)

  // Convert to React Flow nodes
  const nodes: Node<DagNodeData>[] = rawNodes.map((n) => {
    const pos = g.node(n.id)
    return {
      id: n.id,
      type: 'dagNode',
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      data: {
        label: n.label,
        status: n.status,
        kind: n.kind,
      },
    }
  })

  // Convert to React Flow edges
  const edges: Edge[] = rawEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.from,
    target: e.to,
    type: 'smoothstep',
    animated: !e.conditional && rawNodes.find(n => n.id === e.from)?.status === 'running',
    style: {
      stroke: e.conditional ? '#666' : '#444',
      strokeWidth: 1.5,
      strokeDasharray: e.conditional ? '6 4' : undefined,
    },
    label: e.conditional ? 'cond' : undefined,
    labelStyle: { fill: '#666', fontSize: 10 },
    labelBgStyle: { fill: '#0f0f0f' },
  }))

  return { nodes, edges }
}

// ===== Custom Node Component =====
function DagNode({ data, selected }: NodeProps<Node<DagNodeData>>) {
  const { label, status, kind } = data

  const isCircle = kind === 'start' || kind === 'end'

  return (
    <div className={`dag-node dag-node-${status} ${selected ? 'dag-node-selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="dag-handle" />
      <div className={`dag-node-body ${isCircle ? 'dag-node-circle' : ''}`}>
        <span className="dag-node-label">{label}</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="dag-handle" />
    </div>
  )
}

const nodeTypes: NodeTypes = {
  dagNode: DagNode,
}

// ===== DAG View Component =====
export function DagView() {
  const layout = useMemo(() => layoutWithDagre(RAW_NODES, RAW_EDGES), [])
  const [nodes, , onNodesChange] = useNodesState(layout.nodes)
  const [edges, , onEdgesChange] = useEdgesState(layout.edges)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(prev => prev === node.id ? null : node.id)
  }, [])

  return (
    <div className="panel" style={{ flex: 1, minHeight: 0 }}>
      <div className="panel-header">
        DAG View
        {selectedNode && (
          <span className="dag-selected-hint"> · {selectedNode}</span>
        )}
      </div>
      <div className="dag-flow-wrapper">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            type: 'smoothstep',
          }}
        >
          <Background color="#1a1a1a" gap={20} size={1} />
        </ReactFlow>
      </div>
    </div>
  )
}
