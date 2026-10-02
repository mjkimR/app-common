/** A newer refresh cancels its predecessor; late results never update state. */
export class LatestRequest {
  private controller: AbortController | null = null;

  cancel() {
    this.controller?.abort();
    this.controller = null;
  }

  async run<T>(read: (signal: AbortSignal) => Promise<T>, signal?: AbortSignal): Promise<T | undefined> {
    if (signal?.aborted) return;
    this.cancel();
    const controller = new AbortController();
    this.controller = controller;
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    try {
      const value = await read(controller.signal);
      if (!controller.signal.aborted) return value;
    } catch (error) {
      if (!controller.signal.aborted) throw error;
    } finally {
      signal?.removeEventListener('abort', abort);
      if (this.controller === controller) this.controller = null;
    }
  }
}

/** Schedule the next poll after completion, and abort pending reads on unmount. */
export function startPolling(read: (signal: AbortSignal) => Promise<void>, interval: number): () => void {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const run = async () => {
    try {
      await read(controller.signal);
    } finally {
      if (!controller.signal.aborted) timer = setTimeout(() => void run(), interval);
    }
  };
  void run();
  return () => {
    controller.abort();
    clearTimeout(timer);
  };
}
