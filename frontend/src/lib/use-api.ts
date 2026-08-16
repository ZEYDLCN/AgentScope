"use client";

import { useEffect, useState } from "react";

interface UseApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** İstemci tarafı `/api/*` proxy uçlarına basit veri çekme hook'u.
 * `key` değiştiğinde yeniden çeker; `null` verilirse istek atılmaz. */
export function useApi<T>(url: string | null, deps: unknown[] = []): UseApiState<T> & {
  refetch: () => void;
} {
  const [state, setState] = useState<UseApiState<T>>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!url) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({ data: null, error: null, loading: false });
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(url, { cache: "no-store" })
      .then(async (res) => {
        const body = await res.json().catch(() => null);
        if (cancelled) return;
        if (!res.ok) {
          setState({ data: null, error: body?.detail ?? body?.title ?? `Hata (${res.status})`, loading: false });
          return;
        }
        setState({ data: body as T, error: null, loading: false });
      })
      .catch((err) => {
        if (!cancelled) setState({ data: null, error: String(err), loading: false });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, tick, ...deps]);

  return { ...state, refetch: () => setTick((t) => t + 1) };
}
