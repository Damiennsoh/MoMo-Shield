'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cva, type VariantProps } from 'class-variance-authority';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const buttonVariants = cva('inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffcc00]/60 disabled:pointer-events-none disabled:opacity-50', {
  variants: { variant: { default: 'bg-[#ffcc00] text-[#121820] shadow-[0_3px_14px_rgba(255,204,0,.13)] hover:bg-[#ffdc4b]', secondary: 'border border-white/10 bg-white/[.045] text-slate-200 hover:bg-white/[.085]', destructive: 'bg-rose-500/15 text-rose-300 border border-rose-400/20 hover:bg-rose-500/25', ghost: 'text-slate-400 hover:bg-white/[.06] hover:text-white', outline: 'border border-white/10 bg-transparent text-slate-300 hover:bg-white/[.05]' }, size: { default: 'h-9 px-4', sm: 'h-8 rounded-md px-3 text-xs', lg: 'h-11 px-5', icon: 'h-9 w-9' } }, defaultVariants: { variant: 'default', size: 'default' }
});
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => <button ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />);
Button.displayName = 'Button';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn('rounded-2xl border border-white/[.075] bg-[#0e141c]/90 text-slate-100 shadow-[0_10px_40px_rgba(0,0,0,.1)]', className)} {...props} />; }
export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn('flex flex-col space-y-1.5 p-5', className)} {...props} />; }
export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) { return <h3 className={cn('font-semibold leading-none tracking-tight', className)} {...props} />; }
export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) { return <p className={cn('text-sm text-slate-500', className)} {...props} />; }
export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn('p-5 pt-0', className)} {...props} />; }

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> { variant?: 'default' | 'low' | 'medium' | 'high' | 'outline' | 'success' }
export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const variants: Record<NonNullable<BadgeProps['variant']>, string> = { default: 'border-transparent bg-white/10 text-slate-300', low: 'border-emerald-300/15 bg-emerald-300/[.09] text-emerald-300', medium: 'border-amber-300/15 bg-amber-300/[.09] text-amber-200', high: 'border-rose-400/15 bg-rose-400/[.09] text-rose-300', outline: 'border-white/10 bg-transparent text-slate-400', success: 'border-emerald-300/15 bg-emerald-300/[.09] text-emerald-300' };
  return <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[9px] font-semibold capitalize leading-4', variants[variant], className)} {...props} />;
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => <input ref={ref} className={cn('flex h-10 w-full rounded-lg border border-white/10 bg-[#090e14] px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-[#ffcc00]/40 focus:ring-2 focus:ring-[#ffcc00]/10 disabled:cursor-not-allowed disabled:opacity-50', className)} {...props} />);
Input.displayName = 'Input';
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => <textarea ref={ref} className={cn('flex min-h-[110px] w-full resize-y rounded-lg border border-white/10 bg-[#090e14] px-3 py-3 text-sm leading-relaxed text-slate-100 outline-none placeholder:text-slate-600 focus:border-[#ffcc00]/40 focus:ring-2 focus:ring-[#ffcc00]/10', className)} {...props} />);
Textarea.displayName = 'Textarea';

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export function DialogContent({ className, children, ...props }: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
  return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out" /><DialogPrimitive.Content className={cn('fixed right-0 top-0 z-50 flex h-full w-full max-w-[480px] flex-col border-l border-white/10 bg-[#0c121a] shadow-2xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out sm:duration-300', className)} {...props}>{children}<DialogPrimitive.Close className="absolute right-5 top-5 rounded-lg p-2 text-slate-500 transition hover:bg-white/[.07] hover:text-white" aria-label="Close"><X size={16} /></DialogPrimitive.Close></DialogPrimitive.Content></DialogPrimitive.Portal>;
}
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;
