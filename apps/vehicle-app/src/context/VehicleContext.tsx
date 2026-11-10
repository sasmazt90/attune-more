'use client';
import {apiFetch as fetch} from '../utils/localBackend';
import {LOCAL_API_BASE} from '../utils/previewLocalApi';


import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { mockVehicleInstance } from '@packages/vehicle-context/MockVehicleProvider';
import { VehicleState } from '@packages/vehicle-context/types';
import { localBackend } from '../utils/localBackend';
import { streamFocusTracker, vehiclePollInterval } from '../utils/vehiclePolling';

interface VehicleContextType {
  state: VehicleState;
  toggleDrivingMode: () => void;
  setSpeed: (speed: number) => void;
  isParked: boolean;
  isMoving: boolean;
  canAccessVisualModules: boolean;
  syncStatus: 'loading' | 'synced' | 'updating' | 'failed';
  syncError: string | null;
}

const VehicleContext = createContext<VehicleContextType | undefined>(undefined);

export const VehicleContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [vehicleState, setVehicleState] = useState<VehicleState>(mockVehicleInstance.getState());
  const [syncStatus, setSyncStatus] = useState<VehicleContextType['syncStatus']>('loading');
  const [syncError, setSyncError] = useState<string | null>(null);
  const mounted = useRef(false);
  const mutationPending = useRef(false);
  const requestId = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const applyState = useCallback((state: VehicleState) => {
    if (!Number.isFinite(state.currentSpeed) || state.currentSpeed < 0 ||
        state.vehicleMoving !== (state.currentSpeed > 0) || state.vehicleParked === state.vehicleMoving) {
      throw new Error('Geçersiz araç durumu');
    }
    setVehicleState(previous => previous.lastUpdated === state.lastUpdated ? previous : state);
    setSyncStatus('synced');
    setSyncError(null);
  }, []);

  useEffect(() => {
    mounted.current = true;
    let reading = false;
    const refresh = async () => {
      if (mutationPending.current || reading) return;
      reading = true;
      const id = ++requestId.current;
      const controller = new AbortController();
      activeRequest.current = controller;
      const deadline = setTimeout(() => controller.abort(), 5000);
      try {
        const response = await fetch(localBackend('/api/vehicle/state'), { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Araç durumu alınamadı');
        const state = await response.json();
        if (mounted.current && id === requestId.current) applyState(state);
      } catch {
        if (mounted.current && id === requestId.current) {
          setSyncStatus('failed');
          setSyncError('Araç durumu doğrulanamıyor. Görsel kontroller güvenlik için kilitlendi.');
        }
      } finally {
        reading = false;
        clearTimeout(deadline);
      }
    };
    // 1 s normally; 250 ms while app audio owns output, so a driving change stops that audio sooner.
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => { await refresh(); if (mounted.current) schedule(); }, vehiclePollInterval(streams.owners.size));
    };
    const streams = streamFocusTracker(() => { void refresh(); schedule(); });
    void refresh();
    schedule();
    window.addEventListener('focus', refresh);
    window.addEventListener('attune-stream-focus', streams.listener);
    return () => {
      mounted.current = false;
      requestId.current += 1;
      activeRequest.current?.abort();
      clearTimeout(timer);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('attune-stream-focus', streams.listener);
    };
  }, [applyState]);

  const setSpeed = async (speed: number) => {
    if (mutationPending.current || !Number.isFinite(speed) || speed < 0) return;
    mutationPending.current = true;
    const id = ++requestId.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const deadline = setTimeout(() => controller.abort(), 5000);
    // Lock immediately; parked features wait for backend acknowledgement.
    setSyncStatus('updating');
    setSyncError(null);
    try {
      const response = await fetch(localBackend('/api/vehicle/speed'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speedKmH: speed }), signal: controller.signal
      });
      if (!response.ok) throw new Error('Araç durumu güncellenemedi');
      const state = await response.json();
      if (mounted.current && id === requestId.current) applyState(state);
    } catch {
      if (mounted.current && id === requestId.current) {
        setSyncStatus('failed');
        setSyncError('Araç durumu güncellenemedi. Görsel kontroller güvenlik için kilitlendi.');
      }
    } finally {
      mutationPending.current = false;
      clearTimeout(deadline);
    }
  };
  const toggleDrivingMode = () => { void setSpeed(vehicleState.vehicleParked ? 75 : 0); };

  const isParked = vehicleState.vehicleParked && syncStatus === 'synced';
  const isMoving = vehicleState.vehicleMoving;
  const canAccessVisualModules = isParked;

  return (
    <VehicleContext.Provider
      value={{
        state: vehicleState,
        toggleDrivingMode,
        setSpeed,
        isParked,
        isMoving,
        canAccessVisualModules,
        syncStatus,
        syncError,
      }}
    >
      {children}
    </VehicleContext.Provider>
  );
};

export const useVehicle = (): VehicleContextType => {
  const context = useContext(VehicleContext);
  if (!context) {
    throw new Error('useVehicle, VehicleContextProvider içinde kullanılmalıdır.');
  }
  return context;
};
