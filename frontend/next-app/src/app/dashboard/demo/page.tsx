"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Check, AlertTriangle, Send, FileBarChart2, ArrowRight } from "lucide-react";
import dynamic from "next/dynamic";

const Map = dynamic(() => import("@/components/Map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-[#f5f5f7] rounded-[24px] animate-pulse flex items-center justify-center text-neutral-400">
      Loading Intelligence Map...
    </div>
  ),
});

interface Recommendation {
  rank: number;
  zone_name: string;
  score: number;
  confidence: number;
  contributions: Record<string, number>;
  top_drivers: string[];
  top_risks: string[];
  narrative: string | null;
  centroid: { lat: number; lon: number };
}

interface AnalysisResponse {
  analysis_id: string;
  status: "queued" | "running" | "done" | "failed";
  category: string;
  tier: string;
  summary: string | null;
  error: { code: string; message: string } | null;
  recommendations: Recommendation[];
  data_notes: string[];
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

function DashboardContent() {
  const id = useSearchParams().get("id");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [selectedRank, setSelectedRank] = useState(1);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [zonesEvaluated, setZonesEvaluated] = useState<number | null>(null);
  const stopped = useRef(false);

  useEffect(() => {
    if (!id) return;
    stopped.current = false;

    const poll = async () => {
      try {
        const res = await fetch(`/api/analyses/${id}`);
        const data: AnalysisResponse = await res.json();
        if (!res.ok) throw new Error((data as unknown as { error?: { message: string } }).error?.message ?? "Could not load the analysis.");
        setAnalysis(data);
        if (data.status === "done" || data.status === "failed") {
          stopped.current = true;
          return;
        }
      } catch (err) {
        setPollError(err instanceof Error ? err.message : "Could not reach the backend.");
        stopped.current = true;
        return;
      }
      if (!stopped.current) setTimeout(poll, 1500);
    };

    poll();
    return () => {
      stopped.current = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id || analysis?.status !== "done") return;
    fetch(`/api/analyses/${id}/cells`)
      .then((res) => res.json())
      .then((data: { cells: unknown[] }) => setZonesEvaluated(data.cells?.length ?? null))
      .catch(() => setZonesEvaluated(null));
  }, [id, analysis?.status]);

  const sendChat = async () => {
    if (!id || !question.trim() || chatBusy) return;
    const q = question.trim();
    setChat((c) => [...c, { role: "user", text: q }]);
    setQuestion("");
    setChatBusy(true);
    try {
      const res = await fetch(`/api/analyses/${id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      const answer = res.ok ? data.answer : (data?.error?.message ?? "Could not reach the chat agent.");
      setChat((c) => [...c, { role: "assistant", text: answer }]);
    } catch {
      setChat((c) => [...c, { role: "assistant", text: "Could not reach the chat agent." }]);
    } finally {
      setChatBusy(false);
    }
  };

  if (!id) {
    return <FullScreenMessage title="No analysis selected." body="Start one from the Launch screen." />;
  }
  if (pollError) {
    return <FullScreenMessage title="Something went wrong." body={pollError} />;
  }
  if (!analysis || analysis.status === "queued" || analysis.status === "running") {
    return <FullScreenMessage title="Deploying agents..." body="Scoring every zone in Bengaluru for real, live." spin />;
  }
  if (analysis.status === "failed" || analysis.recommendations.length === 0) {
    return <FullScreenMessage title="No candidates found." body={analysis.error?.message ?? "Try loosening your constraints and running again."} />;
  }

  const zones = analysis.recommendations;
  const selected = zones.find((z) => z.rank === selectedRank) ?? zones[0];
  const mapZones = zones.map((z) => ({ rank: z.rank, name: z.zone_name, score: z.score, lat: z.centroid.lat, lon: z.centroid.lon }));

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] font-sans flex flex-col">
      <nav className="px-8 py-6 flex items-center justify-between border-b border-neutral-100 bg-white">
        <div className="flex items-center gap-4">
          <img src="/logo.png" alt="Disha AI" className="w-8 h-8 rounded-full" />
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-70 transition-opacity">
            <ArrowLeft className="w-4 h-4" />
            <span>Exit Intelligence View</span>
          </Link>
        </div>
        <div className="text-sm font-semibold tracking-tight">Analysis ID: {analysis.analysis_id}</div>
      </nav>

      <main className="h-[82vh] flex overflow-hidden p-6 gap-6">
        <div className="flex-1 rounded-[24px] overflow-hidden shadow-sm border border-neutral-100 relative">
          <Map center={[selected.centroid.lat, selected.centroid.lon]} zoom={12} zones={mapZones} />
          <div className="absolute top-6 left-6 z-[400] flex gap-4">
            <div className="bg-white/90 backdrop-blur-md px-6 py-4 rounded-2xl shadow-sm border border-neutral-100">
              <div className="text-3xl font-bold tracking-tight">{selected.score.toFixed(1)}</div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mt-1">Peak Score</div>
            </div>
            <div className="bg-white/90 backdrop-blur-md px-6 py-4 rounded-2xl shadow-sm border border-neutral-100">
              <div className="text-3xl font-bold tracking-tight">{Math.round(selected.confidence * 100)}%</div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mt-1">Confidence</div>
            </div>
          </div>
          <div className="absolute bottom-6 left-6 z-[400] flex gap-2 flex-wrap max-w-[80%]">
            {zones.slice(0, 5).map((z) => (
              <button
                key={z.rank}
                onClick={() => setSelectedRank(z.rank)}
                className={`px-4 py-2 rounded-full text-xs font-semibold shadow-sm border transition-colors ${
                  z.rank === selectedRank ? "bg-black text-white border-black" : "bg-white/90 text-neutral-700 border-neutral-200 hover:bg-white"
                }`}
              >
                #{z.rank} {z.zone_name}
              </button>
            ))}
          </div>
          <div className="absolute bottom-6 right-6 z-[400] bg-white/90 backdrop-blur-md px-5 py-3 rounded-2xl shadow-sm border border-neutral-100">
            <div className="text-[10px] font-semibold text-neutral-500 uppercase tracking-widest mb-2">Score</div>
            <div className="w-32 h-2 rounded-full mb-1" style={{ background: "linear-gradient(90deg, #3b82f6, #22c55e, #f59e0b, #ef4444)" }} />
            <div className="flex justify-between text-[10px] font-semibold text-neutral-400">
              <span>Lower</span>
              <span>Higher</span>
            </div>
          </div>
        </div>

        <div className="w-[480px] bg-[#f5f5f7] rounded-[24px] p-8 overflow-y-auto hide-scrollbar flex flex-col shadow-inner">
          <motion.div key={selected.rank} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <h2 className="text-3xl font-bold tracking-tight mb-2">{selected.zone_name}</h2>
            <p className="text-neutral-500 font-medium mb-8">
              Rank {selected.rank} &middot; {analysis.tier} {analysis.category}
            </p>

            {selected.top_drivers.length > 0 && (
              <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Growth Catalysts</h4>
                <ul className="space-y-4">
                  {selected.top_drivers.map((d, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <div className="mt-0.5 bg-black text-white p-1 rounded-full"><Check className="w-3 h-3" /></div>
                      <span className="text-[15px] font-medium text-neutral-800 leading-snug">{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selected.top_risks.length > 0 && (
              <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Potential Risks</h4>
                <ul className="space-y-4">
                  {selected.top_risks.map((r, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <div className="mt-0.5 bg-red-500 text-white p-1 rounded-full"><AlertTriangle className="w-3 h-3" /></div>
                      <span className="text-[15px] font-medium text-neutral-800 leading-snug">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selected.narrative && (
              <div className="mb-6">
                <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Analyst Briefing</h4>
                <p className="text-[15px] leading-relaxed text-neutral-600 font-medium">{selected.narrative}</p>
              </div>
            )}

            {analysis.data_notes.length > 0 && (
              <p className="text-xs text-neutral-400 leading-relaxed mb-6">{analysis.data_notes.join(" ")}</p>
            )}
          </motion.div>

          <div className="mt-auto pt-4 border-t border-neutral-200">
            <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-3">Ask the Agent</h4>
            <div className="space-y-2 mb-3 max-h-48 overflow-y-auto hide-scrollbar">
              {chat.map((m, i) => (
                <div key={i} className={`text-sm rounded-xl px-3 py-2 ${m.role === "user" ? "bg-black text-white ml-8" : "bg-white text-neutral-700 mr-8"}`}>
                  {m.text}
                </div>
              ))}
              {chatBusy && <div className="text-sm rounded-xl px-3 py-2 bg-white text-neutral-400 mr-8">Thinking...</div>}
            </div>
            <div className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendChat()}
                placeholder="Why does this zone rank first?"
                className="flex-1 bg-white rounded-full px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-black/5"
              />
              <button onClick={sendChat} disabled={chatBusy} className="bg-black text-white rounded-full p-3 disabled:opacity-50">
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </main>

      <section className="max-w-[1400px] mx-auto px-6 pb-10">
        <div className="bg-[#1d1d1f] text-white rounded-[24px] p-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="hidden sm:flex w-14 h-14 rounded-2xl bg-white/10 items-center justify-center shrink-0">
              <FileBarChart2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-xl font-bold tracking-tight mb-1">Full Intelligence Report</h3>
              <p className="text-neutral-400 text-sm font-medium">
                {zonesEvaluated !== null ? zonesEvaluated.toLocaleString() : "Thousands of"} zones scored across 9 weighted
                signals — distribution charts, signal-by-signal breakdowns, and the raw numbers behind every rank.
              </p>
            </div>
          </div>
          <Link
            href={`/dashboard/report?id=${analysis.analysis_id}`}
            className="shrink-0 inline-flex items-center gap-2 bg-white text-black px-6 py-3.5 rounded-full font-semibold hover:scale-105 transition-transform"
          >
            View Full Report
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
      `}} />
    </div>
  );
}

function FullScreenMessage({ title, body, spin }: { title: string; body: string; spin?: boolean }) {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        {spin && <div className="w-8 h-8 border-2 border-neutral-200 border-t-black rounded-full animate-spin mx-auto mb-6" />}
        <h2 className="text-2xl font-bold tracking-tight mb-2">{title}</h2>
        <p className="text-neutral-500 font-medium">{body}</p>
        <Link href="/" className="inline-block mt-8 text-sm font-semibold underline">Back to Platform</Link>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <Suspense fallback={<FullScreenMessage title="Loading..." body="" spin />}>
      <DashboardContent />
    </Suspense>
  );
}
