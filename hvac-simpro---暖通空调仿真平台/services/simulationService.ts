
import { AppState, LoadResult, EnergyResult, SimulationStep } from '../types';

/**
 * Mock simulation service for HVAC calculation logic
 */

export const simulateLoad = async (area: number, type: string): Promise<LoadResult> => {
  // Simulate delay
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Heuristic-based mock load calculation
  const baseLoadFactor = type === '商场' ? 180 : type === '办公楼' ? 120 : 100; // W/m2
  const noise = 0.8 + Math.random() * 0.4;
  
  const coolingPeak = (area * baseLoadFactor * noise) / 1000; // kW
  const heatingPeak = coolingPeak * 0.6; // Typical ratio

  // Generate hourly cooling data (simplified to daily profile for one peak day)
  const hourlyCooling = Array.from({ length: 24 }, (_, i) => {
    const factor = Math.max(0.2, Math.sin((i - 6) / 12 * Math.PI));
    return coolingPeak * factor;
  });

  return {
    coolingPeak,
    heatingPeak,
    peakTime: '15:00',
    hourlyCooling,
    hourlyHeating: Array.from({ length: 24 }, () => heatingPeak * 0.5), // Dummy
  };
};

export const simulateEnergy = async (state: AppState): Promise<Record<string, EnergyResult>> => {
  await new Promise(resolve => setTimeout(resolve, 3000));

  const results: Record<string, EnergyResult> = {};
  
  state.schemes.forEach(scheme => {
    const monthlyConsumption = Array.from({ length: 12 }, (_, i) => {
      // Seasonal variation
      const multiplier = Math.max(0.3, Math.sin((i / 11) * Math.PI));
      const totalKWh = state.load!.coolingPeak * 500 * multiplier / scheme.cop;
      return totalKWh;
    });

    const totalKWh = monthlyConsumption.reduce((a, b) => a + b, 0);
    
    results[scheme.id] = {
      monthlyConsumption,
      totalCarbon: totalKWh * 0.5, // 0.5kg CO2 per kWh
      totalCost: totalKWh * 0.8, // 0.8 CNY per kWh
      scop: scheme.cop * 0.85, // Simple SCOP estimate
      breakdown: {
        chiller: totalKWh * 0.6,
        pumps: totalKWh * 0.15,
        towers: totalKWh * 0.1,
        terminal: totalKWh * 0.15,
      }
    };
  });

  return results;
};
