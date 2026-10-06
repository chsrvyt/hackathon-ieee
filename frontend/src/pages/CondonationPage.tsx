import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useCondonations } from "../api/hooks";
import type { CondonationStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { CondonationCard } from "../components/Condonation";
import { EmptyState, ErrorState, Loading } from "../components/ui";

const TABS: (CondonationStatus | "ALL")[] = ["PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "ALL"];

export function CondonationPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<CondonationStatus | "ALL">("PENDING");
  const isStudent = user?.role === "STUDENT";
  const list = useCondonations(tab, !isStudent);

  // Students manage their own requests from their dashboard.
  if (isStudent) return <Navigate to="/me" replace />;

  const canReview = list.data?.can_review ?? false;
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Condonation requests</h1>
          <p className="sub">
            {canReview
              ? "Review requests from students in your scope. Decisions are recorded with your name and comment."
              : "Read-only view of condonation requests and decisions."}
          </p>
        </div>
      </div>
      <div className="row" role="tablist" aria-label="Filter by status">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`btn btn-sm${tab === t ? " btn-primary" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "ALL" ? "All" : t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>
      <section className="card" aria-live="polite">
        {list.isPending ? (
          <Loading />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.data.items.length === 0 ? (
          <EmptyState title={tab === "PENDING" ? "No pending requests" : "No requests"}>
            {tab === "PENDING" ? "New student requests will appear here." : null}
          </EmptyState>
        ) : (
          <div className="stack">
            {list.data.items.map((r) => (
              <CondonationCard key={r.id} req={r} showStudent canReview={canReview} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
