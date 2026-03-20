export function ChatStream() {
  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel-header">
        Chat Stream
        <span style={{ float: 'right', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
          real-time agent ↔ LLM conversation
        </span>
      </div>
      <div className="panel-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>💬</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Agent Chat Stream</div>
          <div style={{ fontSize: 12, marginTop: 6, maxWidth: 280, lineHeight: 1.6 }}>
            prompt sent → response received → next node
          </div>
          <div style={{ fontSize: 11, marginTop: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            每个节点的 Prompt / Response 对话将按时间顺序实时滚动展示
          </div>
        </div>
      </div>
    </div>
  )
}
