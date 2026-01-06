'use client'

import { createContext, useContext, useState, HTMLAttributes, forwardRef, ButtonHTMLAttributes } from 'react'
import { clsx } from 'clsx'

// Tab context
interface TabsContextValue {
  activeTab: string
  setActiveTab: (tab: string) => void
}

const TabsContext = createContext<TabsContextValue | null>(null)

function useTabsContext() {
  const context = useContext(TabsContext)
  if (!context) {
    throw new Error('Tab components must be used within a Tabs component')
  }
  return context
}

// Tabs root component
export interface TabsProps extends HTMLAttributes<HTMLDivElement> {
  defaultTab: string
  onTabChange?: (tab: string) => void
}

export const Tabs = forwardRef<HTMLDivElement, TabsProps>(
  ({ children, defaultTab, onTabChange, className, ...props }, ref) => {
    const [activeTab, setActiveTab] = useState(defaultTab)

    const handleTabChange = (tab: string) => {
      setActiveTab(tab)
      onTabChange?.(tab)
    }

    return (
      <TabsContext.Provider value={{ activeTab, setActiveTab: handleTabChange }}>
        <div ref={ref} className={clsx('', className)} {...props}>
          {children}
        </div>
      </TabsContext.Provider>
    )
  }
)

Tabs.displayName = 'Tabs'

// Tab list component
export interface TabListProps extends HTMLAttributes<HTMLDivElement> {}

export const TabList = forwardRef<HTMLDivElement, TabListProps>(
  ({ children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="tablist"
        className={clsx(
          'flex items-center gap-1 border-b border-border pb-px',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

TabList.displayName = 'TabList'

// Tab trigger component
export interface TabTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
}

export const TabTrigger = forwardRef<HTMLButtonElement, TabTriggerProps>(
  ({ children, value, className, ...props }, ref) => {
    const { activeTab, setActiveTab } = useTabsContext()
    const isActive = activeTab === value

    return (
      <button
        ref={ref}
        role="tab"
        aria-selected={isActive}
        onClick={() => setActiveTab(value)}
        className={clsx(
          'px-4 py-2.5 text-sm font-medium transition-colors relative',
          'focus:outline-none focus:ring-2 focus:ring-accent-blue focus:ring-inset rounded-t-lg',
          isActive
            ? 'text-text-primary'
            : 'text-text-secondary hover:text-text-primary',
          className
        )}
        {...props}
      >
        {children}
        {isActive && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent-blue to-accent-purple" />
        )}
      </button>
    )
  }
)

TabTrigger.displayName = 'TabTrigger'

// Tab content component
export interface TabContentProps extends HTMLAttributes<HTMLDivElement> {
  value: string
}

export const TabContent = forwardRef<HTMLDivElement, TabContentProps>(
  ({ children, value, className, ...props }, ref) => {
    const { activeTab } = useTabsContext()

    if (activeTab !== value) {
      return null
    }

    return (
      <div
        ref={ref}
        role="tabpanel"
        className={clsx('pt-4', className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)

TabContent.displayName = 'TabContent'
