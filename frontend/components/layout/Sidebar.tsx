'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  PlayCircle,
  BookOpen,
  Award,
  Settings,
  Shield,
  BarChart3,
  Users,
  FileText,
  History,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  href: string
  label: string
  icon: React.ElementType
}

const candidateNav: NavItem[] = [
  { href: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/app/start', label: 'Start Assessment', icon: PlayCircle },
  { href: '/app/topics', label: 'Study List', icon: BookOpen },
  { href: '/app/settings', label: 'Settings', icon: Settings },
]

const adminNav: NavItem[] = [
  { href: '/admin/questions', label: 'Questions', icon: FileText },
  { href: '/admin/sessions', label: 'Flagged Sessions', icon: Shield },
  { href: '/admin/pipeline', label: 'Pipeline', icon: Zap },
  { href: '/admin/stats', label: 'Stats', icon: BarChart3 },
  { href: '/admin/users', label: 'Users', icon: Users },
]

interface SidebarProps {
  variant?: 'candidate' | 'admin'
}

export function Sidebar({ variant = 'candidate' }: SidebarProps) {
  const pathname = usePathname()
  const items = variant === 'admin' ? adminNav : candidateNav

  return (
    <aside className="w-56 shrink-0 border-r bg-background">
      <nav className="flex flex-col gap-1 p-3">
        {items.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
              pathname.startsWith(href)
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
