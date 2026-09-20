"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Printer } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
  ScatterChart, Scatter, ZAxis,
} from "recharts";

interface Recommendation {
  rank: number;
  zone_name: string;
  score: number;
  confidence: number;
  contributions: Record<string, number>;
  top_drivers: string[];
  top_risks: string[];
}

interface AnalysisResponse {
  analysis_id: string;
  status: string;
  city: string;
  category: string;
  tier: string;
  created_at: string | null;
  recommendations: Recommendation[];
  data_notes: string[];
}

interface CellsResponse {
  cells: { score: number | null }[];
}

const FEATURE_LABELS: Record<string, string> = {
  F1_anchor_footfall: "Anchor Footfall",
  F2_affluence_fit: "Affluence Fit",
  F3_residential_demand: "Residential Demand",
  F4_retail_cluster: "Retail Cluster",
  F5_competition_inverted: "Competition (inv.)",
  F6_gap_opportunity: "Gap Opportunity",
  F7_accessibility: "Accessibility",
  F8_rent_efficiency: "Rent Efficiency",
  F9_growth_momentum: "Growth Momentum",
};
const FEATURE_SHORT: Record<string, string> = {
  F1_anchor_footfall: "Foot",
  F2_affluence_fit: "Afflu",
  F3_residential_demand: "Resi",
  F4_retail_cluster: "Retail",
  F5_competition_inverted: "Comp",
  F6_gap_opportunity: "Gap",
  F7_accessibility: "Access",
  F8_rent_efficiency: "Rent",
  F9_growth_momentum: "Growth",
};

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-neutral-100">
      <div className="text-3xl font-bold tracking-tight tabular-nums">{value}</div>
      <div className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-[24px] p-8 shadow-sm border border-neutral-100">
      <h3 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-1">{title}</h3>
      <p className="text-xs text-neutral-400 mb-6">{subtitle}</p>
      {children}
    </div>
  );
}

