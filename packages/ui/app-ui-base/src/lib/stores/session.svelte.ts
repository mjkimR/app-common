export interface UserSession {
  id: string;
  email: string;
  name?: string;
  roles?: string[];
}

export class SessionStore {
  user = $state<UserSession | null>(null);
  token = $state<string | null>(null);
  initialized = $state(false);

  isAuthenticated = $derived(this.user !== null && this.token !== null);

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('access_token');
      const savedUser = localStorage.getItem('session_user');
      if (savedUser) {
        try {
          this.user = JSON.parse(savedUser);
        } catch {
          this.user = null;
        }
      }
      this.initialized = true;
    }
  }

  setSession(user: UserSession, token: string) {
    this.user = user;
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', token);
      localStorage.setItem('session_user', JSON.stringify(user));
    }
  }

  clearSession() {
    this.user = null;
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('session_user');
    }
  }
}

export const sessionStore = new SessionStore();
