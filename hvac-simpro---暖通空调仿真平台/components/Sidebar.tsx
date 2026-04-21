
import React from 'react';
import { SimulationStep } from '../types';
import { cn } from '../lib/utils';
import { 
  Building2, 
  Settings2, 
  Zap, 
  LayoutDashboard, 
  ClipboardCheck, 
  Wind,
  StepForward,
  CheckCircle2
} from 'lucide-react';

interface SidebarProps {
  currentStep: SimulationStep;
  completedSteps: SimulationStep[];
  onStepClick: (step: SimulationStep) => void;
}

const steps = [
  { id: SimulationStep.PROJECT_SETUP, label: '工程信息', icon: ClipboardCheck },
  { id: SimulationStep.BUILDING_INFO, label: '建筑信息', icon: Building2 },
  { id: SimulationStep.LOAD_SIMULATION, label: '负荷仿真', icon: Wind },
  { id: SimulationStep.SYSTEM_SCHEME, label: '空调方案', icon: Settings2 },
  { id: SimulationStep.ENERGY_SIMULATION, label: '能耗仿真', icon: Zap },
  { id: SimulationStep.RESULTS_DISPLAY, label: '结果展示', icon: LayoutDashboard },
];

export const Sidebar: React.FC<SidebarProps> = ({ currentStep, completedSteps, onStepClick }) => {
  return (
    <div className="w-64 h-full bg-zinc-900 border-r border-zinc-800 flex flex-col pt-6">
      <div className="px-6 mb-8">
        <div className="flex items-center gap-2 text-blue-500 mb-1">
          <Wind className="w-6 h-6" />
          <span className="font-bold text-xl tracking-tight">HVAC SimPro</span>
        </div>
        <p className="text-xs text-zinc-500 font-medium">专业级暖通能效平台</p>
      </div>

      <nav className="flex-1 px-4 space-y-2">
        {steps.map((step, index) => {
          const isCompleted = completedSteps.includes(step.id);
          const isActive = currentStep === step.id;
          const isPreviousCompleted = index === 0 || completedSteps.includes(steps[index-1].id);

          return (
            <button
              key={step.id}
              onClick={() => isPreviousCompleted && onStepClick(step.id)}
              disabled={!isPreviousCompleted && !isActive}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
                isActive 
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/20" 
                  : isPreviousCompleted
                    ? "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                    : "text-zinc-600 cursor-not-allowed"
              )}
            >
              <div className={cn(
                "p-1 rounded-md",
                isActive ? "bg-blue-500" : "bg-zinc-800 group-hover:bg-zinc-700"
              )}>
                <step.icon className="w-4 h-4" />
              </div>
              <span className="flex-1 text-left">{step.label}</span>
              {isCompleted && !isActive && (
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              )}
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-zinc-800">
        <div className="bg-zinc-800/50 rounded-xl p-4">
          <div className="flex items-center gap-2 text-zinc-300 text-xs font-semibold mb-2 uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            当前状态
          </div>
          <p className="text-zinc-400 text-xs leading-relaxed">
            {currentStep === SimulationStep.PROJECT_SETUP && "请完善项目地理位置及基础信息。"}
            {currentStep === SimulationStep.BUILDING_INFO && "正在维护建筑围护结构及作息计划。"}
            {currentStep === SimulationStep.LOAD_SIMULATION && "基于地理环境进行全年负荷计算。"}
            {currentStep === SimulationStep.SYSTEM_SCHEME && "配置冷热源设备及输配系统。"}
            {currentStep === SimulationStep.ENERGY_SIMULATION && "执行全文能耗平衡计算。"}
            {currentStep === SimulationStep.RESULTS_DISPLAY && "可视化多维度能效分析结果。"}
          </p>
        </div>
      </div>
    </div>
  );
};
