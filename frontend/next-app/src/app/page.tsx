"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, MapPin, BarChart3, BrainCircuit } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-white selection:bg-white selection:text-black">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-6 bg-black/50 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Disha AI" className="w-9 h-9 rounded-full" />
          <span className="text-xl font-medium tracking-tight">Disha AI.</span>
        </div>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="#features" className="opacity-80 hover:opacity-100 transition-opacity hidden md:block">Platform</Link>
          <Link href="/dashboard/archives" className="opacity-80 hover:opacity-100 transition-opacity hidden md:block">Archives</Link>
          <Link
            href="/new"
            className="bg-white text-black px-5 py-2.5 rounded-full font-semibold hover:scale-105 transition-transform"
          >
            Launch
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative flex flex-col items-center justify-center min-h-screen px-4 overflow-hidden pt-20">

        {/* Subtle Background Glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] rounded-full bg-white opacity-[0.03] blur-[100px] pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 text-center max-w-5xl"
        >
          <motion.img
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            src="/logo.png"
            alt="Disha AI"
            className="w-28 h-28 md:w-36 md:h-36 rounded-[28px] mx-auto mb-10 shadow-[0_0_80px_rgba(168,85,247,0.25)]"
          />

          <h1 className="text-6xl md:text-8xl lg:text-[9rem] font-bold tracking-tighter leading-[0.9] mb-8 flex items-center justify-center gap-4">
            Disha
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-orange-300">
              AI.
            </span>
          </h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 1 }}
            className="text-xl md:text-2xl text-neutral-400 font-light max-w-2xl mx-auto mb-12 tracking-tight"
          >
            Institutional-grade site selection. Autonomous agents deploying real-time geospatial, demographic, and financial models to find your next expansion target.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.8 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link
              href="/new"
              className="group relative flex items-center gap-2 bg-white text-black px-8 py-4 rounded-full font-medium text-lg overflow-hidden transition-transform hover:scale-105 active:scale-95"
            >
              <span>Initialize Engine</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              href="/dashboard/archives"
              className="flex items-center gap-2 px-8 py-4 rounded-full font-medium text-lg border border-neutral-800 text-neutral-300 hover:bg-neutral-900 transition-colors"
            >
              View Archives
            </Link>
          </motion.div>
        </motion.div>
      </main>

      {/* Value Pillars */}
      <section id="features" className="py-32 px-8 bg-neutral-950">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-16">

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8 }}
            className="flex flex-col items-start"
          >
            <div className="w-12 h-12 rounded-2xl bg-neutral-900 flex items-center justify-center mb-6">
              <MapPin className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-2xl font-semibold mb-4 tracking-tight">Geospatial Precision</h3>
            <p className="text-neutral-400 leading-relaxed font-light">
              We divide the city into strict H3 hexagonal grids, evaluating hyper-local footfall anchors like offices, colleges, and metro stations.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, delay: 0.1 }}
            className="flex flex-col items-start"
          >
            <div className="w-12 h-12 rounded-2xl bg-neutral-900 flex items-center justify-center mb-6">
              <BarChart3 className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-2xl font-semibold mb-4 tracking-tight">Financial Validation</h3>
            <p className="text-neutral-400 leading-relaxed font-light">
              Live interpolations of real estate listing data ensure your projected unit economics remain strictly viable in premium markets.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-col items-start"
          >
            <div className="w-12 h-12 rounded-2xl bg-neutral-900 flex items-center justify-center mb-6">
              <BrainCircuit className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-2xl font-semibold mb-4 tracking-tight">Autonomous Logic</h3>
            <p className="text-neutral-400 leading-relaxed font-light">
              Nasiko agents process the raw metrics into actionable narratives, defining clear catalysts and risk profiles for every location.
            </p>
          </motion.div>

        </div>
      </section>

      <footer className="py-12 text-center text-sm text-neutral-600 font-medium tracking-wide">
        Disha AI Intelligence Platform &copy; 2026.
      </footer>
    </div>
  );
}
