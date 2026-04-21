
/**
 * Core types for the HVAC Simulation Platform
 */

export enum SimulationStep {
  PROJECT_SETUP = 'PROJECT_SETUP',
  BUILDING_INFO = 'BUILDING_INFO',
  LOAD_SIMULATION = 'LOAD_SIMULATION',
  SYSTEM_SCHEME = 'SYSTEM_SCHEME',
  ENERGY_SIMULATION = 'ENERGY_SIMULATION',
  RESULTS_DISPLAY = 'RESULTS_DISPLAY',
}

export interface ProjectInfo {
  name: string;
  location: string;
  type: string;
  climateZone: string;
  weatherData?: any;
}

export interface BuildingEnvelope {
  area: number;
  height: number;
  orientation: string;
  wallUValue: number;
  windowRatio: number;
  occupancyDensity: number;
  schedules: Schedule[];
}

export interface Schedule {
  id: string;
  name: string;
  type: 'Occupancy' | 'Lighting' | 'Equipment';
  hourlyValues: number[]; // 24 values, 0-1
}

export interface LoadResult {
  coolingPeak: number; // kW
  heatingPeak: number; // kW
  peakTime: string;
  hourlyCooling: number[]; // 8760 values (simulated as monthly/daily averages for performance)
  hourlyHeating: number[];
}

export interface HVACScheme {
  id: string;
  name: string;
  description: string;
  chillerType: string;
  coolingCapacity: number; // kW
  cop: number;
  pumps: number;
  towers: number;
  controlStrategy: string;
  investment: number; // CNY
}

export interface EnergyResult {
  monthlyConsumption: number[]; // 12 values
  totalCarbon: number;
  totalCost: number;
  scop: number;
  breakdown: {
    chiller: number;
    pumps: number;
    towers: number;
    terminal: number;
  };
}

export interface AppState {
  currentStep: SimulationStep;
  project: ProjectInfo;
  building: BuildingEnvelope;
  load: LoadResult | null;
  schemes: HVACScheme[];
  results: Record<string, EnergyResult>; // Map scheme ID to results
  isCalculating: boolean;
}
