const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class ModelManager {
  static commonPaths = [
    // LocalRecall specific paths
    path.join(os.homedir(), 'Library', 'Application Support', 'LocalRecall', 'models'),
    
    // Common AI model directories
    path.join(os.homedir(), 'local AI', 'models'),
    path.join(os.homedir(), 'Documents', 'AI Models'),
    path.join(os.homedir(), 'Downloads'),
    
    // System-wide locations
    '/opt/homebrew/models',
    '/usr/local/models',
    
    // HuggingFace cache locations
    path.join(os.homedir(), '.cache', 'huggingface', 'hub'),
    path.join(os.homedir(), '.cache', 'modelscope', 'hub'),
  ];

  /**
   * Auto-detect Phi-2 model in common locations
   * @returns {Promise<string|null>} Path to detected model or null
   */
  static async detectModel() {
    console.log('🔍 Scanning for Phi-2 model...');
    
    for (const searchPath of this.commonPaths) {
      try {
        const expandedPath = this.expandPath(searchPath);
        console.log(`   Checking: ${expandedPath}`);
        
        const modelPath = await this.scanDirectory(expandedPath);
        if (modelPath) {
          console.log(`✅ Found Phi-2 model: ${modelPath}`);
          return modelPath;
        }
      } catch (error) {
        // Directory doesn't exist or no permissions, continue searching
        console.log(`   Skipped: ${searchPath} (${error.message})`);
      }
    }
    
    console.log('❌ No Phi-2 model found in common locations');
    return null;
  }

  /**
   * Scan a directory for Phi-2 GGUF files
   * @param {string} dirPath - Directory to scan
   * @returns {Promise<string|null>} Path to model file or null
   */
  static async scanDirectory(dirPath) {
    try {
      const files = await fs.readdir(dirPath, { withFileTypes: true });
      
      // Look for phi-2 GGUF files in current directory
      for (const file of files) {
        if (file.isFile() && this.isPhi2Model(file.name)) {
          return path.join(dirPath, file.name);
        }
      }
      
      // Recursively scan subdirectories (max 2 levels deep)
      for (const file of files) {
        if (file.isDirectory()) {
          const subPath = path.join(dirPath, file.name);
          
          // Skip hidden directories and common non-model directories
          if (this.shouldSkipDirectory(file.name)) {
            continue;
          }
          
          try {
            const modelPath = await this.scanDirectory(subPath);
            if (modelPath) {
              return modelPath;
            }
          } catch (error) {
            // Skip directories we can't access
            continue;
          }
        }
      }
    } catch (error) {
      throw error;
    }
    
    return null;
  }

  /**
   * Check if filename matches Phi-2 model patterns
   * @param {string} filename - File name to check
   * @returns {boolean} True if likely a Phi-2 model
   */
  static isPhi2Model(filename) {
    const name = filename.toLowerCase();
    
    // Must be a GGUF file
    if (!name.endsWith('.gguf')) {
      return false;
    }
    
    // Must contain "phi" and "2" in the name
    const containsPhi = name.includes('phi');
    const containsTwo = name.includes('2');
    
    // Common Phi-2 model name patterns
    const phi2Patterns = [
      'phi-2',
      'phi2',
      'microsoft/phi-2',
      'phi-2-instruct',
      'phi2-instruct'
    ];
    
    const matchesPattern = phi2Patterns.some(pattern => 
      name.includes(pattern.toLowerCase())
    );
    
    return containsPhi && containsTwo && matchesPattern;
  }

  /**
   * Check if directory should be skipped during scanning
   * @param {string} dirname - Directory name
   * @returns {boolean} True if should skip
   */
  static shouldSkipDirectory(dirname) {
    const skipPatterns = [
      // Hidden directories
      /^\./,
      // System directories
      /^node_modules$/,
      /^\.git$/,
      /^__pycache__$/,
      // Non-model directories
      /^logs?$/,
      /^temp$/,
      /^tmp$/,
      /^cache$/,
    ];
    
    return skipPatterns.some(pattern => pattern.test(dirname));
  }

  /**
   * Expand ~ and environment variables in path
   * @param {string} pathStr - Path string to expand
   * @returns {string} Expanded path
   */
  static expandPath(pathStr) {
    if (pathStr.startsWith('~')) {
      return pathStr.replace('~', os.homedir());
    }
    return pathStr;
  }

  /**
   * Validate that a model file exists and is accessible
   * @param {string} modelPath - Path to model file
   * @returns {Promise<boolean>} True if valid and accessible
   */
  static async validateModel(modelPath) {
    try {
      const stats = await fs.stat(modelPath);
      
      // Must be a file
      if (!stats.isFile()) {
        return false;
      }
      
      // Must be reasonable size (at least 100MB for a valid model)
      if (stats.size < 100 * 1024 * 1024) {
        console.log(`⚠️  Model file seems too small: ${stats.size} bytes`);
        return false;
      }
      
      // Must have .gguf extension
      if (!modelPath.toLowerCase().endsWith('.gguf')) {
        return false;
      }
      
      // Must match Phi-2 naming pattern
      if (!this.isPhi2Model(path.basename(modelPath))) {
        return false;
      }
      
      console.log(`✅ Model validation passed: ${path.basename(modelPath)} (${Math.round(stats.size / 1024 / 1024)}MB)`);
      return true;
      
    } catch (error) {
      console.log(`❌ Model validation failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Get model information from file path
   * @param {string} modelPath - Path to model file
   * @returns {Promise<Object>} Model information
   */
  static async getModelInfo(modelPath) {
    try {
      const stats = await fs.stat(modelPath);
      const basename = path.basename(modelPath);
      
      // Extract quantization level from filename
      let quantization = 'Unknown';
      const quantMatch = basename.match(/(Q\d+_[KMF])/i);
      if (quantMatch) {
        quantization = quantMatch[1];
      }
      
      return {
        name: basename,
        path: modelPath,
        size: stats.size,
        sizeFormatted: `${Math.round(stats.size / 1024 / 1024)}MB`,
        quantization,
        lastModified: stats.mtime,
        isValid: await this.validateModel(modelPath)
      };
    } catch (error) {
      return {
        name: path.basename(modelPath),
        path: modelPath,
        error: error.message,
        isValid: false
      };
    }
  }

  /**
   * Create the LocalRecall models directory if it doesn't exist
   * @returns {Promise<string>} Path to models directory
   */
  static async ensureModelsDirectory() {
    const modelsDir = path.join(os.homedir(), 'Library', 'Application Support', 'LocalRecall', 'models');
    
    try {
      await fs.mkdir(modelsDir, { recursive: true });
      console.log(`📁 Created models directory: ${modelsDir}`);
      return modelsDir;
    } catch (error) {
      console.error(`❌ Failed to create models directory: ${error.message}`);
      throw error;
    }
  }

  /**
   * Get recommended download instructions for Phi-2
   * @returns {Object} Download instructions
   */
  static getDownloadInstructions() {
    return {
      modelName: 'Phi-2 Instruct GGUF',
      provider: 'Hugging Face',
      url: 'https://huggingface.co/microsoft/phi-2/tree/main',
      recommendedFile: 'phi-2.Q4_K_M.gguf',
      estimatedSize: '1.4GB',
      downloadSteps: [
        '1. Visit the Hugging Face model page',
        '2. Click on "phi-2.Q4_K_M.gguf" to download',
        '3. Move the downloaded file to your models directory',
        '4. LocalRecall will automatically detect it on next launch'
      ],
      localPath: path.join(os.homedir(), 'Library', 'Application Support', 'LocalRecall', 'models')
    };
  }
}

module.exports = ModelManager;