'use client';

import React, { useState } from 'react';
import { WelcomeStep } from './welcome-step';
import { ModelSetupStep } from './model-setup-step';
import { SetupCompleteStep } from './setup-complete-step';

export interface ModelInfo {
  name: string;
  path: string;
  size?: number;
  sizeFormatted?: string;
  quantization?: string;
  isValid: boolean;
  error?: string;
}

export interface SetupWizardProps {
  onComplete: (modelPath: string) => void;
  onSkip?: () => void;
}

export type SetupStep = 'welcome' | 'model' | 'complete';

export function SetupWizard({ onComplete, onSkip }: SetupWizardProps) {
  const [step, setStep] = useState<SetupStep>('welcome');
  const [modelPath, setModelPath] = useState<string | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Manual model detection only - no automatic detection on mount
  // useEffect(() => {
  //   detectModel();
  // }, []);

  const detectModel = async () => {
    setIsDetecting(true);
    setError(null);
    
    try {
      // Request model detection from Electron main process
      if (window.electronAPI) {
        const result = await window.electronAPI.detectModel();
        
        if (result.found) {
          setModelPath(result.path);
          setModelInfo(result.info);
          // Model auto-detected
        } else {
          // No model detected automatically
          setModelPath(null);
          setModelInfo(null);
        }
      } else {
        // Fallback for development/testing
        // No electronAPI available, skipping auto-detection
      }
    } catch (err) {
      // Model detection error
      setError(err instanceof Error ? err.message : 'Failed to detect model');
    } finally {
      setIsDetecting(false);
    }
  };

  const handleWelcomeNext = () => {
    setStep('model');
  };

  const handleModelFound = (path: string, info?: ModelInfo) => {
    setModelPath(path);
    setModelInfo(info || null);
    setError(null);
  };

  const handleModelNext = () => {
    if (modelPath) {
      setStep('complete');
    } else {
      setError('Please select a model before continuing');
    }
  };

  const handleSetupComplete = () => {
    if (modelPath) {
      onComplete(modelPath);
    }
  };

  const handleSkip = () => {
    if (onSkip) {
      onSkip();
    }
  };

  const handleRetryDetection = () => {
    detectModel();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-6">
      <div className="w-full max-w-4xl mx-auto">
        {/* Progress indicator */}
        <div className="flex justify-center mb-8">
          <div className="flex items-center space-x-4">
            <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
              step === 'welcome' 
                ? 'bg-blue-600 border-blue-600 text-white' 
                : step === 'model' || step === 'complete'
                ? 'bg-green-600 border-green-600 text-white'
                : 'border-slate-600 text-slate-600'
            }`}>
              <span className="text-sm font-semibold">1</span>
            </div>
            <div className={`w-16 h-0.5 ${
              step === 'model' || step === 'complete' 
                ? 'bg-green-600' 
                : 'bg-slate-600'
            }`} />
            <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
              step === 'model' 
                ? 'bg-blue-600 border-blue-600 text-white'
                : step === 'complete'
                ? 'bg-green-600 border-green-600 text-white'
                : 'border-slate-600 text-slate-600'
            }`}>
              <span className="text-sm font-semibold">2</span>
            </div>
            <div className={`w-16 h-0.5 ${
              step === 'complete' 
                ? 'bg-green-600' 
                : 'bg-slate-600'
            }`} />
            <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
              step === 'complete'
                ? 'bg-blue-600 border-blue-600 text-white'
                : 'border-slate-600 text-slate-600'
            }`}>
              <span className="text-sm font-semibold">3</span>
            </div>
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Step components */}
        {step === 'welcome' && (
          <WelcomeStep 
            onNext={handleWelcomeNext} 
            onSkip={handleSkip}
          />
        )}
        
        {step === 'model' && (
          <ModelSetupStep
            modelPath={modelPath}
            modelInfo={modelInfo}
            isDetecting={isDetecting}
            onModelFound={handleModelFound}
            onNext={handleModelNext}
            onSkip={handleSkip}
            onRetryDetection={handleRetryDetection}
          />
        )}
        
        {step === 'complete' && (
          <SetupCompleteStep 
            modelPath={modelPath}
            modelInfo={modelInfo}
            onComplete={handleSetupComplete}
            onBack={() => setStep('model')}
          />
        )}

        {/* Navigation help */}
        <div className="mt-8 text-center">
          <p className="text-slate-400 text-sm">
            Need help? Visit our documentation or contact support
          </p>
        </div>
      </div>
    </div>
  );
}