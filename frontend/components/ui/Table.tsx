import { forwardRef, HTMLAttributes, ThHTMLAttributes, TdHTMLAttributes } from 'react'
import { clsx } from 'clsx'

// Table root
export interface TableProps extends HTMLAttributes<HTMLTableElement> {}

export const Table = forwardRef<HTMLTableElement, TableProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div className="w-full overflow-x-auto">
        <table
          ref={ref}
          className={clsx('w-full text-sm', className)}
          {...props}
        >
          {children}
        </table>
      </div>
    )
  }
)

Table.displayName = 'Table'

// Table header
export interface TableHeaderProps extends HTMLAttributes<HTMLTableSectionElement> {}

export const TableHeader = forwardRef<HTMLTableSectionElement, TableHeaderProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <thead
        ref={ref}
        className={clsx('border-b border-border', className)}
        {...props}
      >
        {children}
      </thead>
    )
  }
)

TableHeader.displayName = 'TableHeader'

// Table body
export interface TableBodyProps extends HTMLAttributes<HTMLTableSectionElement> {}

export const TableBody = forwardRef<HTMLTableSectionElement, TableBodyProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <tbody
        ref={ref}
        className={clsx('divide-y divide-border', className)}
        {...props}
      >
        {children}
      </tbody>
    )
  }
)

TableBody.displayName = 'TableBody'

// Table row
export interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  isClickable?: boolean
}

export const TableRow = forwardRef<HTMLTableRowElement, TableRowProps>(
  ({ className, isClickable, children, ...props }, ref) => {
    return (
      <tr
        ref={ref}
        className={clsx(
          'transition-colors',
          isClickable && 'hover:bg-bg-hover cursor-pointer',
          className
        )}
        {...props}
      >
        {children}
      </tr>
    )
  }
)

TableRow.displayName = 'TableRow'

// Table head cell
export interface TableHeadProps extends ThHTMLAttributes<HTMLTableCellElement> {
  sortable?: boolean
  sorted?: 'asc' | 'desc' | null
  onSort?: () => void
}

export const TableHead = forwardRef<HTMLTableCellElement, TableHeadProps>(
  ({ className, sortable, sorted, onSort, children, ...props }, ref) => {
    return (
      <th
        ref={ref}
        className={clsx(
          'px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase tracking-wider',
          sortable && 'cursor-pointer select-none hover:text-text-primary',
          className
        )}
        onClick={sortable ? onSort : undefined}
        {...props}
      >
        <div className="flex items-center gap-1">
          {children}
          {sortable && (
            <span className="text-text-muted">
              {sorted === 'asc' && '↑'}
              {sorted === 'desc' && '↓'}
              {!sorted && '↕'}
            </span>
          )}
        </div>
      </th>
    )
  }
)

TableHead.displayName = 'TableHead'

// Table cell
export interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {}

export const TableCell = forwardRef<HTMLTableCellElement, TableCellProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <td
        ref={ref}
        className={clsx('px-4 py-3 text-text-primary', className)}
        {...props}
      >
        {children}
      </td>
    )
  }
)

TableCell.displayName = 'TableCell'

// Empty state for tables
export interface TableEmptyProps extends HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  title: string
  description?: string
}

export const TableEmpty = forwardRef<HTMLDivElement, TableEmptyProps>(
  ({ icon, title, description, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx('py-12 text-center', className)}
        {...props}
      >
        {icon && (
          <div className="w-12 h-12 mx-auto mb-4 bg-bg-hover rounded-full flex items-center justify-center text-text-muted">
            {icon}
          </div>
        )}
        <p className="text-text-secondary mb-1">{title}</p>
        {description && (
          <p className="text-sm text-text-muted">{description}</p>
        )}
      </div>
    )
  }
)

TableEmpty.displayName = 'TableEmpty'
