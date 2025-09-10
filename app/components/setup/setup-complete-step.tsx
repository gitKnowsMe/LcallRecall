'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  CheckCircle2, 
  Sparkles, 
  FileText, 
  MessageSquare,
  ArrowRight,
  Brain,
  HardDrive
} from 'lucide-react';
import type { ModelInfo } from './setup-wizard';

export interface SetupCompleteStepProps {
  modelPath: string | null;
  modelInfo: ModelInfo | null;
  onComplete: () => void;
  onBack: () => void;
}

export function SetupCompleteStep({ 
  modelPath, 
  modelInfo, 
  onComplete, 
  onBack 
}: SetupCompleteStepProps) {
  return (
    <div className="text-center space-y-8">
      {/* Success header */}
      <div className="space-y-4">
        <div className="flex justify-center">
          <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center">
            <CheckCircle2 className="w-12 h-12 text-white" />
          </div>
        </div>
        
        <h2 className="text-4xl font-bold text-white">
          Setup Complete!
        </h2>
        
        <p className="text-xl text-slate-300 max-w-2xl mx-auto">
          LocalRecall is ready to help you analyze your documents with AI-powered insights.
        </p>
      </div>

      {/* Configuration summary */}
      <Card className="bg-slate-800/50 border-slate-700 max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-center space-x-2">
            <Sparkles className="w-5 h-5 text-yellow-500" />
            <span>Your Configuration</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {modelPath && modelInfo && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">AI Model:</span>
                <Badge variant="secondary" className="bg-green-500/20 text-green-400">
                  Ready
                </Badge>
              </div>
              
              <div className="bg-slate-900/50 rounded-lg p-3 space-y-2">
                <div className="flex items-center space-x-2">
                  <Brain className="w-4 h-4 text-purple-400" />
                  <span className="text-slate-300 text-sm font-medium">{modelInfo.name}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <HardDrive className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-400 text-xs">{modelInfo.sizeFormatted || 'Size unknown'}</span>
                  {modelInfo.quantization && (
                    <Badge variant="outline" className="text-xs">
                      {modelInfo.quantization}
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div className="border-t border-slate-700 pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-300">Storage Location:</span>
              <Badge variant="outline" className="text-slate-400">
                ~/Library/Application Support/LocalRecall
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-slate-300">Privacy Mode:</span>
              <Badge variant="secondary" className="bg-green-500/20 text-green-400">
                100% Local
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* What's next */}
      <Card className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border-blue-500/20 max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle className="text-white">What you can do next</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <FileText className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-white font-medium">Upload Documents</h3>
                <p className="text-slate-300 text-sm">
                  Add PDFs, text files, and other documents to create your knowledge base
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-purple-600 rounded-lg flex items-center justify-center">
                <MessageSquare className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-white font-medium">Ask Questions</h3>
                <p className="text-slate-300 text-sm">
                  Chat with your documents using natural language queries
                </p>
              </div>
            </div>
          </div>
          
          <div className="mt-6 p-4 bg-slate-800/50 rounded-lg">
            <p className="text-slate-300 text-sm">
              <strong className="text-white">Pro Tip:</strong> Start by uploading a few documents, 
              then try asking questions like "Summarize the key points" or "What are the main findings?"
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
        <Button
          onClick={onComplete}
          size="lg"
          className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-3 text-lg"
        >
          <ArrowRight className="w-5 h-5 mr-2" />
          Start Using LocalRecall
        </Button>
        
        <Button
          onClick={onBack}
          variant="ghost"
          size="lg"
          className="text-slate-400 hover:text-slate-300 px-8 py-3"
        >
          Back to Model Setup
        </Button>
      </div>

      {/* Additional help */}
      <div className="mt-8 p-4 bg-slate-800/30 border border-slate-700 rounded-lg max-w-2xl mx-auto">
        <h3 className="text-sm font-semibold text-white mb-2">Getting Started Tips</h3>
        <ul className="text-xs text-slate-400 space-y-1 text-left">
          <li>• Upload documents using the "+" button or drag-and-drop</li>
          <li>• Wait for processing to complete before asking questions</li>
          <li>• Use specific questions for better AI responses</li>
          <li>• Your data stays private - no internet connection required</li>
          <li>• Check the Memory section to see all uploaded documents</li>
        </ul>
      </div>
    </div>
  );
}