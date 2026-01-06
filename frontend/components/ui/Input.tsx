import { forwardRef, InputHTMLAttributes } from 'react'
import { clsx } from 'clsx'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-')

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-text-secondary mb-1.5"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={clsx(
            'w-full px-3 py-2 bg-bg-secondary border rounded-lg text-text-primary placeholder-text-muted',
            'focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent',
            'transition-colors duration-200',
            error ? 'border-red-500' : 'border-border hover:border-text-muted/50',
            className
          )}
          {...props}
        />
        {error && (
          <p className="mt-1.5 text-sm text-red-400">{error}</p>
        )}
        {hint && !error && (
          <p className="mt-1.5 text-sm text-text-muted">{hint}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

// Select component
export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, options, id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-')

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-sm font-medium text-text-secondary mb-1.5"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={clsx(
            'w-full px-3 py-2 bg-bg-secondary border rounded-lg text-text-primary',
            'focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent',
            'transition-colors duration-200 cursor-pointer',
            error ? 'border-red-500' : 'border-border hover:border-text-muted/50',
            className
          )}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && (
          <p className="mt-1.5 text-sm text-red-400">{error}</p>
        )}
      </div>
    )
  }
)

Select.displayName = 'Select'
