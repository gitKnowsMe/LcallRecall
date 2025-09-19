'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { desktopAPI } from '@/lib/desktop-api';

interface SetupState {
  hasModel: boolean;
  modelPath: string | null;
  isFirstRun: boolean;
  isChecking: boolean;
}

interface SetupContextType {
  setupState: SetupState;
  checkSetupStatus: () => Promise<void>;
  completeSetup: (modelPath: string) => Promise<void>;
  skipSetup: () => void;
  needsSetup: boolean;
}

const SetupContext = createContext<SetupContextType | undefined>(undefined);

export function useSetup() {
  const context = useContext(SetupContext);
  if (context === undefined) {
    throw new Error('useSetup must be used within a SetupProvider');
  }
  return context;
}

interface SetupProviderProps {
  children: ReactNode;
}

export function SetupProvider({ children }: SetupProviderProps) {
  const [setupState, setSetupState] = useState<SetupState>({
    hasModel: false,
    modelPath: null,
    isFirstRun: false,
    isChecking: false, // Start with false to prevent hanging
  });

  const checkSetupStatus = async () => {
    try {

      // Always resolve quickly to show UI immediately
      setSetupState(prev => ({ ...prev, isChecking: false }));

      // Check if we're in desktop app (has model detection capability)
      if (!desktopAPI.isDesktopApp()) {
        setSetupState(prev => ({
          ...prev,
          hasModel: true, // Assume web version doesn't need model setup
          isFirstRun: false,
          isChecking: false,
        }));
        return;
      }

      // Check if setup has been completed before
      const hasCompletedSetup = localStorage.getItem('localrecall_setup_completed');
      const savedModelPath = localStorage.getItem('localrecall_model_path');


      // Set state immediately - no hanging
      const newSetupState: SetupState = {
        hasModel: !!hasCompletedSetup && !!savedModelPath,
        modelPath: savedModelPath,
        isFirstRun: !hasCompletedSetup,
        isChecking: false,
      };

      setSetupState(newSetupState);

    } catch (error) {
      console.error('Setup status check failed:', error);

      // On error, assume first run if no setup flag exists
      const hasCompletedSetup = localStorage.getItem('localrecall_setup_completed');
      setSetupState(prev => ({
        ...prev,
        hasModel: false,
        modelPath: null,
        isFirstRun: !hasCompletedSetup,
        isChecking: false,
      }));
    }
  };

  const completeSetup = async (modelPath: string) => {
    try {
      // Validate the model path
      if (desktopAPI.isDesktopApp()) {
        const validation = await desktopAPI.validateModel(modelPath);
        if (!validation.valid) {
          throw new Error('Selected model is not valid');
        }
      }

      // Mark setup as completed
      localStorage.setItem('localrecall_setup_completed', 'true');
      localStorage.setItem('localrecall_model_path', modelPath);

      // Update state
      setSetupState(prev => ({
        ...prev,
        hasModel: true,
        modelPath: modelPath,
        isFirstRun: false,
      }));

      // Setup completed successfully
    } catch (error) {
      console.error('Setup completion failed:', error);
      throw error;
    }
  };

  const skipSetup = () => {
    // Mark setup as completed even without model (advanced users)
    localStorage.setItem('localrecall_setup_completed', 'true');
    
    setSetupState(prev => ({
      ...prev,
      isFirstRun: false,
    }));

    // Setup skipped by user
  };

  // Check setup status on mount
  useEffect(() => {
    checkSetupStatus();
  }, []);

  const needsSetup = setupState.isFirstRun && desktopAPI.isDesktopApp();

  const value: SetupContextType = {
    setupState,
    checkSetupStatus,
    completeSetup,
    skipSetup,
    needsSetup,
  };

  return <SetupContext.Provider value={value}>{children}</SetupContext.Provider>;
}