<script lang="ts">
  import type { Snippet } from 'svelte';
  import { cn } from '../../styles/utils.js';

  interface Props {
    title: string;
    description: string;
    action?: Snippet;
    class?: string;
  }

  let { title, description, action, class: className }: Props = $props();
</script>

<div
  class={cn(
    'flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center bg-card/50',
    className
  )}
>
  <div class="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
    </svg>
  </div>
  <h3 class="mt-4 text-base font-semibold text-foreground">{title}</h3>
  <p class="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
  {#if action}
    <div class="mt-4">
      {@render action()}
    </div>
  {/if}
</div>
