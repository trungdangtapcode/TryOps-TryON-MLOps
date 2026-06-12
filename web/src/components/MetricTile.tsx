interface MetricTileProps {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "green" | "amber" | "blue" | "red" | "neutral";
}

export function MetricTile({ label, value, detail, tone = "neutral" }: MetricTileProps) {
  return (
    <div className={`metric-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}
