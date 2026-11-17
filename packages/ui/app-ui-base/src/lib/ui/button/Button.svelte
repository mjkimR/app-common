<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import { cn } from '../../styles/utils.js';

  type Variant = 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  type Size = 'default' | 'sm' | 'lg' | 'icon';

  interface Props extends HTMLButtonAttributes {
    variant?: Variant;
    size?: Size;
    children?: Snippet;
    class?: string;
  }

  let {
    variant = 'default',
    size = 'default',
    children,
    class: className,
    type = 'button',
    ...restProps
  }: Props = $props();

  const variantStyles: Record<Variant, string> = {
    default: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90',
    destructive: 'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
    outline: 'border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground',
    secondary: 'bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80',
    ghost: 'hover:bg-accent hover:text-accent-foreground',
    link: 'text-primary underline-offset-4 hover:underline',
  };

  // Icons without an explicit size-* class follow the button size; an icon's own size-* class wins.
  const sizeStyles: Record<Size, string> = {
    default: 'h-9 px-4 py-2',
    sm: "h-8 gap-1.5 rounded-md px-3 text-xs [&_svg:not([class*='size-'])]:size-3.5",
    lg: 'h-10 rounded-md px-8',
    icon: 'h-9 w-9',
  };
</script>

<button
  {type}
  class={cn(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 cursor-pointer [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
    variantStyles[variant],
    sizeStyles[size],
    className
  )}
  {...restProps}
>
  {#if children}
    {@render children()}
  {/if}
</button>
