/**
 * Attune.more - Vehicle Context Types
 * Araç durumu, sürüş modu ve sensör soyutlama tanımları
 */

export type DrivingState = 'PARKED' | 'DRIVING' | 'CHARGING';
export type DriverFatigueLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface GeoLocation {
  latitude: number;
  longitude: number;
  label: string;
}

export interface VehicleState {
  state: DrivingState;
  vehicleMoving: boolean;
  vehicleParked: boolean;
  currentSpeed: number; // km/h
  gear: 'P' | 'R' | 'N' | 'D';
  currentLocation: GeoLocation;
  destination?: GeoLocation;
  estimatedTravelTimeToDestMin: number; // dakika
  driverAuthenticated: boolean;
  driverId: string;
  driverName: string;
  driverFatigueSignal: DriverFatigueLevel;
  cabinCameraAvailable: boolean;
  microphoneAvailable: boolean;
  batteryLevelPct: number;
  lastUpdated: string;
}

export interface IVehicleProvider {
  getState(): VehicleState;
  subscribe(callback: (state: VehicleState) => void): () => void;
  setSpeed(speedKmH: number): void;
  toggleDrivingMode(): void;
  setFatigueSignal(level: DriverFatigueLevel): void;
}
