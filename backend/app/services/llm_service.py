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

        if not os.path.exists(self._model_path):
            raise RuntimeError(f"Model not found at {self._model_path}")

        logger.info(f"Loading Phi-2 model from {self._model_path}")

        # Initialize thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Load model in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            self._executor,
            self._load_model
        )
        logger.info("✅ Phi-2 model loaded successfully")
        return True
    
    def _load_model(self) -> Llama:
        """Load the model (runs in thread pool)"""
        try:
            return Llama(
                model_path=self._model_path,
                n_ctx=2048,     # More conservative context window
                n_batch=256,    # More conservative batch size
                n_threads=2,    # Fewer threads to reduce resource contention
                verbose=True,   # Enable verbose to see detailed error messages
                seed=42,
                use_mlock=False,  # Don't lock memory
                use_mmap=True     # Use memory mapping for efficiency
            )
        except Exception as e:
            logger.error(f"Detailed model loading error: {e}")
            raise e
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None
    
    async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Generate response (non-streaming)"""
        if not self.is_loaded():
            raise RuntimeError("Model not loaded")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                self._generate_sync,
                prompt,
                max_tokens,
                temperature,
                False
            )
            return response
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"Generation failed: {e}")
    
    async def generate_stream(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        if not self.is_loaded():
            raise RuntimeError("Model not loaded")
        
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
                temperature,
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
    
    def _generate_sync(self, prompt: str, max_tokens: int, temperature: float, stream: bool) -> str:
        """Synchronous generation (runs in thread pool)"""
        response = self._model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            echo=False,
            stop=[]  # Empty list allows natural generation end
        )
        
        if stream:
            return response
        else:
            return response['choices'][0]['text'].strip()
    
    def _generate_stream_sync(self, prompt: str, max_tokens: int, temperature: float, token_queue: asyncio.Queue, loop):
        """Synchronous streaming generation (runs in thread pool)"""
        try:
            stream = self._model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                echo=False,
                stop=[]  # Empty list allows natural generation end
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
        """Create RAG prompt for Phi-2 - Enhanced instruction format"""
        return f"""You are a helpful assistant. Answer the question below using the provided context. Provide a comprehensive, detailed response of 5-7 sentences that thoroughly explains the topic. If the context doesn't contain the answer, say "I cannot find this information in the provided context."

CONTEXT:
{context}

QUESTION: {query}

ANSWER: Let me provide a detailed explanation:"""
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._executor:
            self._executor.shutdown(wait=True)
            logger.info("Model cleanup completed")