import { useCallback, useEffect, useRef, useState } from "react";

// Global in-memory cache for query data & timestamps
const queryCache = new Map<string, { data: unknown; timestamp: number }>();

export interface UseQueryOptions<T> {
  enabled?: boolean;
  refetchInterval?: number;
  staleTime?: number; // ms before data is considered stale (default: 10s)
  initialData?: T;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

export interface UseQueryResult<T> {
  data: T | undefined;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  refetch: () => Promise<T | undefined>;
}

export function useQuery<T>(
  queryKey: string | readonly unknown[],
  queryFn: (signal?: AbortSignal) => Promise<T>,
  options: UseQueryOptions<T> = {}
): UseQueryResult<T> {
  const {
    enabled = true,
    refetchInterval,
    staleTime = 10000,
    initialData,
    onSuccess,
    onError,
  } = options;

  const key = Array.isArray(queryKey) ? JSON.stringify(queryKey) : String(queryKey);

  // Check cache for existing data
  const cached = queryCache.get(key);
  const isStale = !cached || Date.now() - cached.timestamp > staleTime;

  const [data, setData] = useState<T | undefined>(() => {
    if (cached) return cached.data as T;
    return initialData;
  });

  const [isLoading, setIsLoading] = useState<boolean>(!cached && enabled);
  const [isFetching, setIsFetching] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const queryFnRef = useRef(queryFn);
  queryFnRef.current = queryFn;

  const executeFetch = useCallback(async (): Promise<T | undefined> => {
    if (!enabled) return undefined;

    // Abort previous in-flight request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setIsFetching(true);
    if (!data && !cached) {
      setIsLoading(true);
    }

    try {
      const result = await queryFnRef.current(signal);
      if (!signal.aborted) {
        queryCache.set(key, { data: result, timestamp: Date.now() });
        setData(result);
        setError(null);
        setIsLoading(false);
        setIsFetching(false);
        onSuccess?.(result);
      }
      return result;
    } catch (err: unknown) {
      if (!signal.aborted) {
        const errorObj = err instanceof Error ? err : new Error(String(err));
        setError(errorObj);
        setIsLoading(false);
        setIsFetching(false);
        onError?.(errorObj);
      }
      return undefined;
    }
  }, [enabled, key, data, cached, onSuccess, onError]);

  // Initial fetch if enabled and stale/missing
  useEffect(() => {
    if (enabled && isStale) {
      executeFetch();
    } else if (cached && !data) {
      setData(cached.data as T);
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [key, enabled, isStale, executeFetch, cached, data]);

  // Polling refetch interval
  useEffect(() => {
    if (!enabled || !refetchInterval || refetchInterval <= 0) return;

    const timer = setInterval(() => {
      executeFetch();
    }, refetchInterval);

    return () => clearInterval(timer);
  }, [enabled, refetchInterval, executeFetch]);

  return {
    data,
    isLoading,
    isFetching,
    error,
    refetch: executeFetch,
  };
}

export function invalidateQuery(keyOrPrefix: string): void {
  for (const key of queryCache.keys()) {
    if (key.includes(keyOrPrefix)) {
      queryCache.delete(key);
    }
  }
}
