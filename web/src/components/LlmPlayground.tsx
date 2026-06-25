import { useState } from "react";
import { Send, Star } from "lucide-react";
import type { TryOpsClient } from "../api";
import { llmVariants, quotaPlans, samplePrompt } from "../data";
import { compactJson, formatNumber, formatOptionalMs } from "../format";
import type { LlmGenerationResponse } from "../types";
import { MetricTile } from "./MetricTile";

interface LlmPlaygroundProps {
  client: TryOpsClient;
  onMutate: () => void;
}

export function LlmPlayground({ client, onMutate }: LlmPlaygroundProps) {
  const [prompt, setPrompt] = useState(samplePrompt);
  const [modelAlias, setModelAlias] = useState("champion");
  const [quotaPlan, setQuotaPlan] = useState("free");
  const [routingMode, setRoutingMode] = useState<"direct" | "canary" | "experiment_ab" | "experiment_bandit">("direct");
  const [canaryPercent, setCanaryPercent] = useState(10);
  const [maxTokens, setMaxTokens] = useState(180);
  const [structured, setStructured] = useState(true);
  const [shadow, setShadow] = useState(false);
  const [semanticCache, setSemanticCache] = useState(false);
  const [result, setResult] = useState<LlmGenerationResponse | undefined>();
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");

  async function submitPrompt() {
    setBusy(true);
    setResult(undefined);
    try {
      const response = await client.generateLlm({
        prompt,
        model_alias: modelAlias,
        max_tokens: maxTokens,
        structured,
        routing_mode: routingMode,
        canary_percent: canaryPercent,
        shadow,
        optimized_available: true,
        fallback_enabled: false,
        semantic_cache_enabled: semanticCache,
        user_id: "console-user",
        quota_plan: quotaPlan
      });
      setResult(response);
      onMutate();
    } finally {
      setBusy(false);
    }
  }

  async function submitFeedback(rating: number) {
    if (!result?.request_id) {
      return;
    }
    await client.submitFeedback({
      request_id: result.request_id,
      user_id: "console-user",
      rating,
      label: rating >= 4 ? "useful" : "review",
      comment: feedback
    });
    setFeedback("");
    onMutate();
  }

  return (
    <section className="workbench-grid">
      <form
        className="panel workbench-primary"
        onSubmit={(event) => {
          event.preventDefault();
          void submitPrompt();
        }}
      >
        <div className="panel-header">
          <div>
            <p className="eyebrow">LLM request</p>
            <h2>Generation</h2>
          </div>
          <button className="primary-button" disabled={busy || !prompt.trim()} type="submit">
            <Send aria-hidden="true" size={17} />
            {busy ? "Running" : "Run"}
          </button>
        </div>
        <label className="field stacked">
          <span>Prompt</span>
          <textarea onChange={(event) => setPrompt(event.target.value)} rows={12} value={prompt} />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Variant</span>
            <select onChange={(event) => setModelAlias(event.target.value)} value={modelAlias}>
              {llmVariants.map((variant) => (
                <option key={variant} value={variant}>{variant}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Quota plan</span>
            <select onChange={(event) => setQuotaPlan(event.target.value)} value={quotaPlan}>
              {quotaPlans.map((plan) => (
                <option key={plan} value={plan}>{plan}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Routing</span>
            <select onChange={(event) => setRoutingMode(event.target.value as typeof routingMode)} value={routingMode}>
              <option value="direct">direct</option>
              <option value="canary">canary</option>
              <option value="experiment_ab">experiment A/B</option>
              <option value="experiment_bandit">experiment bandit</option>
            </select>
          </label>
          <label className="field">
            <span>Canary %</span>
            <input
              max={100}
              min={0}
              onChange={(event) => setCanaryPercent(Number(event.target.value))}
              type="number"
              value={canaryPercent}
            />
          </label>
          <label className="field">
            <span>Max tokens</span>
            <input
              max={2048}
              min={1}
              onChange={(event) => setMaxTokens(Number(event.target.value))}
              type="number"
              value={maxTokens}
            />
          </label>
        </div>
        <div className="toggle-row">
          <label><input checked={structured} onChange={(event) => setStructured(event.target.checked)} type="checkbox" /> Structured</label>
          <label><input checked={shadow} onChange={(event) => setShadow(event.target.checked)} type="checkbox" /> Shadow</label>
          <label><input checked={semanticCache} onChange={(event) => setSemanticCache(event.target.checked)} type="checkbox" /> Cache</label>
        </div>
      </form>

      <aside className="panel">
        <div className="panel-header compact">
          <h2>Response metrics</h2>
        </div>
        <div className="capacity-stack">
          <MetricTile label="Latency" value={formatOptionalMs(result?.metrics?.latency_ms)} tone="green" />
          <MetricTile label="Tokens/sec" value={formatNumber(result?.metrics?.tokens_per_second)} tone="blue" />
          <MetricTile label="Memory" value={`${formatNumber(result?.metrics?.memory_gb)} GB`} tone="amber" />
          <MetricTile label="Quota" value={result?.quota?.allowed === false ? "blocked" : "allowed"} tone={result?.quota?.allowed === false ? "red" : "green"} />
        </div>
      </aside>

      <section className="panel workbench-output">
        <div className="panel-header compact">
          <h2>Output</h2>
          <span className="mono">{result?.trace?.trace_id?.slice(0, 16) || result?.request_id || "-"}</span>
        </div>
        {result?.error ? (
          <div className="error-box">{result.error.code}: {result.error.message}</div>
        ) : (
          <pre className="output-text">{result?.output?.text || "No output yet."}</pre>
        )}
        {result?.request_id ? (
          <div className="feedback-row">
            <input
              onChange={(event) => setFeedback(event.target.value)}
              placeholder="Feedback note"
              value={feedback}
            />
            {[5, 3, 1].map((rating) => (
              <button className="icon-button" key={rating} onClick={() => void submitFeedback(rating)} title={`Rate ${rating}`} type="button">
                <Star aria-hidden="true" size={17} />
              </button>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-header compact">
          <h2>Raw contract</h2>
        </div>
        <pre className="json-box">{result ? compactJson(result) : "{}"}</pre>
      </section>
    </section>
  );
}
