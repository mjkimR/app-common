export type StatusBadgeVariant =
  | 'default'
  | 'outline'
  | 'info'
  | 'success'
  | 'warning'
  | 'attention'
  | 'destructive';

export interface StatusIconShape {
  /** Draw the 24x24 outline circle behind the paths. */
  circle: boolean;
  paths: readonly string[];
}

// Geometry from Lucide (ISC License): info, circle-check, triangle-alert, circle-alert, circle-x.
// Each status role has a distinct shape so it does not depend on color alone.
export const statusIcons: Record<StatusBadgeVariant, StatusIconShape | undefined> = {
  default: undefined,
  outline: undefined,
  info: { circle: true, paths: ['M12 16v-4', 'M12 8h.01'] },
  success: { circle: true, paths: ['m9 12 2 2 4-4'] },
  warning: {
    circle: false,
    paths: [
      'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3',
      'M12 9v4',
      'M12 17h.01',
    ],
  },
  attention: { circle: true, paths: ['M12 8v4', 'M12 16h.01'] },
  destructive: { circle: true, paths: ['m15 9-6 6', 'm9 9 6 6'] },
};
