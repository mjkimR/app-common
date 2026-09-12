<script lang="ts">
  import { cn } from '../../styles/utils.js';

  type Variant = 'default' | 'success' | 'warning' | 'destructive' | 'outline';

  interface Props {
    variant?: Variant;
    label: string;
    class?: string;
  }

  let { variant = 'default', label, class: className }: Props = $props();

  const variantStyles: Record<Variant, string> = {
    default: 'bg-secondary text-secondary-foreground',
    success: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20',
    destructive: 'bg-destructive/15 text-destructive border-destructive/20',
    outline: 'border border-border text-muted-foreground',
  };
</script>

<span
  class={cn(
    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border border-transparent',
    variantStyles[variant],
    className
  )}
>
  {label}
</span>
