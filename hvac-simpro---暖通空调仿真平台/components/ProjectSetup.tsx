
import React from 'react';
import { ProjectInfo } from '../types';
import { MapPin, Building, Globe, CloudSun, ClipboardCheck } from 'lucide-react';

interface ProjectSetupProps {
  data: ProjectInfo;
  onChange: (data: ProjectInfo) => void;
}

const locations = ['北京', '上海', '广州', '深圳', '成都', '武汉', '西安', '沈阳'];
const buildingTypes = ['办公楼', '商场', '酒店', '医院', '学校', '公寓'];


export const ProjectSetup: React.FC<ProjectSetupProps> = ({ data, onChange }) => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <ClipboardCheck className="w-6 h-6 text-blue-500" />
          第一步：工程信息管理
        </h2>
        <p className="text-zinc-400">设置项目的地理位置、所属气候区以及建筑类型，系统将自动匹配气象参数。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            地理定位
          </h3>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-400">项目名称</label>
              <input
                type="text"
                value={data.name}
                onChange={(e) => onChange({ ...data, name: e.target.value })}
                placeholder="请输入工程名称..."
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-400">项目地点</label>
              <select
                value={data.location}
                onChange={(e) => onChange({ ...data, location: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
              >
                <option value="">请选择城市...</option>
                {locations.map(loc => <option key={loc} value={loc}>{loc}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
            <Building className="w-4 h-4" />
            建筑分类
          </h3>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-400">建筑类型</label>
              <select
                value={data.type}
                onChange={(e) => onChange({ ...data, type: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
              >
                <option value="">请选择类型...</option>
                {buildingTypes.map(type => <option key={type} value={type}>{type}</option>)}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-400">气候分区</label>
              <div className="flex items-center gap-3 p-3 bg-zinc-950/50 rounded-lg border border-zinc-800/50 text-xs text-zinc-500">
                <Globe className="w-4 h-4" />
                <span>自动识别：根据地点匹配气候区（如：夏热冬冷地区）</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {data.location && (
        <div className="bg-zinc-900/40 border border-blue-500/20 rounded-2xl p-6 animate-in fade-in zoom-in duration-500">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider flex items-center gap-2">
              <CloudSun className="w-4 h-4" />
              气象预测包预览 ({data.location})
            </h3>
            <span className="text-[10px] bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded uppercase font-bold tracking-widest">
              CSY 典型气象年
            </span>
          </div>
          
          <div className="h-32 flex items-end gap-1 px-2">
            {[...Array(24)].map((_, i) => {
              const height = (Math.sin((i - 6) / 12 * Math.PI) + 1) * 50 + 20;
              return (
                <div 
                  key={i} 
                  className="flex-1 bg-gradient-to-t from-blue-600/40 to-blue-400/10 rounded-t-sm relative group"
                  style={{ height: `${height}%` }}
                >
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[8px] text-zinc-500 opacity-0 group-hover:opacity-100 transition-opacity">
                    {Math.round(height/2)}°C
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between text-[10px] text-zinc-600 mt-2 px-1 font-mono">
            <span>00:00</span>
            <span>06:00</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>24:00</span>
          </div>
        </div>
      )}
    </div>
  );
};
