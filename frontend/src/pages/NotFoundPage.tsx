import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export function NotFoundPage() {
  return (
    <div className="page">
      <div className="card">
        <EmptyState title="Page not found">
          <Link to="/">Go to your home page</Link>
        </EmptyState>
      </div>
    </div>
  );
}
