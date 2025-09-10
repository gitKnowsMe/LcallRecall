'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Brain, Shield, Zap, HardDrive } from 'lucide-react';

export interface WelcomeStepProps {
  onNext: () => void;
  onSkip?: () => void;
}

export function WelcomeStep({ onNext, onSkip }: WelcomeStepProps) {
  return (
    <div className="text-center space-y-8">
      {/* Main heading */}
      <div className="space-y-4">
        <div className="flex justify-center">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center">
            <Brain className="w-12 h-12 text-white" />
          </div>
        </div>
        
        <h1 className="text-4xl font-bold text-white">
          Welcome to LocalRecall
        </h1>
        
        <p className="text-xl text-slate-300 max-w-2xl mx-auto">
          Your private AI-powered document analysis and question-answering system. 
          Let's get you set up in just a few minutes.
        </p>
      </div>

      {/* Feature highlights */}
      <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-3">
            <div className="flex justify-center mb-2">
              <Shield className="w-8 h-8 text-green-500" />
            </div>
            <CardTitle className="text-lg text-white text-center">
              100% Private
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-slate-300 text-sm text-center">
              All processing happens locally on your machine. Your documents never leave your device.
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-3">
            <div className="flex justify-center mb-2">
              <Zap className="w-8 h-8 text-yellow-500" />
            </div>
            <CardTitle className="text-lg text-white text-center">
              AI-Powered
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-slate-300 text-sm text-center">
              Uses Microsoft's Phi-2 model for intelligent document analysis and question answering.
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-3">
            <div className="flex justify-center mb-2">
              <HardDrive className="w-8 h-8 text-blue-500" />
            </div>
            <CardTitle className="text-lg text-white text-center">
              No Internet Required
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-slate-300 text-sm text-center">
              Works completely offline. No API keys, subscriptions, or internet connection needed.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Setup overview */}
      <Card className="bg-slate-800/30 border-slate-700 max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle className="text-white text-center">What we'll set up</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center space-x-3 text-slate-300">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            <span>Detect or help you install the Phi-2 AI model (~1.4GB)</span>
          </div>
          <div className="flex items-center space-x-3 text-slate-300">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            <span>Configure your document storage location</span>
          </div>
          <div className="flex items-center space-x-3 text-slate-300">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            <span>Create your LocalRecall account (username only)</span>
          </div>
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
        <Button
          onClick={onNext}
          size="lg"
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 text-lg"
        >
          Get Started
        </Button>
        
        {onSkip && (
          <Button
            onClick={onSkip}
            variant="ghost"
            size="lg"
            className="text-slate-400 hover:text-slate-300 px-8 py-3"
          >
            Skip Setup (Advanced Users)
          </Button>
        )}
      </div>

      {/* System requirements note */}
      <div className="mt-8 p-4 bg-slate-800/30 border border-slate-700 rounded-lg max-w-2xl mx-auto">
        <h3 className="text-sm font-semibold text-white mb-2">System Requirements</h3>
        <ul className="text-xs text-slate-400 space-y-1">
          <li>• macOS 10.15 or later</li>
          <li>• 4GB RAM minimum (8GB recommended)</li>
          <li>• 2GB free disk space for AI model</li>
          <li>• Apple Silicon (M1/M2) recommended for best performance</li>
        </ul>
      </div>
    </div>
  );
}