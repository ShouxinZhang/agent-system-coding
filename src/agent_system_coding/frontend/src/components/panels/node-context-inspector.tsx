export function NodeContextInspector() {
  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">Node Context Inspector</div>
      <div className="panel-body">
        {/* Tab bar */}
        <div style={{
          display: 'flex',
          gap: 0,
          borderBottom: '1px solid var(--border)',
          marginBottom: 12,
          marginTop: -4,
        }}>
          {['Input', 'Output', 'Prompt', 'Response'].map((tab, i) => (
            <button
              key={tab}
              style={{
                background: i === 2 ? 'var(--bg-panel-hover)' : 'transparent',
                border: 'none',
                borderBottom: i === 2 ? '2px solid var(--accent-purple)' : '2px solid transparent',
                color: i === 2 ? 'var(--text-primary)' : 'var(--text-muted)',
                padding: '8px 16px',
                fontSize: 12,
                fontWeight: i === 2 ? 600 : 400,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Empty state */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: 'calc(100% - 50px)',
        }}>
          <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>🔍</div>
            <div style={{ fontSize: 12 }}>Click a node or chat message to inspect</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>
              Input · Output · Prompt · Response
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
