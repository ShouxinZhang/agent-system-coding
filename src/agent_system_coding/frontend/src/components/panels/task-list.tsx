export function TaskList() {
  return (
    <div className="panel" style={{ flex: 1, minHeight: 0 }}>
      <div className="panel-header">Task List</div>
      <div className="panel-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>☰</div>
          <div style={{ fontSize: 12 }}>Tasks</div>
          <div style={{ fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            status · retries · dependencies
          </div>
        </div>
      </div>
    </div>
  )
}
