import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

interface StatusBannerProps {
  health: "checking" | "ready" | "degraded";
  message?: string;
}

export function StatusBanner({ health, message }: StatusBannerProps) {
  if (health === "ready" && !message) {
    return (
      <div className="status-banner ready">
        <CheckCircle2 aria-hidden="true" size={18} />
        <span>API ready. Live data is connected through the configured gateway.</span>
      </div>
    );
  }

  if (health === "checking") {
    return (
      <div className="status-banner checking">
        <Loader2 aria-hidden="true" className="spin" size={18} />
        <span>Checking API readiness.</span>
      </div>
    );
  }

  return (
    <div className="status-banner degraded">
      <AlertTriangle aria-hidden="true" size={18} />
      <span>{message || "API unavailable. Console is showing local empty states."}</span>
    </div>
  );
}
