import { forwardRef, HTMLAttributes } from 'react'
import { clsx } from 'clsx'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'interactive' | 'highlighted'
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'default', padding = 'md', children, ...props }, ref) => {
    const baseStyles = 'bg-bg-card border border-border rounded-xl'

    const variants = {
      default: '',
      interactive: 'hover:border-text-muted/30 transition-colors cursor-pointer',
      highlighted: 'border-accent-blue/50 bg-accent-blue/5',
    }

    const paddings = {
      none: '',
      sm: 'p-3',
      md: 'p-4',
      lg: 'p-6',
    }

    return (
      <div
        ref={ref}
        className={clsx(baseStyles, variants[variant], paddings[padding], className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

// Card Header component
export interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {}

export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx('flex items-center justify-between mb-4', className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)

CardHeader.displayName = 'CardHeader'

// Card Title component
export interface CardTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  as?: 'h1' | 'h2' | 'h3' | 'h4'
}

export const CardTitle = forwardRef<HTMLHeadingElement, CardTitleProps>(
  ({ className, as: Component = 'h3', children, ...props }, ref) => {
    return (
      <Component
        ref={ref}
        className={clsx('text-lg font-semibold text-text-primary', className)}
        {...props}
      >
        {children}
      </Component>
    )
  }
)

CardTitle.displayName = 'CardTitle'

// Card Content component
export interface CardContentProps extends HTMLAttributes<HTMLDivElement> {}

export const CardContent = forwardRef<HTMLDivElement, CardContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={clsx('', className)} {...props}>
        {children}
      </div>
    )
  }
)

CardContent.displayName = 'CardContent'
