import { useCallback, useEffect, useState } from "react";

/** Load data for an admin screen; `reload()` refetches after an action. */
export function useLoad(fetcher, deps) {
  const [tick, setTick] = useState(0);
  const key = `${JSON.stringify(deps)}#${tick}`;
  const [state, setState] = useState({ key: "", data: null, error: "" });
  useEffect(() => {
    let cancelled = false;
    fetcher()
      .then((data) => !cancelled && setState({ key, data, error: "" }))
      .catch(
        (e) =>
          !cancelled &&
          setState({ key, data: null, error: e?.message || "Request failed." }),
      );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: state.data, error: state.error, loading: state.key !== key, reload };
}

/** Run an admin action, then refresh. Returns an error message or "". */
export async function act(fn, reload) {
  try {
    await fn();
    reload?.();
    return "";
  } catch (e) {
    return e?.message || "That did not work.";
  }
}
