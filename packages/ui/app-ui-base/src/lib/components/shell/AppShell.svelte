<script lang="ts">
  import type { Snippet } from 'svelte';
  import { cn } from '../../styles/utils.js';

  interface Props {
    appName?: string;
    sidebar?: Snippet;
    headerActions?: Snippet;
    children: Snippet;
    class?: string;
  }

  let {
    appName = 'Application',
    sidebar,
    headerActions,
    children,
    class: className,
  }: Props = $props();

  let mobileOpen = $state(false);
</script>

<div class={cn('min-h-screen bg-background text-foreground flex', className)}>
  <!-- Desktop Sidebar -->
  {#if sidebar}
    <aside class="hidden md:flex md:w-64 md:flex-col border-r bg-card shrink-0">
      <div class="h-16 flex items-center px-6 border-b font-semibold text-lg tracking-tight">
        {appName}
      </div>
      <div class="flex-1 overflow-y-auto p-4 space-y-1">
        {@render sidebar()}
      </div>
    </aside>
  {/if}

  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col min-w-0">
    <!-- Topbar -->
    <header class="h-16 border-b px-4 md:px-6 flex items-center justify-between bg-card">
      <div class="flex items-center gap-3">
        {#if sidebar}
          <button
            type="button"
            class="md:hidden p-2 rounded-md hover:bg-accent text-muted-foreground"
            onclick={() => (mobileOpen = !mobileOpen)}
            aria-label="Toggle Navigation"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        {/if}
        <span class="font-semibold md:hidden">{appName}</span>
      </div>
      {#if headerActions}
        <div class="flex items-center gap-2">
          {@render headerActions()}
        </div>
      {/if}
    </header>

    <!-- Mobile Drawer -->
    {#if sidebar && mobileOpen}
      <div
        class="fixed inset-0 z-40 bg-black/50 md:hidden"
        onclick={() => (mobileOpen = false)}
        onkeydown={(e) => e.key === 'Escape' && (mobileOpen = false)}
        role="presentation"
      ></div>
      <aside class="fixed inset-y-0 left-0 z-50 w-64 bg-card border-r flex flex-col md:hidden">
        <div class="h-16 flex items-center justify-between px-6 border-b font-semibold text-lg">
          <span>{appName}</span>
          <button
            type="button"
            class="p-1 rounded-md hover:bg-accent"
            onclick={() => (mobileOpen = false)}
            aria-label="Close Navigation"
          >
            ✕
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-4 space-y-1">
          {@render sidebar()}
        </div>
      </aside>
    {/if}

    <!-- Page Body -->
    <main class="flex-1 p-4 md:p-8 overflow-y-auto">
      {@render children()}
    </main>
  </div>
</div>
