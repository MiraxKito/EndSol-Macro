import { useState, useEffect } from 'react';

declare global {
  interface Window {
    pywebview?: {
      api: Record<string, (...args: unknown[]) => Promise<unknown>>;
    };
  }
}

export function usePyWebView() {
  const [ready, setReady] = useState<boolean>(() => {
    return Boolean(window.pywebview && window.pywebview.api);
  });

  useEffect(() => {
    if (ready) return;

    const handleReady = () => setReady(true);
    window.addEventListener('pywebviewready', handleReady);

    if (window.pywebview && window.pywebview.api) {
      setReady(true);
    }

    return () => {
      window.removeEventListener('pywebviewready', handleReady);
    };
  }, [ready]);

  return ready;
}
