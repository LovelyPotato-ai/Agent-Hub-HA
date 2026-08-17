/**
 * WorkflowsTab.tsx — Workflow CRUD with React Flow DAG editor
 * Lists workflows, allows creating/editing with a visual node canvas.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
  type Node, type Edge, type Connection,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  createWorkflow, deleteWorkflow, listAgents, listWorkflows, updateWorkflow,
  type AgentDef, type TaskDef, type WorkflowCreate, type WorkflowDef,
} from '../api/aiHubClient'

// ---------------------------------------------------------------------------
// Custom task node
// ---------------------------------------------------------------------------

interface TaskNodeData {
  label: string
  agentName: string
  description: string
  [key: string]: unknown
}

const TaskNode: FC<{ data: TaskNodeData }> = ({ data }) => (
  <div className="rounded-lg border-2 border-ha-border bg-ha-surface px-4 py-3 min-w-[180px] max-w-[220px] shadow-lg">
    <div className="text-sm font-semibold text-ha-text truncate">{data.label}</div>
    <div className="text-xs text-ha-blue mt-0.5 truncate">{data.agentName}</div>
    {data.description && (
      <div className="text-xs text-ha-muted mt-1 line-clamp-2">{data.description}</div>
    )}
  </div>
)

const nodeTypes: NodeTypes = { task: TaskNode }

// ---------------------------------------------------------------------------
// Helpers: convert workflow tasks ↔ React Flow nodes/edges
// ---------------------------------------------------------------------------

function tasksToFlow(tasks: TaskDef[], agents: AgentDef[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = tasks.map((t, i) => ({
    id: t.id,
    type: 'task',
    position: t.position ?? { x: i * 250, y: 200 },
    data: {
      label: t.name,
      agentName: agents.find(a => a.id === t.agent_id)?.name ?? 'Unknown Agent',
      description: t.description,
      taskDef: t,
    },
  }))
  const edges: Edge[] = []
  tasks.forEach(t => {
    t.depends_on.forEach(depId => {
      edges.push({
        id: `${depId}->${t.id}`,
        source: depId,
        target: t.id,
        animated: true,
        style: { stroke: '#03a9f4' },
      })
    })
  })
  return { nodes, edges }
}

function flowToTasks(nodes: Node[], edges: Edge[], originalTasks: TaskDef[]): TaskDef[] {
  const taskMap = new Map(originalTasks.map(t => [t.id, t]))
  const dependsOnMap: Map<string, string[]> = new Map()
  edges.forEach(e => {
    const deps = dependsOnMap.get(e.target) ?? []
    deps.push(e.source)
    dependsOnMap.set(e.target, deps)
  })
  return nodes.map(node => {
    const original = taskMap.get(node.id)
    return {
      ...(original ?? {
        id: node.id,
        name: (node.data as TaskNodeData).label,
        description: (node.data as TaskNodeData).description ?? '',
        agent_id: '',
        expected_output: 'Task output',
        allow_delegation: false,
      }),
      depends_on: dependsOnMap.get(node.id) ?? [],
      position: node.position,
    } as TaskDef
  })
}

// ---------------------------------------------------------------------------
// Task editor panel (sidebar)
// ---------------------------------------------------------------------------

interface TaskEditorProps {
  task: TaskDef
  agents: AgentDef[]
  onChange: (updated: TaskDef) => void
  onDelete: () => void
}

const TaskEditor: FC<TaskEditorProps> = ({ task, agents, onChange, onDelete }) => {
  const inputCls = 'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue'
  return (
    <div className="flex flex-col gap-3 p-4 border-l border-ha-border bg-ha-surface h-full overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ha-text">Edit Task</h3>
        <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300">Delete</button>
      </div>
      <div>
        <label className="block text-xs text-ha-muted mb-1">Task Name</label>
        <input className={inputCls} value={task.name} onChange={e => onChange({ ...task, name: e.target.value })} />
      </div>
      <div>
        <label className="block text-xs text-ha-muted mb-1">Assigned Agent</label>
        <select className={inputCls} value={task.agent_id} onChange={e => onChange({ ...task, agent_id: e.target.value })}>
          <option value="">— Select agent —</option>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs text-ha-muted mb-1">Description <span className="text-ha-blue">{'{prompt}'}</span> = user input</label>
        <textarea className={inputCls} rows={4} value={task.description} onChange={e => onChange({ ...task, description: e.target.value })} />
      </div>
      <div>
        <label className="block text-xs text-ha-muted mb-1">Expected Output</label>
        <textarea className={inputCls} rows={2} value={task.expected_output} onChange={e => onChange({ ...task, expected_output: e.target.value })} />
      </div>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={task.allow_delegation} onChange={e => onChange({ ...task, allow_delegation: e.target.checked })} className="w-4 h-4" />
        <span className="text-xs text-ha-text">Allow delegation</span>
      </label>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Workflow editor (canvas + sidebar)
// ---------------------------------------------------------------------------

interface WorkflowEditorProps {
  initial?: WorkflowDef | null
  agents: AgentDef[]
  onSave: (wf: WorkflowDef) => void
  onCancel: () => void
}

const WorkflowEditor: FC<WorkflowEditorProps> = ({ initial, agents, onSave, onCancel }) => {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [process, setProcess] = useState<'sequential' | 'hierarchical' | 'dag'>(initial?.process ?? 'sequential')
  const [tasks, setTasks] = useState<TaskDef[]>(initial?.tasks ?? [])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { nodes: initNodes, edges: initEdges } = tasksToFlow(tasks, agents)
  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  const onConnect = useCallback(
    (params: Connection) => setEdges(eds => addEdge({ ...params, animated: true, style: { stroke: '#03a9f4' } }, eds)),
    [setEdges]
  )

  const addTask = () => {
    const id = `task-${Date.now()}`
    const newTask: TaskDef = {
      id, name: 'New Task', description: '{prompt}', agent_id: '',
      expected_output: 'Task output', depends_on: [], allow_delegation: false,
      position: { x: nodes.length * 250 + 50, y: 200 },
    }
    setTasks(prev => [...prev, newTask])
    setNodes(prev => [...prev, {
      id, type: 'task',
      position: newTask.position,
      data: { label: newTask.name, agentName: '— Select agent —', description: newTask.description, taskDef: newTask },
    }])
    setSelectedTaskId(id)
  }

  const updateTask = (updated: TaskDef) => {
    setTasks(prev => prev.map(t => t.id === updated.id ? updated : t))
    setNodes(prev => prev.map(n => n.id === updated.id ? {
      ...n,
      data: {
        ...n.data,
        label: updated.name,
        agentName: agents.find(a => a.id === updated.agent_id)?.name ?? '— Select agent —',
        description: updated.description,
        taskDef: updated,
      },
    } : n))
  }

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id))
    setNodes(prev => prev.filter(n => n.id !== id))
    setEdges(prev => prev.filter(e => e.source !== id && e.target !== id))
    setSelectedTaskId(null)
  }

  const handleSave = async () => {
    if (!name.trim()) { setError('Workflow name is required'); return }
    setSaving(true)
    setError(null)
    try {
      const currentTasks = flowToTasks(nodes, edges, tasks)
      const payload: WorkflowCreate = { name, description, process, manager_llm: null, tasks: currentTasks }
      let saved: WorkflowDef
      if (initial) {
        saved = await updateWorkflow(initial.id, payload)
      } else {
        saved = await createWorkflow(payload)
      }
      onSave(saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const selectedTask = tasks.find(t => t.id === selectedTaskId) ?? null

  return (
    <div className="flex flex-col gap-4">
      {error && <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-xs text-ha-muted mb-1">Workflow Name *</label>
          <input className="w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
            value={name} onChange={e => setName(e.target.value)} placeholder="My Workflow" />
        </div>
        <div>
          <label className="block text-xs text-ha-muted mb-1">Process</label>
          <select className="w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
            value={process} onChange={e => setProcess(e.target.value as typeof process)}>
            <option value="sequential">Sequential — tasks run in order</option>
            <option value="dag">DAG — parallel independent branches</option>
            <option value="hierarchical">Hierarchical — manager LLM delegates</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-ha-muted mb-1">Description</label>
          <input className="w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
            value={description} onChange={e => setDescription(e.target.value)} placeholder="What this workflow does…" />
        </div>
      </div>

      {/* DAG Canvas */}
      <div className="flex gap-0 border border-ha-border rounded-xl overflow-hidden" style={{ height: 420 }}>
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedTaskId(node.id)}
            nodeTypes={nodeTypes}
            fitView
            style={{ background: '#111827' }}
          >
            <Background color="#374151" gap={20} />
            <Controls />
            <MiniMap nodeColor="#1f2937" maskColor="rgba(17,24,39,0.7)" />
          </ReactFlow>
          <button
            onClick={addTask}
            className="absolute top-3 left-3 z-10 rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-3 py-1.5 text-xs font-semibold shadow transition-colors"
          >
            + Add Task
          </button>
          <div className="absolute bottom-3 left-3 z-10 text-xs text-ha-muted bg-ha-surface/80 rounded px-2 py-1">
            Drag nodes to reposition · Connect nodes to set dependencies · Click node to edit
          </div>
        </div>
        {selectedTask && (
          <div className="w-72 flex-shrink-0">
            <TaskEditor
              task={selectedTask}
              agents={agents}
              onChange={updateTask}
              onDelete={() => deleteTask(selectedTask.id)}
            />
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button onClick={handleSave} disabled={saving}
          className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-5 py-2 text-sm font-semibold disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : initial ? 'Update Workflow' : 'Create Workflow'}
        </button>
        <button onClick={onCancel}
          className="rounded-lg border border-ha-border px-5 py-2 text-sm text-ha-muted hover:text-ha-text transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Workflow card
// ---------------------------------------------------------------------------

interface WorkflowCardProps {
  workflow: WorkflowDef
  agents: AgentDef[]
  onEdit: () => void
  onDelete: () => void
}

const PROCESS_LABELS = { sequential: 'Sequential', hierarchical: 'Hierarchical', dag: 'DAG' }

const WorkflowCard: FC<WorkflowCardProps> = ({ workflow, agents, onEdit, onDelete }) => (
  <div className="card flex flex-col gap-2">
    <div className="flex items-start justify-between gap-2">
      <div>
        <h3 className="text-sm font-semibold text-ha-text">{workflow.name}</h3>
        <p className="text-xs text-ha-blue mt-0.5">{PROCESS_LABELS[workflow.process]} · {workflow.tasks.length} task{workflow.tasks.length !== 1 ? 's' : ''}</p>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button onClick={onEdit} className="text-xs text-ha-muted hover:text-ha-text px-2 py-1 rounded border border-ha-border hover:border-ha-blue/50 transition-colors">Edit</button>
        <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-800/50 hover:border-red-600 transition-colors">Delete</button>
      </div>
    </div>
    {workflow.description && <p className="text-xs text-ha-muted line-clamp-2">{workflow.description}</p>}
    <div className="flex flex-wrap gap-1 mt-1">
      {workflow.tasks.map(t => {
        const agentName = agents.find(a => a.id === t.agent_id)?.name ?? '?'
        return (
          <span key={t.id} className="rounded-full bg-ha-border/40 px-2 py-0.5 text-xs text-ha-muted" title={agentName}>
            {t.name}
          </span>
        )
      })}
    </div>
  </div>
)

// ---------------------------------------------------------------------------
// Main tab
// ---------------------------------------------------------------------------

export const WorkflowsTab: FC = () => {
  const [workflows, setWorkflows] = useState<WorkflowDef[]>([])
  const [agents, setAgents] = useState<AgentDef[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<WorkflowDef | null | 'new'>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [w, a] = await Promise.all([listWorkflows(), listAgents()])
      setWorkflows(w)
      setAgents(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = (saved: WorkflowDef) => {
    setWorkflows(prev => {
      const idx = prev.findIndex(w => w.id === saved.id)
      return idx >= 0 ? prev.map((w, i) => i === idx ? saved : w) : [...prev, saved]
    })
    setEditing(null)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this workflow?')) return
    try {
      await deleteWorkflow(id)
      setWorkflows(prev => prev.filter(w => w.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-ha-muted gap-3">
      <svg className="w-5 h-5 animate-spin text-ha-blue" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      Loading workflows…
    </div>
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ha-text">Workflows</h2>
          <p className="text-sm text-ha-muted mt-0.5">Build multi-agent workflows as visual DAGs. Connect tasks to define execution order.</p>
        </div>
        {!editing && (
          <button onClick={() => setEditing('new')}
            className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-4 py-2 text-sm font-semibold transition-colors">
            + New Workflow
          </button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-700 bg-red-900/20 px-4 py-3 text-sm text-red-300">{error}</div>}

      {editing && (
        <div className="card">
          <h3 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">
            {editing === 'new' ? 'New Workflow' : `Edit: ${(editing as WorkflowDef).name}`}
          </h3>
          <WorkflowEditor
            initial={editing === 'new' ? null : editing as WorkflowDef}
            agents={agents}
            onSave={handleSave}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      {workflows.length === 0 && !editing ? (
        <div className="card text-center py-12 text-ha-muted">
          <p className="text-sm">No workflows yet. Create your first workflow above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {workflows.map(wf => (
            <WorkflowCard
              key={wf.id}
              workflow={wf}
              agents={agents}
              onEdit={() => setEditing(wf)}
              onDelete={() => handleDelete(wf.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
