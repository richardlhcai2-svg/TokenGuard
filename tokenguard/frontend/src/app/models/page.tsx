"use client";

import { useState } from "react";

interface Recommendation {
  recommended_model: string;
  current_model: string;
  task_type: string;
  estimated_saving_pct: number;
  confidence: number;
  reason: string;
}

export default function ModelsPage() {
  const [prompt, setPrompt] = useState("");
  const [currentModel, setCurrentModel] = useState("claude-sonnet-4-20250514");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRecommend = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/recommendations/model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, current_model: currentModel }),
      });
      if (!res.ok) throw new Error("Failed to get recommendation");
      const data = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const models = [
    { id: "claude-opus-4-20250514", name: "Claude Opus 4", provider: "Anthropic", level: "Expert", best_for: "Complex reasoning, architecture, deep debugging" },
    { id: "claude-sonnet-4-5-20250514", name: "Claude Sonnet 4.5", provider: "Anthropic", level: "Advanced", best_for: "Balanced speed + quality for most tasks" },
    { id: "claude-sonnet-4-20250514", name: "Claude Sonnet 4", provider: "Anthropic", level: "Advanced", best_for: "Code generation, refactoring, general use" },
    { id: "claude-fast-4-20250514", name: "Claude Fast 4", provider: "Anthropic", level: "Intermediate", best_for: "Fast, cost-effective drafting and summarization" },
    { id: "claude-haiku-4-20250514", name: "Claude Haiku 4", provider: "Anthropic", level: "Basic", best_for: "Quick tasks, documentation, simple queries" },
    { id: "o1-pro", name: "o1 Pro", provider: "OpenAI", level: "Expert", best_for: "Math, science, complex multi-step reasoning" },
    { id: "o3", name: "o3", provider: "OpenAI", level: "Expert", best_for: "High-quality reasoning, competitive programming" },
    { id: "gpt-4.5-preview", name: "GPT-4.5 Preview", provider: "OpenAI", level: "Advanced", best_for: "Creative writing, nuanced analysis, A/B testing" },
    { id: "chatgpt-4.5-api", name: "ChatGPT-4.5 API", provider: "OpenAI", level: "Advanced", best_for: "Conversational tasks, creative work" },
    { id: "gpt-4.1", name: "GPT-4.1", provider: "OpenAI", level: "Advanced", best_for: "General-purpose coding, balanced cost-performance" },
    { id: "o3-mini", name: "o3 Mini", provider: "OpenAI", level: "Advanced", best_for: "Affordable reasoning, math, coding" },
    { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", provider: "Google", level: "Expert", best_for: "Long context, multimodal, code + docs" },
    { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", provider: "Google", level: "Advanced", best_for: "Fast reasoning, good balance of speed/quality" },
    { id: "deepseek-r1", name: "DeepSeek R1", provider: "DeepSeek", level: "Expert", best_for: "Cost-effective reasoning, coding, math" },
    { id: "deepseek-v3.2", name: "DeepSeek V3.2", provider: "DeepSeek", level: "Advanced", best_for: "General chat, coding, high throughput" },
    { id: "llama-4-maverick", name: "Llama 4 Maverick", provider: "Meta", level: "Advanced", best_for: "Open-weight, self-hosted, API via providers" },
    { id: "mistral-large-latest", name: "Mistral Large", provider: "Mistral", level: "Advanced", best_for: "Multilingual, code, structured output" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Models &amp; Recommendations</h1>

      {/* Recommendation Widget */}
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Model Recommender</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Describe your task and get a model recommendation to optimize cost vs quality.
        </p>
        <div className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Generate a REST API endpoint with authentication"
            className="w-full rounded-md border bg-background p-3 text-sm placeholder:text-muted-foreground"
            rows={3}
          />
          <div className="flex gap-3">
            <select
              value={currentModel}
              onChange={(e) => setCurrentModel(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <optgroup label="Anthropic">
                <option value="claude-opus-4-20250514">Claude Opus 4</option>
                <option value="claude-sonnet-4-5-20250514">Claude Sonnet 4.5</option>
                <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                <option value="claude-fast-4-20250514">Claude Fast 4</option>
                <option value="claude-haiku-4-20250514">Claude Haiku 4</option>
              </optgroup>
              <optgroup label="OpenAI">
                <option value="o1-pro">o1 Pro</option>
                <option value="o3">o3</option>
                <option value="gpt-4.5-preview">GPT-4.5 Preview</option>
                <option value="gpt-4.1">GPT-4.1</option>
                <option value="o3-mini">o3 Mini</option>
                <option value="o4-mini">o4 Mini</option>
              </optgroup>
              <optgroup label="Google">
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              </optgroup>
              <optgroup label="DeepSeek">
                <option value="deepseek-r1">DeepSeek R1</option>
                <option value="deepseek-v3.2">DeepSeek V3.2</option>
              </optgroup>
              <optgroup label="Meta">
                <option value="llama-4-maverick">Llama 4 Maverick</option>
              </optgroup>
              <optgroup label="Mistral">
                <option value="mistral-large-latest">Mistral Large</option>
              </optgroup>
            </select>
            <button
              onClick={handleRecommend}
              disabled={loading || !prompt.trim()}
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? "Analyzing..." : "Recommend"}
            </button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        {result && (
          <div className="mt-4 rounded-lg border bg-card/50 p-4 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">Recommended: <code className="text-primary">{result.recommended_model}</code></span>
              <span className={`text-xs font-medium ${result.estimated_saving_pct > 0 ? "text-green-600" : "text-muted-foreground"}`}>
                {result.estimated_saving_pct > 0 ? `Save ${result.estimated_saving_pct}%` : "Already optimal"}
              </span>
            </div>
            <div className="text-muted-foreground">{result.reason}</div>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Task: {result.task_type}</span>
              <span>Confidence: {(result.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Model Comparison Table */}
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Model Comparison</h2>
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Model</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Provider</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Level</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Best For</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.id} className="border-t">
                  <td className="px-4 py-3 font-mono text-xs">{m.name}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-muted-foreground">{m.provider}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${
                      m.level === "Expert" ? "bg-purple-100 text-purple-700" :
                      m.level === "Advanced" ? "bg-blue-100 text-blue-700" :
                      m.level === "Intermediate" ? "bg-yellow-100 text-yellow-700" :
                      "bg-green-100 text-green-700"
                    }`}>
                      {m.level}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{m.best_for}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
