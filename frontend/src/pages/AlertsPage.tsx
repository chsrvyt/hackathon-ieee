import { AlertsList } from "../components/AlertsList";

export function AlertsPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p className="sub">Generated when an attendance import changes a risk level, and for condonation decisions.</p>
        </div>
      </div>
      <AlertsList title="All alerts" />
    </div>
  );
}
