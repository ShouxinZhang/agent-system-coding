import { Link } from 'react-router-dom'
import './preview-gallery.css'

const panels = [
  { name: 'DAG View', path: '/preview/dag-view', icon: '⬡', desc: 'workflow graph · parallel swim lanes' },
  { name: 'Task List', path: '/preview/task-list', icon: '☰', desc: 'status · retries · dependencies' },
  { name: 'Chat Stream', path: '/preview/chat-stream', icon: '💬', desc: 'agent ↔ LLM conversation' },
  { name: 'Node Inspector', path: '/preview/inspector', icon: '🔍', desc: 'Input · Output · Prompt · Response' },
]

export function PreviewGallery() {
  return (
    <div className="preview-gallery">
      <header className="preview-header">
        <h1>📦 Component Preview Gallery</h1>
        <Link to="/" className="back-link">← 返回完整布局</Link>
      </header>
      <div className="preview-grid">
        {panels.map((p) => (
          <Link key={p.path} to={p.path} className="preview-card">
            <div className="preview-icon">{p.icon}</div>
            <div className="preview-name">{p.name}</div>
            <div className="preview-desc">{p.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
