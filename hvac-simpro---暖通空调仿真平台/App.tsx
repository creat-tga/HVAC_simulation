
import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ProjectSetup } from './components/ProjectSetup';
import { BuildingInfo } from './components/BuildingInfo';
import { 
  SimulationStep, 
  AppState, 
  ProjectInfo, 
  BuildingEnvelope, 
  HVACScheme 
} from './types';
import { simulateLoad, simulateEnergy } from './services/simulationService';
import { cn } from './lib/utils';
import { 
  ArrowRight, 
  Play, 
  RotateCcw, 
  Loader2, 
  AlertCircle,
  Plus,
  Trash2,
  ChevronRight,
  Wind
} from 'lucide-react';

const initialProject: ProjectInfo = {
  name: '陆家嘴办公大楼 B座',
  location: '上海',
  type: '办公楼',
  climateZone: '夏热冬冷',
};

const initialBuilding: BuildingEnvelope = {
  area: 12000,
  height: 4.2,
  orientation: 'South',
  wallUValue: 0.8,
  windowRatio: 0.45,
  occupancyDensity: 10,
  schedules: [
    { id: '1', name: '标准办公作息', type: 'Occupancy', hourlyValues: [0,0,0,0,0,0,0,0.2,0.8,1,1,1,0.5,1,1,1,1,0.6,0.2,0,0,0,0,0] },
    { id: '2', name: '办公照明策略', type: 'Lighting', hourlyValues: [0.1,0.1,0.1,0.1,0.1,0.1,0.2,0.6,0.9,1,1,1,1,1,1,1,1,0.8,0.4,0.2,0.1,0.1,0.1,0.1] },
  ],
};

const initialSchemes: HVACScheme[] = [
  {
    id: 's1',
    name: '方案A：常规离心式冷水机组',
    description: '常规离心机 + 冷却塔系统',
    chillerType: 'Centrifugal',
    coolingCapacity: 1500,
    cop: 5.8,
    pumps: 3,
    towers: 2,
    controlStrategy: '常规顺序启停',
    investment: 3500000,
  }
];

