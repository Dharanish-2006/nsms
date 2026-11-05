export function PageLoader({ label = "Loading…" }) {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorPanel({ message, onRetry }) {
  return (
    <div className="panel error-panel" role="alert">
      <h2>Could not load data</h2>
      <p>{message || "The server did not respond."}</p>
      {onRetry && (
        <button className="primary-button compact-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
