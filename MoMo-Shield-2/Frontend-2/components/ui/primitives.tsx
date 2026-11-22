'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cva, type VariantProps } from 'class-variance-authority';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-xs font-semibold tracking-wide transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffcc00] focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 select-none active:scale-[0.98]',
  {
    variants: {
      variant: {
        default:
          'bg-[#ffcc00] text-[#090d12] shadow-[0_2px_12px_rgba(255,204,0,.22)] hover:bg-[#ffe054] hover:shadow-[0_4px_16px_rgba(255,204,0,.3)] font-bold',
        secondary:
          'border border-slate-700/80 bg-slate-800/80 text-slate-100 hover:bg-slate-700 hover:border-slate-600 hover:text-white',
        destructive:
          'border border-rose-500/40 bg-rose-500/20 text-rose-200 hover:bg-rose-500/30 hover:border-rose-400',
        ghost:
          'text-slate-300 hover:bg-white/[.08] hover:text-white',
        outline:
          'border border-slate-700 bg-transparent text-slate-200 hover:bg-white/[.07] hover:border-slate-500 hover:text-white',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-[11px]',
        lg: 'h-11 px-6 text-sm font-bold',
        icon: 'h-9 w-9 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
  )
);
Button.displayName = 'Button';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-white/[.1] bg-[#0c121a]/95 text-slate-100 shadow-[0_8px_32px_rgba(0,0,0,.35)] backdrop-blur-md transition-shadow',
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col space-y-1.5 p-5', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-sm font-bold tracking-tight text-white', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-xs text-slate-400', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5 pt-0', className)} {...props} />;
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'low' | 'medium' | 'high' | 'outline' | 'success';
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const variants: Record<NonNullable<BadgeProps['variant']>, string> = {
    default: 'border-slate-700 bg-slate-800 text-slate-200',
    low: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300 font-semibold',
    medium: 'border-amber-500/40 bg-amber-500/15 text-amber-200 font-semibold',
    high: 'border-rose-500/45 bg-rose-500/20 text-rose-200 font-bold',
    outline: 'border-white/15 bg-transparent text-slate-300',
    success: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300 font-semibold',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-medium leading-4 tracking-wide',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-lg border border-white/[.14] bg-[#080d14] px-3.5 py-2 text-xs font-medium text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-[#ffcc00] focus:ring-2 focus:ring-[#ffcc00]/20 disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  )
);
Input.displayName = 'Input';

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[120px] w-full resize-y rounded-lg border border-white/[.14] bg-[#080d14] px-3.5 py-3 text-xs leading-relaxed text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-[#ffcc00] focus:ring-2 focus:ring-[#ffcc00]/20',
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = 'Textarea';

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md data-[state=open]:animate-in data-[state=closed]:animate-out" />
      <DialogPrimitive.Content
        className={cn(
          'fixed right-0 top-0 z-50 flex h-full w-full max-w-[520px] flex-col border-l border-white/[.12] bg-[#0b1018] shadow-2xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out sm:duration-300',
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className="absolute right-5 top-5 rounded-lg border border-white/10 p-2 text-slate-400 transition hover:bg-white/[.1] hover:text-white"
          aria-label="Close"
        >
          <X size={16} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;