const App: React.FC = () => {
  const [state, setState] = useState<AppState>({
    currentStep: SimulationStep.PROJECT_SETUP,
    project: initialProject,
    building: initialBuilding,
    load: null,
    schemes: initialSchemes,
    results: {},
    isCalculating: false,
  });

  const [completedSteps, setCompletedSteps] = useState<SimulationStep[]>([]);

  const handleStepChange = (step: SimulationStep) => {
    setState(prev => ({ ...prev, currentStep: step }));
  };

  const handleProjectChange = (project: ProjectInfo) => {
    setState(prev => ({ ...prev, project }));
  };

  const handleBuildingChange = (building: BuildingEnvelope) => {
    setState(prev => ({ ...prev, building }));
  };

  const runLoadSimulation = async () => {
    setState(prev => ({ ...prev, isCalculating: true }));
    try {
      const load = await simulateLoad(state.building.area, state.project.type);
      setState(prev => ({ 
        ...prev, 
        load, 
        isCalculating: false,
        currentStep: SimulationStep.SYSTEM_SCHEME 
      }));
      setCompletedSteps(prev => [...new Set([...prev, SimulationStep.PROJECT_SETUP, SimulationStep.BUILDING_INFO, SimulationStep.LOAD_SIMULATION])]);
    } catch (error) {
      console.error(error);
      setState(prev => ({ ...prev, isCalculating: false }));
    }
  };

  const runEnergySimulation = async () => {
    setState(prev => ({ ...prev, isCalculating: true }));
    try {
      const results = await simulateEnergy(state);
      setState(prev => ({ 
        ...prev, 
        results, 
        isCalculating: false,
        currentStep: SimulationStep.RESULTS_DISPLAY 
      }));
      setCompletedSteps(prev => [...new Set([...prev, SimulationStep.SYSTEM_SCHEME, SimulationStep.ENERGY_SIMULATION])]);
    } catch (error) {
      console.error(error);
      setState(prev => ({ ...prev, isCalculating: false }));
    }
  };

  const addScheme = () => {
    const newScheme: HVACScheme = {
      ...state.schemes[0],
      id: crypto.randomUUID(),
      name: `方案${String.fromCharCode(65 + state.schemes.length)}：新配置`,
    };
    setState(prev => ({ ...prev, schemes: [...prev.schemes, newScheme] }));
  };

  const updateScheme = (id: string, updates: Partial<HVACScheme>) => {
    setState(prev => ({
      ...prev,
      schemes: prev.schemes.map(s => s.id === id ? { ...s, ...updates } : s)
    }));
  };

  const removeScheme = (id: string) => {
    if (state.schemes.length <= 1) return;
    setState(prev => ({
      ...prev,
      schemes: prev.schemes.filter(s => s.id !== id)
    }));
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-50 overflow-hidden font-sans">
      <Sidebar 
        currentStep={state.currentStep} 
        completedSteps={completedSteps}
        onStepClick={handleStepChange}
      />

      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Header with quick breadcrumbs */}
        <header className="h-16 border-b border-zinc-800 flex items-center justify-between px-8 bg-zinc-950/50 backdrop-blur-md z-20">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-zinc-500">{state.project.name}</span>
            <ChevronRight className="w-4 h-4 text-zinc-700" />
            <span className="text-zinc-200 font-medium">
              {state.currentStep === SimulationStep.PROJECT_SETUP && "工程配置"}
              {state.currentStep === SimulationStep.BUILDING_INFO && "建筑建模"}
              {state.currentStep === SimulationStep.LOAD_SIMULATION && "负荷仿真"}
              {state.currentStep === SimulationStep.SYSTEM_SCHEME && "系统设计"}
              {state.currentStep === SimulationStep.ENERGY_SIMULATION && "能耗计算"}
              {state.currentStep === SimulationStep.RESULTS_DISPLAY && "报告看板"}
            </span>
          </div>

          <div className="flex items-center gap-4">
            {state.isCalculating && (
              <div className="flex items-center gap-2 text-blue-400 text-xs font-medium animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin" />
                正在计算仿真中...
              </div>
            )}
            <button className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-2">
              <RotateCcw className="w-3 h-3" />
              重置工程
            </button>
          </div>
        </header>

        {/* Scrollable Workspace */}
        <div className="flex-1 overflow-y-auto bg-dot-grid">
          <div className="max-w-7xl mx-auto px-8 py-10 min-h-full flex flex-col">
            
            {/* Step Content Content */}
            <div className="flex-1">
              {state.currentStep === SimulationStep.PROJECT_SETUP && (
                <ProjectSetup data={state.project} onChange={handleProjectChange} />
              )}
              
              {state.currentStep === SimulationStep.BUILDING_INFO && (
                <BuildingInfo data={state.building} onChange={handleBuildingChange} />
              )}

              {state.currentStep === SimulationStep.LOAD_SIMULATION && (
                <div className="max-w-4xl mx-auto space-y-12">
                  <div className="text-center space-y-4">
                    <div className="inline-flex p-4 bg-blue-500/10 rounded-full text-blue-500 mb-2">
                      <Wind className="w-12 h-12" />
                    </div>
                    <h2 className="text-3xl font-bold">准备就绪，开始负荷仿真</h2>
                    <p className="text-zinc-400 max-w-lg mx-auto">
                      系统将基于 8760 小时气象参数，结合建筑围护结构热物性，计算该项目的全年逐时逐项负荷。
                    </p>
                  </div>

                  <div className="flex justify-center">
                    <button 
                      onClick={runLoadSimulation}
                      disabled={state.isCalculating}
                      className="group relative px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold text-lg flex items-center gap-3 transition-all active:scale-95 disabled:opacity-50"
                    >
                      {state.isCalculating ? <Loader2 className="w-6 h-6 animate-spin" /> : <Play className="w-6 h-6" />}
                      开始建筑负荷仿真
                      {state.isCalculating && <span className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs text-zinc-500 whitespace-nowrap">预计耗时 2-5 秒...</span>}
                    </button>
                  </div>
                </div>
              )}

              {state.currentStep === SimulationStep.SYSTEM_SCHEME && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-bold">第三步：空调系统方案设计</h2>
                      <p className="text-zinc-400">目前基于负荷峰值进行选型。冷负荷峰值：<span className="text-blue-400 font-mono font-bold">{Math.round(state.load?.coolingPeak || 0)} kW</span></p>
                    </div>
                    <button 
                      onClick={addScheme}
                      className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all active:scale-95"
                    >
                      <Plus className="w-4 h-4" />
                      添加对比方案
                    </button>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {state.schemes.map((scheme, idx) => (
                      <div key={scheme.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden flex flex-col shadow-xl">
                        <div className="p-6 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
                          <input 
                            value={scheme.name}
                            onChange={(e) => updateScheme(scheme.id, { name: e.target.value })}
                            className="bg-transparent text-lg font-bold text-white focus:outline-none focus:ring-1 focus:ring-blue-500 rounded px-1"
                          />
                          {state.schemes.length > 1 && (
                            <button onClick={() => removeScheme(scheme.id)} className="text-zinc-500 hover:text-red-500 transition-colors">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                        
                        <div className="p-6 space-y-6">
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">主机类型</label>
                              <select 
                                value={scheme.chillerType} 
                                onChange={(e) => updateScheme(scheme.id, { chillerType: e.target.value })}
                                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200"
                              >
                                <option value="Centrifugal">离心式冷水机组</option>
                                <option value="Screw">螺杆式冷水机组</option>
                                <option value="Magnetic">磁悬浮变频机组</option>
                                <option value="VRF">多联机系统 (VRF)</option>
                              </select>
                            </div>
                            <div className="space-y-1.5">
                              <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">设计能效 (COP)</label>
                              <input 
                                type="number" 
                                value={scheme.cop} 
                                step="0.1" 
                                onChange={(e) => updateScheme(scheme.id, { cop: parseFloat(e.target.value) })}
                                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-blue-400 font-mono"
                              />
                            </div>
                          </div>

                          <div className="space-y-3 p-4 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
                            <div className="flex justify-between items-center text-xs">
                              <span className="text-zinc-500">建议冷量 (1.1x)</span>
                              <span className="text-zinc-300 font-mono">~{Math.round((state.load?.coolingPeak || 0) * 1.1)} kW</span>
                            </div>
                            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                              <div 
                                className={cn(
                                  "h-full transition-all duration-500",
                                  scheme.coolingCapacity < (state.load?.coolingPeak || 0) ? "bg-red-500" : "bg-emerald-500"
                                )}
                                style={{ width: `${Math.min(100, (scheme.coolingCapacity / ((state.load?.coolingPeak || 0) * 1.2)) * 100)}%` }}
                              />
                            </div>
                            <div className="flex justify-between items-end">
                              <div className="space-y-1">
                                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">当前配置冷量</span>
                                <div className="flex items-center gap-2">
                                  <input 
                                    type="number" 
                                    value={scheme.coolingCapacity} 
                                    onChange={(e) => updateScheme(scheme.id, { coolingCapacity: parseFloat(e.target.value) })}
                                    className="bg-transparent text-xl font-bold text-white focus:outline-none w-24"
                                  />
                                  <span className="text-zinc-500 font-medium">kW</span>
                                </div>
                              </div>
                              {scheme.coolingCapacity < (state.load?.coolingPeak || 0) && (
                                <div className="flex items-center gap-1 text-red-500 text-[10px] font-bold animate-pulse">
                                  <AlertCircle className="w-3 h-3" />
                                  风险：负荷覆盖率不足
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {state.currentStep === SimulationStep.ENERGY_SIMULATION && (
                <div className="max-w-4xl mx-auto space-y-12 py-12">
                   <div className="text-center space-y-4">
                    <div className="inline-flex p-4 bg-emerald-500/10 rounded-full text-emerald-500 mb-2">
                      <Zap className="w-12 h-12" />
                    </div>
                    <h2 className="text-3xl font-bold">最后一步：计算全生命周期能耗</h2>
                    <p className="text-zinc-400 max-w-lg mx-auto">
                      系统将模拟 8760 小时运行策略，计算电费支出、碳排放总量以及系统综合 COP (SCOP)。
                    </p>
                  </div>

                  <div className="flex justify-center">
                    <button 
                      onClick={runEnergySimulation}
                      disabled={state.isCalculating}
                      className="group px-8 py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-2xl font-bold text-lg flex items-center gap-3 transition-all active:scale-95 shadow-xl shadow-emerald-900/20 disabled:opacity-50"
                    >
                      {state.isCalculating ? <Loader2 className="w-6 h-6 animate-spin" /> : <Play className="w-6 h-6" />}
                      开始系统能耗仿真
                    </button>
                  </div>
                </div>
              )}

              {state.currentStep === SimulationStep.RESULTS_DISPLAY && (
                 <div className="space-y-8 animate-in fade-in duration-500 pb-20">
                    <div className="flex items-center justify-between">
                      <h2 className="text-2xl font-bold">仿真结果展示与多方案对比</h2>
                      <div className="flex gap-2">
                         <button className="bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-xl text-sm font-bold border border-zinc-700">导出 PDF 报告</button>
                         <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-sm font-bold">查看诊断建议</button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                       {/* Result Cards */}
                       {state.schemes.map(scheme => {
                         const result = state.results[scheme.id];
                         if (!result) return null;
                         return (
                           <div key={scheme.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h3 className="text-sm font-bold text-zinc-300">{scheme.name}</h3>
                                  <p className="text-[10px] text-zinc-500 font-mono mt-1 uppercase tracking-widest">{scheme.chillerType} System</p>
                                </div>
                                <div className="p-1 px-2 bg-emerald-500/10 text-emerald-500 rounded text-[10px] font-bold">
                                  SIMULATED
                                </div>
                              </div>

                              <div className="grid grid-cols-2 gap-4">
                                <div className="p-4 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
                                   <div className="text-[10px] text-zinc-500 font-bold uppercase mb-1">全年电费 (CNY)</div>
                                   <div className="text-lg font-mono font-bold text-white">¥ {Math.round(result.totalCost).toLocaleString()}</div>
                                </div>
                                <div className="p-4 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
                                   <div className="text-[10px] text-zinc-500 font-bold uppercase mb-1">综合能效 SCOP</div>
                                   <div className="text-lg font-mono font-bold text-blue-400">{result.scop.toFixed(2)}</div>
                                </div>
                              </div>

                              <div className="space-y-3">
                                <div className="flex justify-between items-center">
                                  <span className="text-xs text-zinc-500">碳排放总量 (tCO₂)</span>
                                  <span className="text-sm font-mono text-zinc-200">{Math.round(result.totalCarbon / 1000)} t</span>
                                </div>
                                <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                                  <div className="h-full bg-blue-500" style={{ width: '70%' }} />
                                </div>
                              </div>
                           </div>
                         );
                       })}
                    </div>

                    <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8">
                       <h3 className="text-lg font-bold mb-8">逐月能耗分布对比 (kWh)</h3>
                       <div className="h-80 flex items-end gap-1">
                          {Array.from({ length: 12 }).map((_, i) => (
                             <div key={i} className="flex-1 flex gap-1 justify-center items-end h-full group relative">
                                {state.schemes.map((scheme, sIdx) => {
                                   const result = state.results[scheme.id];
                                   if (!result) return null;
                                   const height = (result.monthlyConsumption[i] / 50000) * 100;
                                   return (
                                     <div 
                                      key={scheme.id}
                                      className={cn(
                                        "w-2 sm:w-4 rounded-t-lg transition-all hover:brightness-125 cursor-pointer",
                                        sIdx === 0 ? "bg-blue-500/80 shadow-[0_0_15px_rgba(59,130,246,0.3)]" : "bg-zinc-700/80"
                                      )}
                                      style={{ height: `${Math.max(5, height)}%` }}
                                     >
                                        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-zinc-800 text-white text-[10px] p-2 rounded opacity-0 group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap border border-zinc-700 shadow-2xl">
                                           {scheme.name}: <span className="text-blue-400 font-mono font-bold">{Math.round(result.monthlyConsumption[i])} kWh</span>
                                        </div>
                                     </div>
                                   )
                                })}
                             </div>
                          ))}
                       </div>
                       <div className="flex justify-between px-2 mt-4 text-[10px] text-zinc-500 font-mono">
                          {['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'].map(m => (
                            <span key={m}>{m}</span>
                          ))}
                       </div>
                    </div>
                 </div>
              )}
            </div>

            {/* Bottom Floating Navigation */}
            <div className="mt-auto pt-10 sticky bottom-8 flex justify-center pointer-events-none">
               <div className="bg-zinc-900/80 backdrop-blur-xl border border-zinc-800 p-2 rounded-2xl shadow-2xl flex items-center gap-4 pointer-events-auto">
                  <div className="px-4 border-r border-zinc-800 hidden sm:block">
                    <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">仿真项目</p>
                    <p className="text-xs font-semibold text-zinc-200">{state.project.name}</p>
                  </div>
                  
                  <nav className="flex items-center gap-2">
                    {state.currentStep !== SimulationStep.PROJECT_SETUP && (
                      <button 
                        onClick={() => {
                          const idx = Object.values(SimulationStep).indexOf(state.currentStep);
                          handleStepChange(Object.values(SimulationStep)[idx - 1] as SimulationStep);
                        }}
                        className="p-3 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-xl transition-all"
                      >
                        <RotateCcw className="w-5 h-5" />
                      </button>
                    )}

                    {state.currentStep !== SimulationStep.RESULTS_DISPLAY && (
                      <button 
                         onClick={() => {
                            if (state.currentStep === SimulationStep.LOAD_SIMULATION) {
                              runLoadSimulation();
                            } else if (state.currentStep === SimulationStep.ENERGY_SIMULATION) {
                              runEnergySimulation();
                            } else {
                              const idx = Object.values(SimulationStep).indexOf(state.currentStep);
                              const next = Object.values(SimulationStep)[idx + 1] as SimulationStep;
                              handleStepChange(next);
                            }
                         }}
                         className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold text-sm shadow-lg shadow-blue-900/40 transition-all active:scale-95 group"
                      >
                         下一步
                         <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                      </button>
                    )}
                  </nav>
               </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
