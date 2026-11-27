import { useCallback, useEffect, useState } from 'react';

// Loads data for a page. Returns { data, error, loading, reload, setData }.
// `load` must be stable (wrap it in useCallback with its inputs).
export default function useLoad(load) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  const reload = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await load();
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState((s) => ({ ...s, error, loading: false }));
    }
  }, [load]);

  useEffect(() => { reload(); }, [reload]);

  const setData = useCallback((data) => setState({ data, error: null, loading: false }), []);
  return { ...state, reload, setData };
}