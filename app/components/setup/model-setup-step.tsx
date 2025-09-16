'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  CheckCircle2, 
  AlertCircle, 
  Download, 
  FolderOpen, 
  ExternalLink,
  RefreshCw,
  Brain,
  HardDrive,
  Loader2
} from 'lucide-react';
import type { ModelInfo } from './setup-wizard';

export interface ModelSetupStepProps {
  modelPath: string | null;
  modelInfo: ModelInfo | null;
  isDetecting: boolean;
  onModelFound: (path: string, info?: ModelInfo) => void;
  onNext: () => void;
  onSkip?: () => void;
  onRetryDetection: () => void;
}

export function ModelSetupStep({ 
  modelPath, 
  modelInfo, 
  isDetecting,
  onModelFound, 
  onNext, 
  onSkip,
  onRetryDetection 
}: ModelSetupStepProps) {
  const [showDownloadInstructions, setShowDownloadInstructions] = useState(false);
  const [isSelectingFile, setIsSelectingFile] = useState(false);

  const handleSelectFile = async () => {
    setIsSelectingFile(true);
    
    try {
      if (window.electronAPI) {
        const result = await window.electronAPI.selectModelFile();
        
        if (result.success && result.path) {
          const info = result.info || {
            name: result.path.split('/').pop() || 'Unknown',
            path: result.path,
            isValid: true
          };
          onModelFound(result.path, info);
        }
      }
    } catch (error) {
      console.error('File selection error:', error);
    } finally {
      setIsSelectingFile(false);
    }
  };

  const handleDownloadClick = () => {
    if (window.electronAPI) {
      window.electronAPI.openExternal('https://huggingface.co/microsoft/phi-2/tree/main');
    }
    setShowDownloadInstructions(true);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-4">
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-600 rounded-2xl flex items-center justify-center">
            <Brain className="w-10 h-10 text-white" />
          </div>
        </div>
        
        <h2 className="text-3xl font-bold text-white">
          AI Model Setup
        </h2>
        
        <p className="text-lg text-slate-300 max-w-2xl mx-auto">
          LocalRecall needs the Phi-2 AI model to answer questions about your documents. 
          Let's find or download it.
        </p>
      </div>

      {/* Auto-detection status */}
      <Card className="bg-slate-800/50 border-slate-700 max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle className="text-white flex items-center space-x-2">
            {isDetecting ? (
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
            ) : modelPath ? (
              <CheckCircle2 className="w-5 h-5 text-green-500" />
            ) : (
              <AlertCircle className="w-5 h-5 text-yellow-500" />
            )}
            <span>Model Detection</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isDetecting ? (
            <div className="text-slate-300">
              <p>Scanning common locations for Phi-2 model...</p>
              <div className="mt-2 text-sm text-slate-400">
                This may take a few moments...
              </div>
            </div>
          ) : modelPath && modelInfo ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-green-400 font-medium">✅ Model Found!</span>
                <Badge variant="secondary" className="bg-green-500/20 text-green-400">
                  {modelInfo.sizeFormatted || 'Unknown size'}
                </Badge>
              </div>
              
              <div className="bg-slate-900/50 rounded-lg p-3 space-y-2">
                <div className="flex items-center space-x-2">
                  <HardDrive className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-300 text-sm font-medium">{modelInfo.name}</span>
                </div>
                <div className="text-xs text-slate-400 font-mono break-all">
                  {modelInfo.path}
                </div>
                {modelInfo.quantization && (
                  <Badge variant="outline" className="text-xs">
                    {modelInfo.quantization} Quantization
                  </Badge>
                )}
              </div>
              
              <Button
                onClick={onRetryDetection}
                variant="ghost"
                size="sm"
                className="text-slate-400 hover:text-slate-300"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Scan Again
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-yellow-400">No Phi-2 model found automatically</p>
              <p className="text-slate-300 text-sm">
                We searched common locations but didn't find a Phi-2 GGUF model. 
                You can download one or select an existing file.
              </p>
              
              <Button
                onClick={onRetryDetection}
                variant="ghost"
                size="sm"
                className="text-slate-400 hover:text-slate-300"
                disabled={isDetecting}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Try Again
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action options */}
      <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        {/* Download option */}
        <Card className="bg-slate-800/50 border-slate-700 hover:bg-slate-800/70 transition-colors">
          <CardHeader>
            <CardTitle className="text-white flex items-center space-x-2">
              <Download className="w-5 h-5 text-blue-500" />
              <span>Download Phi-2</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-slate-300 text-sm">
              Download the recommended Phi-2 model from Hugging Face. 
              This is a one-time download of about 1.4GB.
            </p>
            
            <div className="space-y-2 text-xs text-slate-400">
              <div>• File: phi-2.Q4_K_M.gguf</div>
              <div>• Size: ~1.4GB</div>
              <div>• Provider: Microsoft/Hugging Face</div>
              <div>• Quality: 4-bit quantized (good balance)</div>
            </div>
            
            <Button
              onClick={handleDownloadClick}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              Open Download Page
            </Button>
          </CardContent>
        </Card>

        {/* Browse option */}
        <Card className="bg-slate-800/50 border-slate-700 hover:bg-slate-800/70 transition-colors">
          <CardHeader>
            <CardTitle className="text-white flex items-center space-x-2">
              <FolderOpen className="w-5 h-5 text-green-500" />
              <span>Select Existing Model</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-slate-300 text-sm">
              Already have a Phi-2 model file? Browse your computer 
              to select the GGUF file.
            </p>
            
            <div className="space-y-2 text-xs text-slate-400">
              <div>• Must be a .gguf file</div>
              <div>• Should contain "phi-2" in filename</div>
              <div>• Recommended: Q4_K_M quantization</div>
              <div>• Minimum size: 100MB</div>
            </div>
            
            <Button
              onClick={handleSelectFile}
              variant="outline"
              className="w-full border-slate-600 hover:bg-slate-700"
              disabled={isSelectingFile}
            >
              {isSelectingFile ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <FolderOpen className="w-4 h-4 mr-2" />
              )}
              {isSelectingFile ? 'Selecting...' : 'Browse Files'}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Download instructions (if shown) */}
      {showDownloadInstructions && (
        <Card className="bg-blue-500/10 border-blue-500/20 max-w-3xl mx-auto">
          <CardHeader>
            <CardTitle className="text-blue-400">Download Instructions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="space-y-2 text-slate-300 text-sm">
              <li className="flex items-start space-x-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-600 text-white text-xs rounded-full flex items-center justify-center mt-0.5">1</span>
                <span>Click "phi-2.Q4_K_M.gguf" on the Hugging Face page to download</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-600 text-white text-xs rounded-full flex items-center justify-center mt-0.5">2</span>
                <span>Wait for the download to complete (~1.4GB)</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-600 text-white text-xs rounded-full flex items-center justify-center mt-0.5">3</span>
                <span>Move the file to: <code className="bg-slate-800 px-2 py-1 rounded text-xs">~/Library/Application Support/LocalRecall/models/</code></span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-600 text-white text-xs rounded-full flex items-center justify-center mt-0.5">4</span>
                <span>Click "Try Again" above to detect the downloaded model</span>
              </li>
            </ol>
            
            <div className="mt-4 p-3 bg-slate-800/50 rounded-lg">
              <p className="text-slate-400 text-xs">
                <strong>Note:</strong> The download may take 5-15 minutes depending on your internet connection. 
                The model will be cached locally and only needs to be downloaded once.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Navigation buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
        <Button
          onClick={onNext}
          disabled={!modelPath}
          size="lg"
          className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {modelPath ? 'Continue Setup' : 'Select a Model First'}
        </Button>
        
        {onSkip && (
          <Button
            onClick={onSkip}
            variant="ghost"
            size="lg"
            className="text-slate-400 hover:text-slate-300 px-8 py-3"
          >
            Skip for Now
          </Button>
        )}
      </div>

      {!modelPath && (
        <div className="text-center text-slate-400 text-sm">
          A Phi-2 model is required for LocalRecall to function properly
        </div>
      )}
    </div>
  );
}