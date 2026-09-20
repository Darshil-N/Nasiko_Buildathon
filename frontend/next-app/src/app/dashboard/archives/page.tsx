"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowUpRight } from "lucide-react";

interface AnalysisListItem {
  analysis_id: string;
  city: string;
  category: string;
  tier: string;
  status: string;
  created_at: string | null;
  top_zone: string | null;
}

const statusColor: Record<string, string> = {
  done: "bg-black text-white",
  running: "bg-neutral-200 text-neutral-700",
  queued: "bg-neutral-200 text-neutral-700",
  failed: "bg-red-100 text-red-700",
};

export default function Archives() {
  const router = useRouter();
  const [items, setItems] = useState<AnalysisListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/analyses")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error?.message ?? "Could not load past analyses.");
        setItems(data.analyses);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load past analyses."));
  }, []);

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] font-sans">
      <nav className="p-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <img src="/logo.png" alt="Disha AI" className="w-8 h-8 rounded-full" />
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-70 transition-opacity">
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Platform</span>
          </Link>
        </div>
        <Link
          href="/new"
          className="bg-black text-white px-6 py-3 rounded-full text-sm font-semibold hover:scale-[1.02] transition-transform"
        >
          New Evaluation
        </Link>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-5xl font-bold tracking-tight mb-2"
        >
          Archives.
        </motion.h1>
        <p className="text-xl text-[#86868b] font-medium mb-12">Every evaluation this platform has run.</p>

        {error && (
          <div className="bg-white rounded-2xl p-8 text-center text-red-600 font-medium shadow-sm">{error}</div>
        )}

        {!error && items === null && (
          <div className="bg-white rounded-2xl p-8 text-center text-neutral-400 font-medium shadow-sm">Loading...</div>
        )}

        {!error && items !== null && items.length === 0 && (
          <div className="bg-white rounded-2xl p-12 text-center shadow-sm">
            <p className="text-neutral-500 font-medium mb-6">No evaluations yet.</p>
            <Link href="/new" className="inline-block bg-black text-white px-8 py-3 rounded-full text-sm font-semibold">
              Run your first evaluation
            </Link>
          </div>
        )}

        {!error && items !== null && items.length > 0 && (
          <div className="space-y-3">
            {items.map((item) => (
              <button
                key={item.analysis_id}
                onClick={() => item.status === "done" && router.push(`/dashboard/demo?id=${item.analysis_id}`)}
                disabled={item.status !== "done"}
                className="w-full bg-white rounded-2xl p-6 shadow-sm flex items-center justify-between text-left hover:shadow-md transition-shadow disabled:cursor-default disabled:hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-lg font-semibold tracking-tight capitalize">
                      {item.tier} {item.category}
                    </span>
                    <span className={`text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wide ${statusColor[item.status] ?? "bg-neutral-200 text-neutral-700"}`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-500 font-medium capitalize">
                    {item.city}
                    {item.top_zone ? ` · Top zone: ${item.top_zone}` : ""}
                    {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ""}
                  </p>
                </div>
                {item.status === "done" && <ArrowUpRight className="w-5 h-5 text-neutral-400" />}
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
