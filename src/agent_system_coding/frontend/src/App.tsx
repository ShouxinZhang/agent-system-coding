import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { WorkflowDetailPage } from './pages/workflow-detail'
import { PreviewGallery } from './pages/preview-gallery'
import { PreviewShell } from './pages/preview-shell'
import { DagView } from './components/panels/dag-view'
import { TaskList } from './components/panels/task-list'
import { ChatStream } from './components/panels/chat-stream'
import { NodeContextInspector } from './components/panels/node-context-inspector'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ===== 主页面 ===== */}
        <Route path="/" element={<WorkflowDetailPage />} />

        {/* ===== 组件预览系统 ===== */}
        <Route path="/preview" element={<PreviewGallery />} />
        <Route path="/preview/dag-view" element={
          <PreviewShell name="DAG View">
            <DagView />
          </PreviewShell>
        } />
        <Route path="/preview/task-list" element={
          <PreviewShell name="Task List">
            <TaskList />
          </PreviewShell>
        } />
        <Route path="/preview/chat-stream" element={
          <PreviewShell name="Chat Stream">
            <ChatStream />
          </PreviewShell>
        } />
        <Route path="/preview/inspector" element={
          <PreviewShell name="Node Context Inspector">
            <NodeContextInspector />
          </PreviewShell>
        } />
      </Routes>
    </BrowserRouter>
  )
}

export default App
