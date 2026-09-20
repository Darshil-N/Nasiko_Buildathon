"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowLeft, Check, AlertTriangle } from "lucide-react";
import dynamic from "next/dynamic";

// Dynamically import the map to prevent SSR issues
const Map = dynamic(() => import("@/components/Map"), { ssr: false, loading: () => <div className="w-full h-full bg-[#f5f5f7] rounded-[24px] animate-pulse flex items-center justify-center text-neutral-400">Loading Intelligence Map...</div> });

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-white text-[#1d1d1f] font-sans h-screen overflow-hidden flex flex-col">
      <nav className="px-8 py-6 flex items-center justify-between border-b border-neutral-100">
        <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-70 transition-opacity">
          <ArrowLeft className="w-4 h-4" />
          <span>Exit Intelligence View</span>
        </Link>
        <div className="text-sm font-semibold tracking-tight">Analysis ID: an_86dd6fa8</div>
      </nav>

      <main className="flex-1 flex overflow-hidden p-6 gap-6">

        {/* Left Side: Map */}
        <div className="flex-1 rounded-[24px] overflow-hidden shadow-sm border border-neutral-100 relative">
          <Map center={[12.9716, 77.5946]} zoom={13} />

          {/* Floating Metrics Overlay */}
          <div className="absolute top-6 left-6 z-[400] flex gap-4">
            <div className="bg-white/90 backdrop-blur-md px-6 py-4 rounded-2xl shadow-sm border border-neutral-100">
              <div className="text-3xl font-bold tracking-tight">84.0</div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mt-1">Peak Score</div>
            </div>
            <div className="bg-white/90 backdrop-blur-md px-6 py-4 rounded-2xl shadow-sm border border-neutral-100">
              <div className="text-3xl font-bold tracking-tight">100%</div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mt-1">Confidence</div>
            </div>
          </div>
        </div>

        {/* Right Side: Intelligence Panel */}
        <div className="w-[480px] bg-[#f5f5f7] rounded-[24px] p-8 overflow-y-auto hide-scrollbar flex flex-col shadow-inner">
          <h2 className="text-3xl font-bold tracking-tight mb-2">Mangamannapalya</h2>
          <p className="text-neutral-500 font-medium mb-8">Rank 1 &middot; Premium Cafe Segment</p>

          <div className="bg-white rounded-2xl p-6 shadow-sm mb-8">
            <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Growth Catalysts</h4>
            <ul className="space-y-4">
              <li className="flex items-start gap-3">
                <div className="mt-0.5 bg-black text-white p-1 rounded-full"><Check className="w-3 h-3" /></div>
                <span className="text-[15px] font-medium text-neutral-800 leading-snug">High footfall anchors (offices, colleges, malls) within reach.</span>
              </li>
              <li className="flex items-start gap-3">
                <div className="mt-0.5 bg-black text-white p-1 rounded-full"><Check className="w-3 h-3" /></div>
                <span className="text-[15px] font-medium text-neutral-800 leading-snug">Area spending power exactly matches the Premium tier.</span>
              </li>
            </ul>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm mb-8">
            <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Potential Risks</h4>
            <ul className="space-y-4">
              <li className="flex items-start gap-3">
                <div className="mt-0.5 bg-red-500 text-white p-1 rounded-full"><AlertTriangle className="w-3 h-3" /></div>
                <span className="text-[15px] font-medium text-neutral-800 leading-snug">High competitor density. 4 existing premium cafes detected within 2km radius.</span>
              </li>
            </ul>
          </div>

          <div className="flex-1">
            <h4 className="text-sm font-semibold uppercase tracking-widest text-neutral-400 mb-4">Analyst Briefing</h4>
            <p className="text-[15px] leading-relaxed text-neutral-600 font-medium">
              Mangamannapalya represents the optimal balance of raw footfall and disposable income for a premium cafe. The presence of major corporate parks guarantees strong weekday morning and lunch traffic. While competition exists, the underlying demographic velocity supports further market absorption. Securing a lease under 150,000 INR will ensure break-even within 8 months.
            </p>
          </div>

          <button className="mt-8 w-full bg-black text-white py-4 rounded-full font-semibold hover:scale-[1.02] transition-transform">
            Export Full Dossier
          </button>
        </div>
      </main>

      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
      `}} />
    </div>
  );
}
