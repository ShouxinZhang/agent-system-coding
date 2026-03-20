import { Header } from '../components/layout/header'
import { DagView } from '../components/panels/dag-view'
import { TaskList } from '../components/panels/task-list'
import { ChatStream } from '../components/panels/chat-stream'
import { NodeContextInspector } from '../components/panels/node-context-inspector'
import './workflow-detail.css'

export function WorkflowDetailPage() {
  return (
    <div className="workflow-detail">
      <Header />
      <main className="workspace">
        {/* Left Column: DAG + Task List */}
        <aside className="col-left">
          <DagView />
          <TaskList />
        </aside>

        {/* Center Column: Chat Stream */}
        <section className="col-center">
          <ChatStream />
        </section>

        {/* Right Column: Node Context Inspector */}
        <aside className="col-right">
          <NodeContextInspector />
        </aside>
      </main>
    </div>
  )
}
