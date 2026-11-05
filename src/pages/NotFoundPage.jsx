import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="content-page standard-page">
      <div className="panel not-found">
        <h1>Page not found</h1>
        <p>The page you opened does not exist or has moved.</p>
        <Link className="primary-button as-link" to="/">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
