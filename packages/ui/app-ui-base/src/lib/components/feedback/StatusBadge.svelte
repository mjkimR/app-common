<script lang="ts">
  import { cn } from '../../styles/utils.js';
  import { statusIcons, type StatusBadgeVariant } from './status-icons.js';

  interface Props {
    variant?: StatusBadgeVariant;
    /** Visible status text; the tone color and icon only reinforce it. */
    label: string;
    /** Show the variant's decorative (aria-hidden) icon. Neutral variants have none. */
    icon?: boolean;
    class?: string;
  }

  let { variant = 'default', label, icon = true, class: className }: Props = $props();

  // Tone recipe: border + 15% tint + toned text, all from semantic tokens.
  const variantStyles: Record<StatusBadgeVariant, string> = {
    default: 'bg-secondary text-secondary-foreground',
    outline: 'border-border text-muted-foreground',
    info: 'border-info/30 bg-info/15 text-info',
    success: 'border-success/30 bg-success/15 text-success',
    warning: 'border-warning/30 bg-warning/15 text-warning',
    attention: 'border-attention/30 bg-attention/15 text-attention',
    destructive: 'border-destructive/30 bg-destructive/15 text-destructive',
  };

  const shape = $derived(icon ? statusIcons[variant] : undefined);
</script>

<span
  class={cn(
    'inline-flex max-w-full items-center gap-1 rounded-full border border-transparent px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
    variantStyles[variant],
    className
  )}
>
  {#if shape}
    <svg
      class="size-3.5 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {#if shape.circle}<circle cx="12" cy="12" r="10" />{/if}
      {#each shape.paths as d (d)}<path {d} />{/each}
    </svg>
  {/if}
  <span class="truncate">{label}</span>
</span>
