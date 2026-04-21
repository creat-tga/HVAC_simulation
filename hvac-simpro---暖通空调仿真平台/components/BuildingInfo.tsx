
import React, { useState } from 'react';
import { BuildingEnvelope, Schedule } from '../types';
import { 
  Box, 
  Layers, 
  Clock, 
  Users, 
  Zap, 
  Sun, 
  ArrowRight,
  Maximize2
} from 'lucide-react';
import { cn } from '../lib/utils';

interface BuildingInfoProps {
  data: BuildingEnvelope;
  onChange: (data: BuildingEnvelope) => void;
}

export const BuildingInfo: React.FC<BuildingInfoProps> = ({ data, onChange }) => {
  const [activeTab, setActiveTab] = useState<'envelope' | 'schedules'>('envelope');

  return (
    <div className="flex flex-col h-full space-y-6 animate-in fade-in duration-500">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <Layers className="w-6 h-6 text-blue-500" />
          第二步：维护建筑信息
        </h2>
        <p className="text-zinc-400">详细定义建筑的热工参数以及各区域的人员、照明、设备运行作息。</p>
      </div>

      <div className="flex gap-1 p-1 bg-zinc-900 border border-zinc-800 rounded-xl w-fit">
        <button
          onClick={() => setActiveTab('envelope')}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2",
            activeTab === 'envelope' ? "bg-zinc-800 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          <Box className="w-4 h-4" />
          围护结构参数
        </button>
        <button
          onClick={() => setActiveTab('schedules')}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2",
            activeTab === 'schedules' ? "bg-zinc-800 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          <Clock className="w-4 h-4" />
          运营作息计划
        </button>
      </div>

      <div className="flex-1 min-h-[500px] flex gap-6">
        {/* Left Side: Parameters or List */}
        <div className="w-full">
          {activeTab === 'envelope' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                { label: '建筑面积 (㎡)', key: 'area', icon: Maximize2, min: 0, max: 1000000 },
                { label: '层高 (m)', key: 'height', icon: Layers, min: 2, max: 20 },
                { label: '墙体传热系数 U-Value', key: 'wallUValue', icon: Box, step: 0.1 },
                { label: '窗墙比 Window Ratio', key: 'windowRatio', icon: Sun, step: 0.05, max: 1 },
                { label: '人员密度 (㎡/人)', key: 'occupancyDensity', icon: Users, min: 0 },
              ].map((field) => (
                <div key={field.key} className="bg-zinc-900/50 border border-zinc-800 p-6 rounded-2xl space-y-4 hover:border-zinc-700 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-zinc-800 rounded-lg">
                      <field.icon className="w-4 h-4 text-zinc-400" />
                    </div>
                    <label className="text-sm font-medium text-zinc-300">{field.label}</label>
                  </div>
                  <input
                    type="number"
                    value={(data as any)[field.key]}
                    onChange={(e) => onChange({ ...data, [field.key]: parseFloat(e.target.value) })}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-lg font-mono text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 transition-all"
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6">
              {data.schedules.map((schedule) => (
                <div key={schedule.id} className="bg-zinc-900/50 border border-zinc-800 p-6 rounded-2xl space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "p-2 rounded-lg",
                        schedule.type === 'Occupancy' ? "bg-orange-500/10 text-orange-500" :
                        schedule.type === 'Lighting' ? "bg-yellow-500/10 text-yellow-500" :
                        "bg-blue-500/10 text-blue-500"
                      )}>
                        {schedule.type === 'Occupancy' ? <Users className="w-5 h-5" /> :
                         schedule.type === 'Lighting' ? <Sun className="w-5 h-5" /> :
                         <Zap className="w-5 h-5" />}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-white">{schedule.name}</h4>
                        <p className="text-[10px] text-zinc-500 uppercase tracking-widest">{schedule.type} Schedule</p>
                      </div>
                    </div>
                  </div>

                  {/* Heatmap visualization for schedule */}
                  <div className="space-y-2">
                    <div className="flex h-12 gap-1">
                      {schedule.hourlyValues.map((val, i) => (
                        <div
                          key={i}
                          className="flex-1 rounded-sm relative group"
                          style={{ 
                            backgroundColor: schedule.type === 'Occupancy' 
                              ? `rgba(249, 115, 22, ${val})` 
                              : schedule.type === 'Lighting'
                                ? `rgba(234, 179, 8, ${val})`
                                : `rgba(59, 130, 246, ${val})`
                          }}
                        >
                          <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-white/20 transition-opacity flex items-center justify-center text-[8px] font-bold text-white">
                            {Math.round(val * 100)}%
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-between text-[10px] text-zinc-600 font-mono px-1">
                      <span>0h</span>
                      <span>12h</span>
                      <span>24h</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
