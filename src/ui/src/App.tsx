import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { InboxView } from './components/InboxView'
import { VideoQueue } from './components/VideoQueue'
import { useIsMobile } from './hooks/useIsMobile'
import { useVideos } from './hooks/useVideos'

export function App() {
  const isMobile = useIsMobile()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { videos, loading, refresh } = useVideos()

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--c-bg)' }}>

      {/* Desktop sidebar */}
      {!isMobile && (
        <div style={{ width: 252, flexShrink: 0, height: '100vh', overflowY: 'auto', boxShadow: '2px 0 12px rgba(0,0,0,0.04)' }}>
          <Sidebar videos={videos} onRefresh={refresh} />
        </div>
      )}

      {/* Mobile sidebar overlay */}
      {isMobile && sidebarOpen && (
        <>
          <div
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.25)',
              zIndex: 40,
              animation: 'fade-in 0.18s ease-out',
            }}
          />
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: 280,
            height: '100vh',
            zIndex: 50,
            overflowY: 'auto',
            boxShadow: '4px 0 24px rgba(0,0,0,0.12)',
          }}>
            <Sidebar onClose={() => setSidebarOpen(false)} videos={videos} onRefresh={refresh} />
          </div>
        </>
      )}

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>

        {/* Mobile top bar */}
        {isMobile && (
          <div style={{
            height: 52,
            background: 'var(--c-sidebar)',
            borderBottom: '1px solid var(--c-border)',
            borderLeft: '3px solid var(--c-gold)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 16px',
            flexShrink: 0,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              fontWeight: 700,
              letterSpacing: '0.2em',
              color: 'var(--c-gold)',
            }}>
              SHORTS BOT
            </span>
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Open sidebar"
              style={{
                background: 'none',
                border: '1px solid var(--c-border)',
                color: 'var(--c-text2)',
                borderRadius: 5,
                width: 44,
                height: 44,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                fontSize: '1rem',
              }}
            >
              ☰
            </button>
          </div>
        )}

        {/* Single scrollable main panel */}
        <div style={{ flex: 1, overflowY: 'auto' }}>

          {/* Inbox section */}
          <InboxView videos={videos} onRefresh={refresh} />

          {/* Divider */}
          <div style={{
            margin: '0 16px',
            borderTop: '1px solid var(--c-border)',
          }} />

          {/* Pipeline section */}
          <VideoQueue videos={videos} loading={loading} onRefresh={refresh} />

        </div>
      </div>
    </div>
  )
}
