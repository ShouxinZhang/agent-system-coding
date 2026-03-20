import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function PreviewShell({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-root)',
    }}>
      {/* Mini nav bar */}
      <div style={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-panel)',
        flexShrink: 0,
        fontSize: 12,
      }}>
        <Link to="/preview" style={{ color: 'var(--accent-purple)', textDecoration: 'none' }}>
          ← Gallery
        </Link>
        <span style={{ color: 'var(--text-muted)' }}>/</span>
        <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{name}</span>
        <span style={{ marginLeft: 'auto' }}>
          <Link to="/" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: 11 }}>
            Full Layout
          </Link>
        </span>
      </div>
      {/* Component fills remaining space */}
      <div style={{ flex: 1, padding: 12, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {children}
      </div>
    </div>
  )
}
