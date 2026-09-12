<script lang="ts">
  import { cn } from '../../styles/utils.js';

  interface Props {
    size?: 'sm' | 'md' | 'lg';
    class?: string;
  }

  let { size = 'md', class: className }: Props = $props();

  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-8 w-8 border-3',
  };
</script>

<div
  class={cn(
    'inline-block animate-spin rounded-full border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite] text-primary',
    sizeClasses[size],
    className
  )}
  role="status"
>
  <span class="sr-only">Loading...</span>
</div>
