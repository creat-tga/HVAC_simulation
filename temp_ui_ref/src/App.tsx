/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  Sun, Moon, Wind, Thermometer, 
  Activity, Settings, LayoutDashboard, 
  Fan, Droplets, Power
} from 'lucide-react';

// --- Background Component ---
// This is the core background design requested.
function HVACBackground({ isDark }: { isDark: boolean }) {
  return (
    <div className={`fixed inset-0 z-[-1] transition-colors duration-700 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      
      {/* 1. Technical Grid Pattern (Represents engineering/simulation precision) */}
      <div 
        className={`absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:32px_32px] transition-opacity duration-700 ${
          isDark ? 'opacity-30' : 'opacity-60'
        }`}
      />

      {/* 2. Fluid Dynamics / Thermal Blobs (Represents hot/cold airflow and thermodynamics) */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden blur-[100px] opacity-60 pointer-events-none">
        
        {/* Cold Air Source (Cooling) */}
        <div 
          className={`absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full animate-blob transition-colors duration-700 ${
            isDark ? 'bg-cyan-600/20' : 'bg-cyan-400/30'
          }`}
        />
        
        {/* Warm Air Source (Heating/Return Air) */}
        <div 
          className={`absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full animate-blob animation-delay-2000 transition-colors duration-700 ${
            isDark ? 'bg-orange-600/10' : 'bg-orange-400/20'
          }`}
        />
        
        {/* Neutral/Mixed Air Circulation */}
        <div 
          className={`absolute top-[30%] left-[50%] w-[40%] h-[40%] rounded-full animate-blob animation-delay-4000 transition-colors duration-700 ${
            isDark ? 'bg-blue-600/15' : 'bg-blue-400/20'
          }`}
        />
      </div>

      {/* 3. Subtle Vignette/Gradient Overlay for depth */}
      <div className={`absolute inset-0 transition-opacity duration-700 ${
        isDark 
          ? 'bg-[radial-gradient(circle_at_center,transparent_0%,rgba(2,6,23,0.8)_100%)]' 
          : 'bg-[radial-gradient(circle_at_center,transparent_0%,rgba(248,250,252,0.6)_100%)]'
      }`} />
    </div>
  );
}

// --- Sample Dashboard UI to demonstrate the background ---
export default function App() {
  const [isDark, setIsDark] = useState(true);

  // Toggle theme class on body for Tailwind (optional, but good practice)
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const glassClass = isDark 
    ? 'bg-slate-900/50 border-slate-700/50 text-slate-200' 
    : 'bg-white/60 border-slate-200/60 text-slate-800';

  return (
    <div className={`min-h-screen font-sans transition-colors duration-700 ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
      <HVACBackground isDark={isDark} />

      {/* Top Navigation */}
      <nav className={`sticky top-0 z-10 backdrop-blur-md border-b transition-colors duration-700 ${
        isDark ? 'bg-slate-950/50 border-slate-800' : 'bg-white/50 border-slate-200'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${isDark ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-100 text-cyan-600'}`}>
                <Wind className="w-6 h-6" />
              </div>
              <span className="font-semibold text-lg tracking-tight">
                HVAC Digital Twin
              </span>
            </div>
            
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsDark(!isDark)}
                className={`p-2 rounded-full transition-all ${
                  isDark ? 'hover:bg-slate-800 text-slate-400 hover:text-yellow-400' : 'hover:bg-slate-200 text-slate-500 hover:text-slate-900'
                }`}
                title="Toggle Theme"
              >
                {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-medium ${
                isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'
              }`}>
                Admin
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex gap-8">
        
        {/* Sidebar */}
        <aside className="w-64 hidden md:block shrink-0">
          <div className="flex flex-col gap-2 sticky top-24">
            {[
              { icon: LayoutDashboard, label: 'System Overview', active: true },
              { icon: Fan, label: 'Chiller Units' },
              { icon: Wind, label: 'Air Handling (AHU)' },
              { icon: Droplets, label: 'Cooling Towers' },
              { icon: Activity, label: 'Energy Analytics' },
              { icon: Settings, label: 'Configuration' },
            ].map((item, i) => (
              <button 
                key={i}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm font-medium ${
                  item.active 
                    ? (isDark ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'bg-cyan-50 text-cyan-700 border border-cyan-200')
                    : (isDark ? 'hover:bg-slate-800/50 text-slate-400' : 'hover:bg-slate-200/50 text-slate-600')
                }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </button>
            ))}
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1">
          <header className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight mb-2">System Overview</h1>
            <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Real-time simulation data for Central Plant Alpha.
            </p>
          </header>

          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`p-6 rounded-2xl border backdrop-blur-xl shadow-sm ${glassClass}`}
            >
              <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl ${isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                  <Thermometer className="w-5 h-5" />
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}`}>Normal</span>
              </div>
              <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Avg Supply Temp</p>
              <h3 className="text-3xl font-bold">7.2 <span className="text-lg font-normal text-slate-500">°C</span></h3>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`p-6 rounded-2xl border backdrop-blur-xl shadow-sm ${glassClass}`}
            >
              <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl ${isDark ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-100 text-cyan-600'}`}>
                  <Fan className="w-5 h-5" />
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700'}`}>Optimal</span>
              </div>
              <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Total Airflow</p>
              <h3 className="text-3xl font-bold">45,200 <span className="text-lg font-normal text-slate-500">CFM</span></h3>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className={`p-6 rounded-2xl border backdrop-blur-xl shadow-sm ${glassClass}`}
            >
              <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl ${isDark ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-100 text-orange-600'}`}>
                  <Power className="w-5 h-5" />
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>Peak Load</span>
              </div>
              <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>System Power</p>
              <h3 className="text-3xl font-bold">342 <span className="text-lg font-normal text-slate-500">kW</span></h3>
            </motion.div>
          </div>

          {/* Main Simulation Area */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className={`p-6 rounded-2xl border backdrop-blur-xl shadow-sm min-h-[400px] flex flex-col ${glassClass}`}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">Live Thermal Simulation</h3>
              <div className="flex gap-2">
                <div className="flex items-center gap-2 text-xs">
                  <span className="w-3 h-3 rounded-full bg-cyan-500"></span> Cooling
                </div>
                <div className="flex items-center gap-2 text-xs ml-3">
                  <span className="w-3 h-3 rounded-full bg-orange-500"></span> Heating
                </div>
              </div>
            </div>
            
            {/* Placeholder for actual simulation canvas/WebGL */}
            <div className={`flex-1 rounded-xl border border-dashed flex items-center justify-center ${
              isDark ? 'border-slate-700 bg-slate-900/30' : 'border-slate-300 bg-slate-100/50'
            }`}>
              <div className="text-center">
                <Activity className={`w-12 h-12 mx-auto mb-3 opacity-20 ${isDark ? 'text-cyan-400' : 'text-cyan-600'}`} />
                <p className={`text-sm font-mono ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  [ 3D Simulation Canvas Area ]<br/>
                  Background shines through translucent panels.
                </p>
              </div>
            </div>
          </motion.div>

        </main>
      </div>
    </div>
  );
}
