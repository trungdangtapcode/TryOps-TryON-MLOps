export function formatOptionalMs(value?: number | null): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Math.round(value).toLocaleString()} ms`;
}

export function formatNumber(value?: number | null): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function stageTone(stage: string): "green" | "amber" | "blue" | "red" | "neutral" {
  if (stage === "champion" || stage === "approved") {
    return "green";
  }
  if (stage === "challenger" || stage === "candidate") {
    return "amber";
  }
  if (stage === "rejected" || stage === "blocked") {
    return "red";
  }
  return "blue";
}

export function compactJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
