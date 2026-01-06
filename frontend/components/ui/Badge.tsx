import { HTMLAttributes, forwardRef } from 'react'
import { clsx } from 'clsx'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 't90' | 't30' | 'dss' | 'standard'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-medium rounded-full'

    const variants = {
      default: 'bg-bg-hover text-text-secondary',
      success: 'bg-green-500/10 text-green-400 border border-green-500/30',
      warning: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30',
      error: 'bg-red-500/10 text-red-400 border border-red-500/30',
      info: 'bg-accent-blue/10 text-accent-blue border border-accent-blue/30',
      // Fire rating variants
      t90: 'bg-fire-t90/10 text-fire-t90 border border-fire-t90/30',
      t30: 'bg-fire-t30/10 text-fire-t30 border border-fire-t30/30',
      dss: 'bg-fire-dss/10 text-fire-dss border border-fire-dss/30',
      standard: 'bg-fire-std/10 text-fire-std border border-fire-std/30',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-1 text-sm',
    }

    return (
      <span
        ref={ref}
        className={clsx(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'

// Confidence badge specifically for extraction confidence scores
export interface ConfidenceBadgeProps extends Omit<BadgeProps, 'variant'> {
  confidence: number // 0.0 to 1.0
}

export const ConfidenceBadge = forwardRef<HTMLSpanElement, ConfidenceBadgeProps>(
  ({ confidence, className, size = 'sm', ...props }, ref) => {
    const percentage = Math.round(confidence * 100)

    let variant: BadgeProps['variant'] = 'default'
    if (confidence >= 0.9) variant = 'success'
    else if (confidence >= 0.7) variant = 'info'
    else if (confidence >= 0.5) variant = 'warning'
    else variant = 'error'

    return (
      <Badge ref={ref} variant={variant} size={size} className={className} {...props}>
        {percentage}%
      </Badge>
    )
  }
)

ConfidenceBadge.displayName = 'ConfidenceBadge'

// Fire rating badge that auto-selects the right color
export interface FireRatingBadgeProps extends Omit<BadgeProps, 'variant'> {
  rating: string | null | undefined
}

export const FireRatingBadge = forwardRef<HTMLSpanElement, FireRatingBadgeProps>(
  ({ rating, className, ...props }, ref) => {
    if (!rating || rating === '-') {
      return (
        <Badge ref={ref} variant="standard" className={className} {...props}>
          Standard
        </Badge>
      )
    }

    let variant: BadgeProps['variant'] = 'standard'
    const upperRating = rating.toUpperCase()

    if (upperRating.includes('T90') || upperRating.includes('T 90')) {
      variant = 't90'
    } else if (upperRating.includes('T30') || upperRating.includes('T 30')) {
      variant = 't30'
    } else if (upperRating.includes('DSS') || upperRating.includes('RS')) {
      variant = 'dss'
    }

    return (
      <Badge ref={ref} variant={variant} className={className} {...props}>
        {rating}
      </Badge>
    )
  }
)

FireRatingBadge.displayName = 'FireRatingBadge'
