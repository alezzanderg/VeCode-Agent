from __future__ import annotations
from dataclasses import dataclass
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip loading
import logging
from openai import OpenAI
from typing import Optional

@dataclass
class EditInstruction:
    goal: str
    context: str  # file content or snippet

class LLM:
    """
    DeepSeek API integration for generating unified diffs and text generation.
    Uses OpenAI-compatible API format.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            logging.warning("DEEPSEEK_API_KEY not found. LLM will use fallback mode.")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
        
    def generate_unified_diff(self, filename: str, old_text: str, instruction: EditInstruction) -> str:
        """
        Generate a unified diff using DeepSeek API.
        Falls back to simple comment injection if API is not available.
        """
        if not self.client:
            # Fallback mode when API key is not available
            return self._fallback_diff(filename, old_text, instruction)
        
        try:
            prompt = f"""You are a code editor assistant. Generate a unified diff to modify the following code according to the instruction.

Filename: {filename}
Instruction: {instruction.goal}
Context: {instruction.context}

Original code:
```
{old_text}
```

Generate a unified diff format that shows the changes needed. The diff should:
1. Use proper unified diff format with --- and +++ headers
2. Show line numbers and context
3. Only include the minimal changes needed
4. Be syntactically correct for the file type

Return ONLY the unified diff, no explanations."""

            response = self.client.chat.completions.create(
                model="deepseek-coder",
                messages=[
                    {"role": "system", "content": "You are a precise code editor that generates unified diffs."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"DeepSeek API error: {e}")
            return self._fallback_diff(filename, old_text, instruction)
    
    def generate_text(self, prompt: str, system_prompt: str = "You are a helpful AI assistant.") -> str:
        """
        Generate text using DeepSeek API for general text generation tasks.
        """
        if not self.client:
            return "Error: DeepSeek API key not available"
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"DeepSeek API error: {e}")
            return f"Error: {str(e)}"
    
    def _fallback_diff(self, filename: str, old_text: str, instruction: EditInstruction) -> str:
        """
        Fallback implementation when API is not available.
        """
        return f"""--- a/{filename}
+++ b/{filename}
@@ -1,{len(old_text.splitlines())} +1,{len(old_text.splitlines()) + 1} @@
 {old_text.rstrip()}
+// TODO: {instruction.goal}
"""
