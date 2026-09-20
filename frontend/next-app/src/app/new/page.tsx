"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

export default function NewAnalysis() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("cafe");
  const [tier, setTier] = useState("mid");
  const [rent, setRent] = useState(150000);
  const [sqft, setSqft] = useState(800);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: "bengaluru",
          category,
          tier,
          answers: {},
          constraints: { monthly_rent_budget_inr: rent, shop_size_sqft: sqft },
          top_n: 10,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error?.message ?? "Could not start the analysis.");
      }
      router.push(`/dashboard/demo?id=${data.analysis_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the analysis.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] font-sans selection:bg-black selection:text-white">
      <nav className="p-8 flex items-center gap-4">
        <img src="/logo.png" alt="Disha AI" className="w-8 h-8 rounded-full" />
        <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-70 transition-opacity">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Platform</span>
        </Link>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="text-5xl font-bold tracking-tight mb-2">Define your market.</h1>
          <p className="text-xl text-[#86868b] font-medium mb-16">Set absolute constraints. The agents handle the rest.</p>

          <form onSubmit={handleSubmit} className="bg-white p-10 sm:p-16 rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-16">

              <div className="space-y-8">
                <div>
                  <h3 className="text-xl font-semibold mb-6">Market Parameters</h3>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-semibold mb-2 ml-1">Target City</label>
                      <select
                        className="w-full bg-[#f5f5f7] rounded-2xl px-4 py-4 text-[#1d1d1f] font-medium outline-none focus:ring-2 focus:ring-black/5 appearance-none border-none"
                        disabled
                      >
                        <option value="bengaluru">Bengaluru</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2 ml-1">Business Category</label>
                      <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="w-full bg-[#f5f5f7] rounded-2xl px-4 py-4 text-[#1d1d1f] font-medium outline-none focus:ring-2 focus:ring-black/5 appearance-none border-none"
                      >
                        <option value="cafe">Cafe / Coffee Shop</option>
                        <option value="clothing">Apparel Retail</option>
                        <option value="pharmacy">Pharmacy / Healthcare</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2 ml-1">Target Tier</label>
                      <select
                        value={tier}
                        onChange={(e) => setTier(e.target.value)}
                        className="w-full bg-[#f5f5f7] rounded-2xl px-4 py-4 text-[#1d1d1f] font-medium outline-none focus:ring-2 focus:ring-black/5 appearance-none border-none"
                      >
                        <option value="premium">Premium / Niche</option>
                        <option value="mid">Mid-Market</option>
                        <option value="budget">Value / Budget</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-8">
                <div>
                  <h3 className="text-xl font-semibold mb-6">Financial Boundaries</h3>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-semibold mb-2 ml-1">Maximum Monthly Rent (INR)</label>
                      <input
                        type="number"
                        min={0}
                        value={rent}
                        onChange={(e) => setRent(Number(e.target.value))}
                        className="w-full bg-[#f5f5f7] rounded-2xl px-4 py-4 text-[#1d1d1f] font-medium outline-none focus:ring-2 focus:ring-black/5 border-none"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-semibold mb-2 ml-1">Expected Floor Space (Sq. Ft.)</label>
                      <input
                        type="number"
                        min={1}
                        value={sqft}
                        onChange={(e) => setSqft(Number(e.target.value))}
                        className="w-full bg-[#f5f5f7] rounded-2xl px-4 py-4 text-[#1d1d1f] font-medium outline-none focus:ring-2 focus:ring-black/5 border-none"
                      />
                    </div>
                  </div>
                </div>

                <div className="pt-8">
                  {error && (
                    <p className="text-sm font-medium text-red-600 mb-4">{error}</p>
                  )}
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-black text-white font-semibold text-lg py-5 rounded-full hover:bg-neutral-800 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:scale-100 flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        Deploying Agents...
                      </span>
                    ) : "Start Evaluation"}
                  </button>
                </div>
              </div>

            </div>
          </form>
        </motion.div>
      </main>
    </div>
  );
}
