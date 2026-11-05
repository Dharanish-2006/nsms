import { Component } from "react";

/** Catches rendering crashes so users see a message instead of a blank page. */
export class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="fullscreen-message" role="alert">
        <h1>Something went wrong</h1>
        <p>The page hit an unexpected problem. Reloading usually fixes it.</p>
        <button className="primary-button" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </div>
    );
  }
}
