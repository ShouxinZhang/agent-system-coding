import './header.css'

export function Header() {
  return (
    <header className="app-header">
      <div className="header-left">
        <span className="header-logo">◆</span>
        <h1 className="header-title">Agent System Coding</h1>
      </div>
      <div className="header-center">
        <div className="run-status">
          <span className="badge badge-running">● Running</span>
          <span className="run-id">RUN-20260315-a8c3</span>
        </div>
      </div>
      <div className="header-right">
        <button className="btn-new-workflow">+ New Workflow</button>
      </div>
    </header>
  )
}
