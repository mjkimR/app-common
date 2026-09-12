<script lang="ts">
  import type { Snippet } from 'svelte';
  import { cn } from '../../styles/utils.js';

  interface Props {
    children?: Snippet;
    class?: string;
  }

  let { children, class: className }: Props = $props();
</script>

<div
  class={cn(
    'rounded-xl border bg-card text-card-foreground shadow-sm',
    className
  )}
>
  {#if children}
    {@render children()}
  {/if}
</div>
