import { forwardRef, HTMLAttributes } from 'react'
import { clsx } from 'clsx'

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number // 0 to 100
  max?: number
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'error'
}

export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, max = 100, showLabel = false, size = 'md', variant = 'default', ...props }, ref) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

    const sizes = {
      sm: 'h-1.5',
      md: 'h-2.5',
      lg: 'h-4',
    }

    const variants = {
      default: 'bg-gradient-to-r from-accent-blue to-accent-purple',
      success: 'bg-green-500',
      warning: 'bg-yellow-500',
      error: 'bg-red-500',
    }

    return (
      <div className={clsx('w-full', className)} {...props} ref={ref}>
        {showLabel && (
          <div className="flex justify-between mb-1">
            <span className="text-sm text-text-secondary">Progress</span>
            <span className="text-sm text-text-primary font-medium">{Math.round(percentage)}%</span>
          </div>
        )}
        <div className={clsx('w-full bg-bg-hover rounded-full overflow-hidden', sizes[size])}>
          <div
            className={clsx('h-full rounded-full transition-all duration-300', variants[variant])}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    )
  }
)

Progress.displayName = 'Progress'

// Processing steps progress
export interface ProcessingStep {
  id: string
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  result?: string
}

export interface ProcessingStepsProps extends HTMLAttributes<HTMLDivElement> {
  steps: ProcessingStep[]
}

export const ProcessingSteps = forwardRef<HTMLDivElement, ProcessingStepsProps>(
  ({ steps, className, ...props }, ref) => {
    return (
      <div ref={ref} className={clsx('space-y-3', className)} {...props}>
        {steps.map((step) => (
          <div key={step.id} className="flex items-center gap-3">
            <div className="flex-shrink-0">
              {step.status === 'completed' && (
                <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
              {step.status === 'in_progress' && (
                <div className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
              )}
              {step.status === 'pending' && (
                <div className="w-5 h-5 border-2 border-border rounded-full" />
              )}
              {step.status === 'error' && (
                <div className="w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className={clsx(
                'text-sm',
                step.status === 'completed' ? 'text-text-primary' :
                step.status === 'in_progress' ? 'text-accent-blue' :
                step.status === 'error' ? 'text-red-400' : 'text-text-muted'
              )}>
                {step.label}
              </p>
              {step.result && step.status === 'completed' && (
                <p className="text-xs text-text-secondary">{step.result}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }
)

ProcessingSteps.displayName = 'ProcessingSteps'