function TooltipBox({ active, payload }: { active?: boolean; payload?: { payload: Record<string, unknown> }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-[#1d1d1f] text-white text-xs font-medium px-3 py-2 rounded-lg shadow-lg">
      {Object.entries(p).map(([k, v]) => (
        <div key={k}>
          {k}: {typeof v === "number" ? v.toFixed(1) : String(v)}
        </div>
      ))}
    </div>
  );
}

function truncateLabel(name: string, max = 24): string {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

function heatColor(t: number): string {
  // Single-hue sequential ramp (light -> dark blue), for magnitude within one feature column.
  const clamped = Math.max(0, Math.min(1, t));
  const lightness = 94 - clamped * 55;
  return `hsl(221, 70%, ${lightness}%)`;
}

function ReportContent() {
  const id = useSearchParams().get("id");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [cells, setCells] = useState<CellsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/analyses/${id}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status !== "done") throw new Error("This analysis has not finished yet.");
        setAnalysis(data);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the analysis."));
    fetch(`/api/analyses/${id}/cells`)
      .then((res) => res.json())
      .then(setCells)
      .catch(() => setCells(null));
  }, [id]);

  if (!id) return <Empty title="No analysis selected." />;
  if (error) return <Empty title={error} />;
  if (!analysis) return <Empty title="Loading report..." spin />;

  const zones = analysis.recommendations;
  const top = zones[0];
  const avgConfidence = zones.length ? (zones.reduce((s, z) => s + z.confidence, 0) / zones.length) * 100 : 0;
  const allFeatureKeys = Object.keys(top?.contributions ?? {});

  // The scoring engine falls back to a fixed neutral value for a signal it has no real data for
  // (rent efficiency, when no rent CSV exists for this city) rather than dropping it outright.
  // A column that's identical across every zone isn't a real comparison, so hide it here instead
  // of showing what would look like a fake, unchanging number in a "real data" report.
  const noRentData = analysis.data_notes.some((n) => n.toLowerCase().includes("rent") && n.toLowerCase().includes("not available"));
  const featureKeys = noRentData ? allFeatureKeys.filter((k) => k !== "F8_rent_efficiency") : allFeatureKeys;

  // City-wide score distribution, real bins over every evaluated cell.
  const scores = (cells?.cells ?? []).map((c) => c.score).filter((s): s is number => s !== null);
  const BIN_COUNT = 18;
  const maxScore = scores.length ? Math.max(...scores) : 100;
  const binSize = maxScore / BIN_COUNT || 1;
  const bins = Array.from({ length: BIN_COUNT }, (_, i) => ({
    range: `${Math.round(i * binSize)}-${Math.round((i + 1) * binSize)}`,
    count: 0,
    from: i * binSize,
  }));
  for (const s of scores) {
    const idx = Math.min(BIN_COUNT - 1, Math.floor(s / binSize));
    bins[idx].count += 1;
  }
  const topZoneBinIndex = top ? Math.min(BIN_COUNT - 1, Math.floor(top.score / binSize)) : -1;

  const rankData = zones
    .slice(0, 10)
    .map((z) => ({ name: z.zone_name, Score: z.score, rank: z.rank }))
    .sort((a, b) => a.Score - b.Score); // ascending so rank 1 renders at the top of the horizontal chart
  const scatterData = zones.map((z) => ({ score: z.score, confidence: z.confidence * 100, name: z.zone_name, rank: z.rank }));

  // Per-signal (per-column) max, so the heatmap actually compares zones against each other on the
  // same signal - normalizing per row instead would make every zone show a "hot" cell regardless
  // of its real strength, since it would always highlight that zone's own relative best signal.
  const topZones = zones.slice(0, 10);
  const columnMax = Object.fromEntries(
    featureKeys.map((k) => [k, Math.max(...topZones.map((z) => z.contributions[k] ?? 0), 0.01)])
  );

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] font-sans">
      <nav className="px-8 py-6 flex items-center justify-between border-b border-neutral-200 bg-white sticky top-0 z-10 print:hidden">
        <div className="flex items-center gap-4">
          <img src="/logo.png" alt="Disha AI" className="w-8 h-8 rounded-full" />
          <Link href={`/dashboard/demo?id=${id}`} className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-70 transition-opacity">
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Results</span>
          </Link>
        </div>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 bg-black text-white px-5 py-2.5 rounded-full text-sm font-semibold hover:scale-105 transition-transform"
        >
          <Printer className="w-4 h-4" />
          Export / Print
        </button>
      </nav>

      <main className="max-w-[1400px] mx-auto px-6 py-10">
        <div className="mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-2">Full Intelligence Report</h1>
          <p className="text-neutral-500 font-medium capitalize">
            {analysis.city} &middot; {analysis.tier} {analysis.category} &middot; Analysis {analysis.analysis_id}
            {analysis.created_at ? ` · ${new Date(analysis.created_at).toLocaleString()}` : ""}
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatTile value={scores.length ? scores.length.toLocaleString() : "—"} label="Zones Evaluated" />
          <StatTile value={String(featureKeys.length)} label="Weighted Signals" />
          <StatTile value={top ? top.score.toFixed(1) : "—"} label="Peak Score" />
          <StatTile value={`${avgConfidence.toFixed(0)}%`} label="Avg. Confidence (Top 10)" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <ChartCard
              title="City-Wide Score Distribution"
              subtitle={`Every one of ${scores.length.toLocaleString()} evaluated zones in ${analysis.city}, binned by score. The dark bar is where your top zone landed.`}
            >
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={bins} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis dataKey="range" tick={{ fontSize: 10, fill: "#86868b" }} axisLine={false} tickLine={false} interval={2} />
                  <YAxis tick={{ fontSize: 11, fill: "#86868b" }} axisLine={false} tickLine={false} />
                  <Tooltip content={<TooltipBox />} cursor={{ fill: "#f5f5f7" }} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {bins.map((b, i) => (
                      <Cell key={b.range} fill={i === topZoneBinIndex ? "#1d1d1f" : "#d4d4d8"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <ChartCard title="Confidence vs. Score" subtitle="Every recommended zone, positioned by score and data confidence.">
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart margin={{ left: 0, right: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" dataKey="score" name="Score" tick={{ fontSize: 10, fill: "#86868b" }} axisLine={false} tickLine={false} />
                <YAxis type="number" dataKey="confidence" name="Confidence" unit="%" tick={{ fontSize: 10, fill: "#86868b" }} axisLine={false} tickLine={false} />
                <ZAxis range={[60, 60]} />
                <Tooltip content={<TooltipBox />} cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatterData} fill="#1d1d1f" />
              </ScatterChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        <ChartCard title="Top 10 Zones, Ranked" subtitle="Direct output of the scoring engine for this run.">
          <ResponsiveContainer width="100%" height={420}>
            <BarChart data={rankData} layout="vertical" margin={{ left: 8, right: 32 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: "#86868b" }} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="name"
                width={200}
                tickFormatter={(v: string) => truncateLabel(v)}
                tick={{ fontSize: 12, fill: "#1d1d1f" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<TooltipBox />} cursor={{ fill: "#f5f5f7" }} />
              <Bar dataKey="Score" radius={[0, 4, 4, 0]} maxBarSize={22}>
                {rankData.map((d) => (
                  <Cell key={d.rank} fill={d.rank === 1 ? "#1d1d1f" : "#c7c7cc"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <div className="bg-white rounded-[24px] p-8 shadow-sm border border-neutral-100 mt-6">
          <div className="flex items-center justify-between mb-1 flex-wrap gap-4">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-neutral-400">Signal Contribution Matrix</h3>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wide">Lowest</span>
              <div className="w-24 h-2 rounded-full" style={{ background: `linear-gradient(90deg, ${heatColor(0)}, ${heatColor(1)})` }} />
              <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wide">Highest</span>
            </div>
          </div>
          <p className="text-xs text-neutral-400 mb-6">
            All 9 weighted signals, for the top 10 zones — the exact numbers the engine computed. Each column is shaded
            against the other 9 zones on that same signal, so darker genuinely means stronger there, not just “this
            zone&apos;s own best signal.”
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[820px] border-separate border-spacing-1">
              <thead>
                <tr>
                  <th className="text-left text-neutral-400 font-semibold uppercase tracking-wide pb-2 pr-3 sticky left-0 bg-white">Zone</th>
                  {featureKeys.map((k) => (
                    <th key={k} title={FEATURE_LABELS[k] ?? k} className="text-center text-neutral-400 font-semibold uppercase tracking-wide pb-2 px-1 whitespace-nowrap cursor-help">
                      {FEATURE_SHORT[k] ?? k}
                    </th>
                  ))}
                  <th className="text-right text-neutral-400 font-semibold uppercase tracking-wide pb-2 pl-3">Total</th>
                </tr>
              </thead>
              <tbody>
                {topZones.map((z) => (
                  <tr key={z.rank}>
                    <td className="py-1.5 pr-3 font-semibold whitespace-nowrap sticky left-0 bg-white">#{z.rank} {z.zone_name}</td>
                    {featureKeys.map((k) => {
                      const v = z.contributions[k] ?? 0;
                      const t = v / columnMax[k];
                      return (
                        <td key={k} className="text-center tabular-nums font-medium rounded-md" style={{ background: heatColor(t), color: t > 0.6 ? "white" : "#1d1d1f" }}>
                          {v.toFixed(1)}
                        </td>
                      );
                    })}
                    <td className="text-right pl-3 font-bold tabular-nums">{z.score.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {analysis.data_notes.length > 0 && (
          <div className="mt-6 text-xs text-neutral-400 leading-relaxed bg-white rounded-2xl p-6 border border-neutral-100">
            <span className="font-semibold text-neutral-500 uppercase tracking-widest text-[10px] block mb-2">Methodology &amp; Data Notes</span>
            {analysis.data_notes.join(" ")}
          </div>
        )}
      </main>
    </div>
  );
}

function Empty({ title, spin }: { title: string; spin?: boolean }) {
  return (
    <div className="min-h-screen bg-[#f5f5f7] flex items-center justify-center">
      <div className="text-center">
        {spin && <div className="w-8 h-8 border-2 border-neutral-200 border-t-black rounded-full animate-spin mx-auto mb-6" />}
        <p className="text-neutral-500 font-medium">{title}</p>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<Empty title="Loading..." spin />}>
      <ReportContent />
    </Suspense>
  );
}
