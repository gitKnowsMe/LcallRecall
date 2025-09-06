import os
import logging
from typing import Optional, AsyncGenerator
from llama_cpp import Llama
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ModelManager:
    """Singleton Phi-2 model manager with streaming support"""
    
    _instance: Optional['ModelManager'] = None
    _model: Optional[Llama] = None
    _executor: Optional[ThreadPoolExecutor] = None
    _model_path = "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> bool:
        """Initialize the Phi-2 model (called once at startup)"""
        if self._model is not None:
            logger.info("Model already loaded")
            return True
            
        try:
            if not os.path.exists(self._model_path):
                logger.warning(f"Model not found at {self._model_path}")
                logger.info("Using mock mode for development")
                self._model = "mock"  # Use mock mode
                return True
            
            logger.info(f"Loading Phi-2 model from {self._model_path}")
            
            # Initialize thread pool for blocking operations
            self._executor = ThreadPoolExecutor(max_workers=1)
            
            try:
                # Load model in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    self._executor,
                    self._load_model
                )
                logger.info("✅ Phi-2 model loaded successfully")
                return True
            except Exception as model_error:
                logger.warning(f"Failed to load model: {model_error}")
                logger.info("Falling back to mock mode for development")
                self._model = "mock"  # Use mock mode as fallback
                return True
            
        except Exception as e:
            logger.error(f"Failed to initialize model service: {e}")
            logger.info("Using mock mode for development")
            self._model = "mock"  # Use mock mode
            return True
    
    def _load_model(self) -> Llama:
        """Load the model (runs in thread pool)"""
        return Llama(
            model_path=self._model_path,
            n_ctx=2048,  # Smaller context window to reduce memory usage
            n_batch=256,  # Smaller batch size
            n_threads=2,  # Fewer threads
            verbose=False,
            seed=42,  # Reproducible outputs
            use_mlock=False,  # Don't lock memory
            use_mmap=True,  # Use memory mapping
            n_gpu_layers=0  # Force CPU only
        )
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None
    
    def _is_mock_mode(self) -> bool:
        """Check if running in mock mode"""
        return self._model == "mock"
    
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate response (non-streaming)"""
        if not self.is_loaded():
            raise RuntimeError("Model not loaded")
        
        # Mock mode for development
        if self._is_mock_mode():
            await asyncio.sleep(0.5)  # Simulate processing time
            return f"Mock response to: {prompt[:50]}... This is a simulated AI response for development purposes."
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                self._generate_sync,
                prompt,
                max_tokens,
                False
            )
            return response
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"Generation failed: {e}")
    
    async def generate_stream(self, prompt: str, max_tokens: int = 512) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        if not self.is_loaded():
            raise RuntimeError("Model not loaded")
        
        # Mock mode for development  
        if self._is_mock_mode():
            mock_response = f"Mock streaming response to: {prompt[:50]}... This is a simulated AI response for development purposes with streaming simulation."
            words = mock_response.split()
            for word in words:
                await asyncio.sleep(0.1)  # Simulate streaming delay
                yield word + " "
            return
        
        try:
            # Create a queue for streaming tokens
            token_queue = asyncio.Queue()
            
            # Get current event loop to pass to thread
            loop = asyncio.get_event_loop()
            
            # Start generation in thread pool
            generation_task = loop.run_in_executor(
                self._executor,
                self._generate_stream_sync,
                prompt,
                max_tokens,
                token_queue,
                loop  # Pass the loop to the thread
            )
            
            # Yield tokens as they arrive
            while True:
                try:
                    token = await asyncio.wait_for(token_queue.get(), timeout=1.0)
                    if token is None:  # End of stream
                        break
                    yield token
                except asyncio.TimeoutError:
                    if generation_task.done():
                        break
                    continue
            
            # Wait for generation to complete
            await generation_task
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            raise RuntimeError(f"Streaming generation failed: {e}")
    
    def _generate_sync(self, prompt: str, max_tokens: int, stream: bool) -> str:
        """Synchronous generation (runs in thread pool)"""
        response = self._model(
            prompt,
            max_tokens=max_tokens,
            stream=stream,
            echo=False,
            stop=["</s>", "\n\nUser:", "\n\nHuman:"]
        )
        
        if stream:
            return response
        else:
            return response['choices'][0]['text'].strip()
    
    def _generate_stream_sync(self, prompt: str, max_tokens: int, token_queue: asyncio.Queue, loop):
        """Synchronous streaming generation (runs in thread pool)"""
        try:
            stream = self._model(
                prompt,
                max_tokens=max_tokens,
                stream=True,
                echo=False,
                stop=["</s>", "\n\nUser:", "\n\nHuman:"]
            )
            
            for chunk in stream:
                token = chunk['choices'][0]['text']
                # Put token in queue (thread-safe) using the passed loop
                future = asyncio.run_coroutine_threadsafe(
                    token_queue.put(token), 
                    loop
                )
                # Wait for the future to complete to ensure proper error handling
                future.result()
            
            # Signal end of stream
            future = asyncio.run_coroutine_threadsafe(
                token_queue.put(None),
                loop
            )
            future.result()
            
        except Exception as e:
            logger.error(f"Streaming generation error: {e}")
            try:
                future = asyncio.run_coroutine_threadsafe(
                    token_queue.put(None),
                    loop
                )
                future.result()
            except Exception:
                pass  # Ignore errors when signaling end during exception handling
    
    def create_rag_prompt(self, query: str, context: str) -> str:
        """Create RAG prompt for Phi-2"""
        return f"""<|system|>
You are a helpful AI assistant. Use the provided context to answer the user's question accurately. If the context doesn't contain relevant information, say so clearly.

Context:
{context}

<|user|>
{query}

<|assistant|>
"""
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._executor:
            self._executor.shutdown(wait=True)
            logger.info("Model cleanup completed")