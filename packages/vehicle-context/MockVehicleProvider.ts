import { VehicleState, IVehicleProvider, DriverFatigueLevel } from './types';

/**
 * MockVehicleProvider
 * Gerçek araç üreticisi API'leri entegre edilmeden önce araç telemetrisini ve durumunu simüle eder.
 * UI üzerinden tek tıkla Park (0 km/s) ve Sürüş (85 km/s) modları arasında geçiş sağlar.
 */
export class MockVehicleProvider implements IVehicleProvider {
  private state: VehicleState;
  private listeners: Set<(state: VehicleState) => void> = new Set();

  constructor(initialParked: boolean = true) {
    this.state = {
      state: initialParked ? 'PARKED' : 'DRIVING',
      vehicleMoving: !initialParked,
      vehicleParked: initialParked,
      currentSpeed: initialParked ? 0 : 85,
      gear: initialParked ? 'P' : 'D',
      currentLocation: {
        latitude: 40.9912,
        longitude: 29.0234,
        label: 'Kadıköy, İstanbul'
      },
      destination: {
        latitude: 41.0082,
        longitude: 28.9784,
        label: 'Levent, İstanbul'
      },
      estimatedTravelTimeToDestMin: 22,
      driverAuthenticated: true,
      driverId: 'tru-user-001',
      driverName: 'Ahmet Yılmaz',
      driverFatigueSignal: 'LOW',
      cabinCameraAvailable: true,
      microphoneAvailable: true,
      batteryLevelPct: 78,
      lastUpdated: new Date().toISOString()
    };
  }

  public getState(): VehicleState {
    return { ...this.state };
  }

  public subscribe(callback: (state: VehicleState) => void): () => void {
    this.listeners.add(callback);
    callback(this.getState());
    return () => {
      this.listeners.delete(callback);
    };
  }

  public setSpeed(speedKmH: number): void {
    const isMoving = speedKmH > 0;
    this.state = {
      ...this.state,
      currentSpeed: speedKmH,
      vehicleMoving: isMoving,
      vehicleParked: !isMoving,
      gear: isMoving ? 'D' : 'P',
      state: isMoving ? 'DRIVING' : 'PARKED',
      lastUpdated: new Date().toISOString()
    };
    this.notify();
  }

  public toggleDrivingMode(): void {
    if (this.state.vehicleParked) {
      this.setSpeed(75);
    } else {
      this.setSpeed(0);
    }
  }

  public setFatigueSignal(level: DriverFatigueLevel): void {
    this.state = {
      ...this.state,
      driverFatigueSignal: level,
      lastUpdated: new Date().toISOString()
    };
    this.notify();
  }

  private notify(): void {
    const snapshot = this.getState();
    this.listeners.forEach((listener) => listener(snapshot));
  }
}

// Singleton global mock provider instance
export const mockVehicleInstance = new MockVehicleProvider(true);
