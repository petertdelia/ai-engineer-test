import { Navbar } from './Navbar'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  children: React.ReactNode
  sidebarVariant?: 'candidate' | 'admin'
}

export function AppShell({ children, sidebarVariant = 'candidate' }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar variant={sidebarVariant} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  )
}
