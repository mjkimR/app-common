export type ThemeMode = 'light' | 'dark';

export class ThemeStore {
  current = $state<ThemeMode>('light');

  constructor() {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme') as ThemeMode | null;
      if (saved === 'dark' || saved === 'light') {
        this.current = saved;
      } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        this.current = 'dark';
      }
      this.apply();
    }
  }

  toggle() {
    this.current = this.current === 'dark' ? 'light' : 'dark';
    this.apply();
  }

  set(mode: ThemeMode) {
    this.current = mode;
    this.apply();
  }

  private apply() {
    if (typeof document !== 'undefined') {
      const root = document.documentElement;
      if (this.current === 'dark') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
      localStorage.setItem('theme', this.current);
    }
  }
}

export const themeStore = new ThemeStore();
