#!/usr/bin/env python3
"""
VSCode AI Agent CLI
A command-line interface for the VSCode AI Agent with DeepSeek integration.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip loading

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from agent.config import AgentConfig
from agent.llm import LLM, EditInstruction
from agent.tools.executor import Executor
from agent.tools.fs import FileSystemTool
from agent.tools.edit import EditTool
from agent.tools.terminal import TerminalTool
from agent.tools.planner import Planner

try:
    from colorama import init, Fore, Back, Style
    init()  # Initialize colorama for Windows
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # Fallback color definitions
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

class CLIColors:
    """Color utilities for CLI output"""
    
    @staticmethod
    def success(text: str) -> str:
        return f"{Fore.GREEN}{text}{Style.RESET_ALL}" if COLORS_AVAILABLE else text
    
    @staticmethod
    def error(text: str) -> str:
        return f"{Fore.RED}{text}{Style.RESET_ALL}" if COLORS_AVAILABLE else text
    
    @staticmethod
    def warning(text: str) -> str:
        return f"{Fore.YELLOW}{text}{Style.RESET_ALL}" if COLORS_AVAILABLE else text
    
    @staticmethod
    def info(text: str) -> str:
        return f"{Fore.CYAN}{text}{Style.RESET_ALL}" if COLORS_AVAILABLE else text
    
    @staticmethod
    def highlight(text: str) -> str:
        return f"{Fore.MAGENTA}{Style.BRIGHT}{text}{Style.RESET_ALL}" if COLORS_AVAILABLE else text

class VSCodeAICLI:
    """Main CLI class for VSCode AI Agent"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or os.getcwd()).resolve()
        # Determine shell path for Windows
        if os.name == "nt":
            # Try to find PowerShell executable
            import shutil
            shell_path = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
        else:
            shell_path = "bash"
            
        self.config = AgentConfig(
            project_root=self.project_root,
            shell=shell_path
        ).resolve()
        
        # Initialize components
        self.llm = LLM()
        self.executor = Executor(self.config)
        self.fs_tool = FileSystemTool(self.config)
        self.edit_tool = EditTool(self.config, self.llm)
        self.terminal_tool = TerminalTool(self.config)
        self.planner_tool = Planner()
        
        # Check for DeepSeek API key
        self._check_api_key()
    
    def _check_api_key(self):
        """Check if DeepSeek API key is configured"""
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            print(CLIColors.warning(
                "⚠️  Warning: DEEPSEEK_API_KEY not found in environment variables."
            ))
            print(CLIColors.info(
                "💡 Set your API key: export DEEPSEEK_API_KEY=your_api_key_here"
            ))
            print(CLIColors.info(
                "   Or add it to your .env file in the project root."
            ))
            print()
    
    def edit_file(self, filepath: str, instruction: str) -> bool:
        """Edit a file using AI assistance"""
        try:
            file_path = Path(filepath)
            if not file_path.is_absolute():
                file_path = self.project_root / file_path
            
            if not file_path.exists():
                print(CLIColors.error(f"❌ File not found: {file_path}"))
                return False
            
            print(CLIColors.info(f"📝 Editing file: {file_path}"))
            print(CLIColors.info(f"📋 Instruction: {instruction}"))
            print()
            
            # Read current file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Generate edit instruction
            edit_instruction = EditInstruction(goal=instruction, context=content)
            
            # Get AI-generated diff
            diff = self.llm.generate_unified_diff(str(file_path), content, edit_instruction)
            
            print(CLIColors.highlight("🤖 AI Generated Changes:"))
            print(diff)
            print()
            
            # Ask for confirmation
            response = input(CLIColors.info("Apply these changes? (y/N): ")).strip().lower()
            if response in ['y', 'yes']:
                # Apply the edit using the edit tool
                result = self.edit_tool.apply_unified_diff(str(file_path), diff)
                if result.get('ok', False):
                    print(CLIColors.success("✅ Changes applied successfully!"))
                    return True
                else:
                    print(CLIColors.error(f"❌ Failed to apply changes: {result.get('error', 'Unknown error')}"))
                    return False
            else:
                print(CLIColors.warning("⏭️  Changes cancelled."))
                return False
                
        except Exception as e:
            print(CLIColors.error(f"❌ Error editing file: {str(e)}"))
            return False
    
    def list_files(self, directory: str = ".") -> bool:
        """List files in a directory"""
        try:
            dir_path = Path(directory)
            if not dir_path.is_absolute():
                dir_path = self.project_root / dir_path
            
            files = self.fs_tool.tree(str(dir_path.relative_to(self.project_root)) if dir_path != self.project_root else ".")
            if files:
                print(f"\n📁 Files in {dir_path}:")
                for file in files:
                    file_type = "📁" if file.get('type') == 'dir' else "📄"
                    print(f"  {file_type} {file['path']}")
            else:
                print(f"\n📁 Directory {dir_path} is empty.")
            return True
                
        except Exception as e:
            print(CLIColors.error(f"❌ Error listing files: {str(e)}"))
            return False
    
    def run_command(self, command: str) -> bool:
        """Run a terminal command"""
        try:
            print(CLIColors.info(f"🔧 Running command: {command}"))
            
            # Use a default session for CLI commands
            session_id = "cli_session"
            
            # Open session if not exists
            self.terminal_tool.open(session_id)
            
            # Execute command
            exec_result = self.terminal_tool.exec(session_id, command)
            
            if exec_result.get('ok', False):
                # Wait a moment for command to execute
                import time
                time.sleep(1.5)
                
                # Read output
                read_result = self.terminal_tool.read(session_id)
                output = read_result.get('output', '')
                
                if output.strip():
                    print(CLIColors.highlight("📤 Output:"))
                    print(output)
                
                print(CLIColors.success("✅ Command executed successfully!"))
                return True
            else:
                print(CLIColors.error("❌ Command execution failed"))
                return False
                
        except Exception as e:
            print(CLIColors.error(f"❌ Error running command: {str(e)}"))
            return False
    
    def plan_task(self, task_description: str) -> bool:
        """Create a plan for a given task"""
        try:
            print(CLIColors.info(f"🎯 Planning task: {task_description}"))
            steps = self.planner_tool.plan(task_description)
            
            if steps:
                print(CLIColors.highlight("\n📋 Generated Plan:"))
                for i, step in enumerate(steps, 1):
                    print(f"  {i}. {step.kind}: {step.args}")
                return True
            else:
                print(CLIColors.warning("\n📋 No specific steps generated. Task might be straightforward."))
                return True
                
        except Exception as e:
            print(CLIColors.error(f"❌ Error planning task: {str(e)}"))
            return False
    
    def create_folder(self, folder_name: str) -> bool:
        """Create a new folder"""
        try:
            folder_path = Path(folder_name)
            if not folder_path.is_absolute():
                folder_path = self.project_root / folder_path
            
            if folder_path.exists():
                print(CLIColors.warning(f"⚠️  Folder already exists: {folder_path}"))
                return False
            
            folder_path.mkdir(parents=True, exist_ok=True)
            print(CLIColors.success(f"✅ Created folder: {folder_path}"))
            return True
            
        except Exception as e:
            print(CLIColors.error(f"❌ Error creating folder: {str(e)}"))
            return False
    
    def create_file(self, file_name: str) -> bool:
        """Create a new file"""
        try:
            file_path = Path(file_name)
            if not file_path.is_absolute():
                file_path = self.project_root / file_path
            
            if file_path.exists():
                print(CLIColors.warning(f"⚠️  File already exists: {file_path}"))
                return False
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create empty file
            file_path.touch()
            print(CLIColors.success(f"✅ Created file: {file_path}"))
            return True
            
        except Exception as e:
            print(CLIColors.error(f"❌ Error creating file: {str(e)}"))
            return False
    
    def create_file_with_content(self, file_name: str, instruction: str, content_type: str) -> bool:
        """Create a new file with AI-generated content"""
        try:
            file_path = Path(file_name)
            if not file_path.is_absolute():
                file_path = self.project_root / file_path
            
            if file_path.exists():
                print(CLIColors.warning(f"⚠️  File already exists: {file_path}"))
                return False
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate content based on the instruction and content type
            content = self._generate_file_content(file_name, instruction, content_type)
            
            if content:
                # Write content to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(CLIColors.success(f"✅ Created file with content: {file_path}"))
                return True
            else:
                # Fallback to empty file if content generation fails
                file_path.touch()
                print(CLIColors.warning(f"⚠️  Created empty file (content generation failed): {file_path}"))
                return True
            
        except Exception as e:
            print(CLIColors.error(f"❌ Error creating file: {str(e)}"))
            return False
    
    def _generate_file_content(self, file_name: str, instruction: str, content_type: str) -> str:
        """Generate file content using AI based on instruction and content type"""
        try:
            # Check if DeepSeek API key is available
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                print(CLIColors.warning("🤖 Content generation requires DEEPSEEK_API_KEY to be set."))
                return ""
            
            print(CLIColors.info(f"🤖 Generating {content_type} content..."))
            
            # Determine file extension and language
            file_path = Path(file_name)
            file_ext = file_path.suffix.lower()
            
            # Create content generation prompt based on content type
            if content_type == 'calculator':
                content_prompt = f"""Generate the actual Python calculator code that should be written inside '{file_name}'. 
                
Requirements:
- Include basic arithmetic operations (add, subtract, multiply, divide)
- Handle user input and output
- Include error handling for division by zero and invalid input
- Make it user-friendly with clear prompts
- Add a main function and proper if __name__ == '__main__' guard
- Include docstrings and comments
                
Generate ONLY the Python code content, not code that creates files."""
            
            elif content_type == 'web_server':
                content_prompt = f"""Create a simple web server for the file '{file_name}'.
                
Requirements:
- Use Python with Flask or built-in http.server
- Include basic routes (home page, about)
- Handle GET requests
- Include proper error handling
- Make it easy to run and test
- Add comments explaining the code
                
Generate complete, functional Python code."""
            
            elif content_type == 'api':
                content_prompt = f"""Create a REST API for the file '{file_name}'.
                
Requirements:
- Use Python with Flask
- Include CRUD operations (GET, POST, PUT, DELETE)
- Use JSON for data exchange
- Include proper error handling and status codes
- Add example endpoints
- Include documentation in comments
                
Generate complete, functional Python code."""
            
            elif content_type == 'script':
                content_prompt = f"""Create a Python script for the file '{file_name}' based on: {instruction}
                
Requirements:
- Make it functional and ready to run
- Include proper error handling
- Add helpful comments
- Use best practices
- Include a main function if appropriate
                
Generate complete, functional Python code."""
            
            elif content_type == 'config':
                if file_ext in ['.json']:
                    content_prompt = f"""Create a JSON configuration file for '{file_name}' based on: {instruction}
                    
Requirements:
- Use proper JSON format
- Include common configuration options
- Add comments where possible (if JSON5 format)
- Make it well-structured and readable
                    
Generate valid JSON content."""
                elif file_ext in ['.yaml', '.yml']:
                    content_prompt = f"""Create a YAML configuration file for '{file_name}' based on: {instruction}
                    
Requirements:
- Use proper YAML format
- Include common configuration options
- Add comments explaining each section
- Make it well-structured and readable
                    
Generate valid YAML content."""
                else:
                    content_prompt = f"""Create a configuration file for '{file_name}' based on: {instruction}
                    
Requirements:
- Use appropriate format for the file extension
- Include common configuration options
- Add comments explaining settings
- Make it well-structured and readable
                    
Generate valid configuration content."""
            
            elif content_type == 'readme':
                content_prompt = f"""Create a README.md file for '{file_name}' based on: {instruction}
                
Requirements:
- Use proper Markdown format
- Include project title, description, installation, usage
- Add examples if relevant
- Include contributing guidelines
- Make it comprehensive and helpful
                
Generate complete Markdown content."""
            
            else:  # 'other' or unknown content type
                content_prompt = f"""Create content for the file '{file_name}' based on: {instruction}
                
Requirements:
- Make it functional and appropriate for the file type
- Include proper formatting for the file extension
- Add helpful comments or documentation
- Use best practices
- Make it ready to use
                
Generate complete, functional content."""
            
            # Generate content using LLM
            system_prompt = "You are a code generator. Generate ONLY the actual code content that should go inside the file, not code that creates the file. Do not include any explanations, markdown formatting, file creation code, or additional text. Output should be the direct file content ready to write."
            content = self.llm.generate_text(content_prompt, system_prompt)
            
            # Clean up the content (remove markdown code blocks if present)
            content = content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                # Remove first line (```language) and last line (```)
                if len(lines) > 2 and lines[-1].strip() == '```':
                    content = '\n'.join(lines[1:-1])
                elif len(lines) > 1:
                    content = '\n'.join(lines[1:])
            
            return content
            
        except Exception as e:
            print(CLIColors.error(f"🤖 Error generating content: {str(e)}"))
            return ""
    
    def delete_item(self, item_name: str) -> bool:
        """Delete a file or folder"""
        try:
            item_path = Path(item_name)
            if not item_path.is_absolute():
                item_path = self.project_root / item_path
            
            if not item_path.exists():
                print(CLIColors.error(f"❌ Item not found: {item_path}"))
                return False
            
            # Ask for confirmation
            item_type = "folder" if item_path.is_dir() else "file"
            response = input(CLIColors.warning(f"⚠️  Delete {item_type} '{item_path}'? (y/N): ")).strip().lower()
            
            if response in ['y', 'yes']:
                if item_path.is_dir():
                    import shutil
                    shutil.rmtree(item_path)
                else:
                    item_path.unlink()
                print(CLIColors.success(f"✅ Deleted {item_type}: {item_path}"))
                return True
            else:
                print(CLIColors.info("⏭️  Deletion cancelled."))
                return False
            
        except Exception as e:
            print(CLIColors.error(f"❌ Error deleting item: {str(e)}"))
            return False
    
    def review_code(self, file_path: str, auto_fix: bool = False) -> bool:
        """Review code for errors, style issues, and quality"""
        try:
            target_path = Path(file_path)
            if not target_path.is_absolute():
                target_path = self.project_root / target_path
            
            if not target_path.exists():
                print(CLIColors.error(f"❌ File not found: {target_path}"))
                return False
            
            if not target_path.is_file():
                print(CLIColors.error(f"❌ Path is not a file: {target_path}"))
                return False
            
            print(CLIColors.info(f"🔍 Reviewing code: {target_path}"))
            if auto_fix:
                print(CLIColors.warning("🔧 Auto-fix mode enabled - will attempt to fix detected issues"))
            else:
                print(CLIColors.info("📋 Analysis mode - will detect and explain issues without fixing"))
            print()
            
            # Determine file type
            file_ext = target_path.suffix.lower()
            
            if file_ext == '.py':
                return self._review_python_file(target_path, auto_fix)
            elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
                return self._review_javascript_file(target_path)
            else:
                print(CLIColors.warning(f"⚠️  Unsupported file type: {file_ext}"))
                print(CLIColors.info("💡 Currently supported: .py, .js, .ts, .jsx, .tsx"))
                return False
                
        except Exception as e:
            print(CLIColors.error(f"❌ Error reviewing code: {str(e)}"))
            return False
    
    def _review_python_file(self, file_path: Path, auto_fix: bool = False) -> bool:
        """Review a Python file using various linting tools and AI"""
        import subprocess
        import tempfile
        
        issues_found = False
        
        # Read file content for AI review
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            print(CLIColors.error(f"❌ Error reading file: {str(e)}"))
            return False
        
        print(CLIColors.highlight("🔧 Running Python Code Analysis..."))
        print()
        
        # 1. Syntax Check with detailed explanations
        print(CLIColors.info("📋 Checking syntax..."))
        try:
            compile(file_content, str(file_path), 'exec')
            print(CLIColors.success("✅ Syntax: No syntax errors found"))
        except SyntaxError as e:
            print(CLIColors.error(f"❌ Syntax Error: Line {e.lineno}: {e.msg}"))
            
            # Provide detailed explanation and fix suggestions
            self._explain_syntax_error(e, file_content, file_path)
            
            # Only auto-fix if explicitly requested
            if auto_fix:
                if self._auto_fix_syntax_error(file_path, file_content, e):
                    print(CLIColors.success("🔧 Auto-fix applied! Re-checking syntax..."))
                    # Re-read the file and check syntax again
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            fixed_content = f.read()
                        compile(fixed_content, str(file_path), 'exec')
                        print(CLIColors.success("✅ Syntax: Fixed! No syntax errors found"))
                    except SyntaxError:
                        print(CLIColors.warning("⚠️  Auto-fix applied but syntax error still exists"))
                        issues_found = True
                else:
                    issues_found = True
            else:
                issues_found = True
        
        # 2. Flake8 (Style and Error Checking)
        print(CLIColors.info("📋 Running flake8 analysis..."))
        try:
            result = subprocess.run(
                ['python', '-m', 'flake8', '--max-line-length=88', str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(CLIColors.success("✅ Flake8: No style issues found"))
            else:
                print(CLIColors.warning("⚠️  Flake8 Issues:"))
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"  {CLIColors.warning('•')} {line}")
                issues_found = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(CLIColors.warning("⚠️  Flake8 not available or timed out"))
        except Exception as e:
            print(CLIColors.warning(f"⚠️  Flake8 error: {str(e)}"))
        
        # 3. Pylint (Comprehensive Analysis)
        print(CLIColors.info("📋 Running pylint analysis..."))
        try:
            result = subprocess.run(
                ['python', '-m', 'pylint', '--score=no', '--reports=no', str(file_path)],
                capture_output=True, text=True, timeout=45
            )
            if result.stdout.strip():
                print(CLIColors.warning("⚠️  Pylint Issues:"))
                for line in result.stdout.strip().split('\n'):
                    if line.strip() and not line.startswith('*'):
                        # Color code different issue types
                        if 'ERROR' in line or 'E:' in line:
                            print(f"  {CLIColors.error('🔴')} {line}")
                        elif 'WARNING' in line or 'W:' in line:
                            print(f"  {CLIColors.warning('🟡')} {line}")
                        elif 'INFO' in line or 'I:' in line:
                            print(f"  {CLIColors.info('🔵')} {line}")
                        else:
                            print(f"  {CLIColors.warning('•')} {line}")
                issues_found = True
            else:
                print(CLIColors.success("✅ Pylint: No issues found"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(CLIColors.warning("⚠️  Pylint not available or timed out"))
        except Exception as e:
            print(CLIColors.warning(f"⚠️  Pylint error: {str(e)}"))
        
        # 4. Bandit (Security Analysis)
        print(CLIColors.info("📋 Running bandit security analysis..."))
        try:
            result = subprocess.run(
                ['python', '-m', 'bandit', '-f', 'txt', str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            if 'No issues identified' in result.stdout:
                print(CLIColors.success("✅ Bandit: No security issues found"))
            elif result.stdout.strip():
                print(CLIColors.error("🔒 Security Issues Found:"))
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Issue:' in line or 'Severity:' in line or 'Confidence:' in line:
                        print(f"  {CLIColors.error('🔴')} {line}")
                    elif line.strip() and not line.startswith('Run started') and not line.startswith('Files skipped'):
                        print(f"  {line}")
                issues_found = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(CLIColors.warning("⚠️  Bandit not available or timed out"))
        except Exception as e:
            print(CLIColors.warning(f"⚠️  Bandit error: {str(e)}"))
        
        # 5. MyPy (Type Checking)
        print(CLIColors.info("📋 Running mypy type checking..."))
        try:
            result = subprocess.run(
                ['python', '-m', 'mypy', '--ignore-missing-imports', str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(CLIColors.success("✅ MyPy: No type issues found"))
            else:
                print(CLIColors.warning("⚠️  Type Issues:"))
                for line in result.stdout.strip().split('\n'):
                    if line.strip() and 'error:' in line:
                        print(f"  {CLIColors.warning('🟡')} {line}")
                issues_found = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(CLIColors.warning("⚠️  MyPy not available or timed out"))
        except Exception as e:
            print(CLIColors.warning(f"⚠️  MyPy error: {str(e)}"))
        
        # 6. AI-Powered Code Review
        print()
        print(CLIColors.highlight("🤖 AI-Powered Code Review..."))
        ai_review_success = self._ai_code_review(file_content, str(file_path))
        
        # Summary
        print()
        print(CLIColors.highlight("📊 Review Summary:"))
        if not issues_found and ai_review_success:
            print(CLIColors.success("✅ Overall: Code looks good! No major issues found."))
        elif issues_found:
            print(CLIColors.warning("⚠️  Overall: Issues found that should be addressed."))
        else:
            print(CLIColors.info("ℹ️  Overall: Review completed with limited analysis."))
        
        return True
    
    def _explain_syntax_error(self, syntax_error: SyntaxError, file_content: str, file_path: Path) -> None:
        """Provide detailed explanation and manual fix suggestions for syntax errors"""
        lines = file_content.split('\n')
        error_line = syntax_error.lineno - 1 if syntax_error.lineno else 0
        error_msg = syntax_error.msg.lower()
        
        print()
        print(CLIColors.highlight("🔍 Detailed Error Analysis:"))
        
        # Show the problematic line with context
        if error_line < len(lines):
            start_line = max(0, error_line - 2)
            end_line = min(len(lines), error_line + 3)
            
            print(CLIColors.info("📍 Code context:"))
            for i in range(start_line, end_line):
                line_num = i + 1
                line_content = lines[i] if i < len(lines) else ""
                if i == error_line:
                    print(f"  {CLIColors.error('→')} {line_num:3d}: {line_content}")
                    if syntax_error.offset:
                        print(f"      {' ' * (len(str(line_num)) + syntax_error.offset + 1)}^")
                else:
                    print(f"    {line_num:3d}: {line_content}")
        
        print()
        print(CLIColors.info("💡 Error Explanation & Fix Suggestions:"))
        
        # Provide specific explanations and fix suggestions
        if 'unterminated string literal' in error_msg or 'eol while scanning string literal' in error_msg:
            print("  • Problem: String is missing a closing quote")
            print("  • Fix: Add the missing quote (\" or ') at the end of the string")
            if error_line < len(lines):
                line = lines[error_line]
                if '"' in line and line.count('"') % 2 == 1:
                    print(f"  • Suggested fix: Add \" at the end of line {error_line + 1}")
                elif "'" in line and line.count("'") % 2 == 1:
                    print(f"  • Suggested fix: Add ' at the end of line {error_line + 1}")
        
        elif 'eof while scanning triple-quoted string literal' in error_msg:
            print("  • Problem: Triple-quoted string (\"\"\" or ''') is never closed")
            print("  • Fix: Add the closing triple quotes at the end of the docstring/multiline string")
            
            # Find the unclosed triple quote
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if '"""' in line and line.count('"""') % 2 == 1:
                    print(f"  • Unclosed triple quote found at line {i + 1}")
                    print(f"  • Suggested fix: Add \"\"\" at the end of the file or where the docstring should end")
                    break
                elif "'''" in line and line.count("'''") % 2 == 1:
                    print(f"  • Unclosed triple quote found at line {i + 1}")
                    print(f"  • Suggested fix: Add ''' at the end of the file or where the docstring should end")
                    break
        
        elif 'invalid syntax' in error_msg and syntax_error.text:
            if '(' in syntax_error.text and ')' not in syntax_error.text:
                print("  • Problem: Missing closing parenthesis")
                print(f"  • Fix: Add ')' to close the parenthesis on line {error_line + 1}")
            
            elif any(keyword in syntax_error.text for keyword in ['if ', 'for ', 'while ', 'def ', 'class ', 'try:', 'except', 'else', 'elif']):
                if not syntax_error.text.strip().endswith(':'):
                    print("  • Problem: Missing colon (:) at the end of control structure")
                    print(f"  • Fix: Add ':' at the end of line {error_line + 1}")
            else:
                print("  • Problem: Invalid Python syntax")
                print("  • Fix: Check for typos, missing operators, or incorrect indentation")
        
        else:
            print("  • Problem: Syntax error detected")
            print("  • Fix: Review the code structure and Python syntax rules")
        
        print()
        print(CLIColors.warning("💡 To automatically fix this error, use: review --fix <filename>"))
        print()
    
    def _auto_fix_syntax_error(self, file_path: Path, file_content: str, syntax_error: SyntaxError) -> bool:
        """Attempt to automatically fix common syntax errors"""
        try:
            lines = file_content.split('\n')
            error_line = syntax_error.lineno - 1 if syntax_error.lineno else 0
            error_msg = syntax_error.msg.lower()
            
            print(CLIColors.info(f"🔧 Attempting to auto-fix: {syntax_error.msg}"))
            
            # Fix unterminated string literals
            if 'unterminated string literal' in error_msg or 'eol while scanning string literal' in error_msg:
                return self._fix_unterminated_string(file_path, lines, error_line)
            
            # Fix unterminated triple-quoted strings
            elif 'eof while scanning triple-quoted string literal' in error_msg:
                return self._fix_unterminated_triple_quote(file_path, lines, error_line)
            
            # Fix missing parentheses
            elif 'invalid syntax' in error_msg and syntax_error.text:
                if '(' in syntax_error.text and ')' not in syntax_error.text:
                    return self._fix_missing_parenthesis(file_path, lines, error_line)
            
            # Fix missing colons
            elif 'invalid syntax' in error_msg and syntax_error.text:
                text = syntax_error.text.strip()
                if any(keyword in text for keyword in ['if ', 'for ', 'while ', 'def ', 'class ', 'try:', 'except', 'else', 'elif']):
                    if not text.endswith(':'):
                        return self._fix_missing_colon(file_path, lines, error_line)
            
            print(CLIColors.warning("⚠️  Auto-fix not available for this type of syntax error"))
            return False
            
        except Exception as e:
            print(CLIColors.error(f"❌ Error during auto-fix: {str(e)}"))
            return False
    
    def _fix_unterminated_string(self, file_path: Path, lines: list, error_line: int) -> bool:
        """Fix unterminated string literals"""
        try:
            if error_line < len(lines):
                line = lines[error_line]
                # Find the unterminated string and add closing quote
                if '"' in line and line.count('"') % 2 == 1:
                    lines[error_line] = line + '"'
                elif "'" in line and line.count("'") % 2 == 1:
                    lines[error_line] = line + "'"
                else:
                    return False
                
                # Write the fixed content back to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                
                print(CLIColors.success(f"🔧 Fixed unterminated string on line {error_line + 1}"))
                return True
        except Exception:
            return False
        return False
    
    def _fix_unterminated_triple_quote(self, file_path: Path, lines: list, error_line: int) -> bool:
        """Fix unterminated triple-quoted strings"""
        try:
            # Look for the start of the triple-quoted string
            triple_quote_start = -1
            quote_type = None
            
            # Search backwards from the end of file to find the unterminated triple quote
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if '"""' in line:
                    # Count the number of triple quotes in this line
                    count = line.count('"""')
                    if count % 2 == 1:  # Odd number means one is unterminated
                        triple_quote_start = i
                        quote_type = '"""'
                        break
                elif "'''" in line:
                    count = line.count("'''")
                    if count % 2 == 1:
                        triple_quote_start = i
                        quote_type = "'''"
                        break
            
            if triple_quote_start >= 0 and quote_type:
                # Add the closing triple quote at the end of the file
                lines.append(quote_type)
                
                # Write the fixed content back to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                
                print(CLIColors.success(f"🔧 Fixed unterminated triple-quoted string starting at line {triple_quote_start + 1}"))
                return True
                
        except Exception:
            return False
        return False
    
    def _fix_missing_parenthesis(self, file_path: Path, lines: list, error_line: int) -> bool:
        """Fix missing closing parenthesis"""
        try:
            if error_line < len(lines):
                line = lines[error_line]
                open_parens = line.count('(')
                close_parens = line.count(')')
                
                if open_parens > close_parens:
                    lines[error_line] = line + ')' * (open_parens - close_parens)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    
                    print(CLIColors.success(f"🔧 Fixed missing parenthesis on line {error_line + 1}"))
                    return True
        except Exception:
            return False
        return False
    
    def _fix_missing_colon(self, file_path: Path, lines: list, error_line: int) -> bool:
        """Fix missing colon in control structures"""
        try:
            if error_line < len(lines):
                line = lines[error_line].rstrip()
                if not line.endswith(':'):
                    lines[error_line] = line + ':'
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    
                    print(CLIColors.success(f"🔧 Fixed missing colon on line {error_line + 1}"))
                    return True
        except Exception:
            return False
        return False
    
    def _review_javascript_file(self, file_path: Path) -> bool:
        """Review a JavaScript/TypeScript file"""
        import subprocess
        
        print(CLIColors.info("📋 Running JavaScript/TypeScript analysis..."))
        
        # Try ESLint
        try:
            result = subprocess.run(
                ['npx', 'eslint', str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(CLIColors.success("✅ ESLint: No issues found"))
            else:
                print(CLIColors.warning("⚠️  ESLint Issues:"))
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"  {CLIColors.warning('•')} {line}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(CLIColors.warning("⚠️  ESLint not available. Install with: npm install -g eslint"))
        except Exception as e:
            print(CLIColors.warning(f"⚠️  ESLint error: {str(e)}"))
        
        # AI Review for JS/TS
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            print()
            print(CLIColors.highlight("🤖 AI-Powered Code Review..."))
            self._ai_code_review(file_content, str(file_path))
        except Exception as e:
            print(CLIColors.error(f"❌ Error reading file for AI review: {str(e)}"))
        
        return True
    
    def _ai_code_review(self, file_content: str, file_path: str) -> bool:
        """Perform AI-powered code review"""
        try:
            # Check if DeepSeek API key is available
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                print(CLIColors.warning("🤖 AI code review requires DEEPSEEK_API_KEY to be set."))
                return False
            
            # Create AI review prompt
            review_prompt = f"""Please review this code file and provide a comprehensive analysis:

File: {file_path}

Code:
```
{file_content}
```

Please analyze:
1. Code quality and best practices
2. Potential bugs or logical errors
3. Performance considerations
4. Security vulnerabilities
5. Maintainability and readability
6. Suggestions for improvement

Provide specific, actionable feedback with line references where applicable."""
            
            system_prompt = "You are an expert code reviewer. Provide detailed, constructive feedback on code quality, potential issues, and improvements. Be specific and reference line numbers when possible."
            
            print(CLIColors.info("🤖 Analyzing code with AI..."))
            ai_response = self.llm.generate_text(review_prompt, system_prompt)
            
            if ai_response:
                print(CLIColors.highlight("🤖 AI Code Review Results:"))
                print(ai_response)
                return True
            else:
                print(CLIColors.warning("🤖 AI review failed to generate response"))
                return False
                
        except Exception as e:
            print(CLIColors.error(f"🤖 AI review error: {str(e)}"))
            return False
    
    def _handle_natural_language_command(self, user_input: str) -> bool:
        """Handle natural language commands using AI interpretation"""
        try:
            # Check if DeepSeek API key is available
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                print(CLIColors.warning("🤖 AI interpretation requires DEEPSEEK_API_KEY to be set."))
                return False
            
            print(CLIColors.info("🤖 Interpreting your command with AI..."))
            
            # Create a prompt for command interpretation
            interpretation_prompt = f"""You are a CLI command interpreter. The user said: "{user_input}"

Analyze this command and determine what the user wants to do. Respond with a JSON object containing:
{{
  "action": "create_folder" | "create_file" | "create_file_with_content" | "delete" | "edit" | "list" | "run" | "plan" | "review" | "fix" | "unknown",
  "target": "the file/folder name or path",
  "instruction": "additional instruction if needed (for content generation)",
  "content_type": "calculator" | "web_server" | "api" | "script" | "config" | "readme" | "empty" | "other",
  "confidence": 0.0-1.0
}}

Examples:
- "make new folder name like 'test example 1'" -> {{"action": "create_folder", "target": "test example 1", "confidence": 0.9}}
- "create a new folder and name 'example test 1'" -> {{"action": "create_folder", "target": "example test 1", "confidence": 0.9}}
- "create a new folder and name \"example tset 1\"" -> {{"action": "create_folder", "target": "example tset 1", "confidence": 0.9}}
- "make a folder called test" -> {{"action": "create_folder", "target": "test", "confidence": 0.9}}
- "create directory named xyz" -> {{"action": "create_folder", "target": "xyz", "confidence": 0.9}}
- "create a file called readme.txt" -> {{"action": "create_file", "target": "readme.txt", "confidence": 0.9}}
- "access to the test folder and create a new python file about a calculator" -> {{"action": "create_file_with_content", "target": "test/calculator.py", "instruction": "create a calculator", "content_type": "calculator", "confidence": 0.9}}
- "create a calculator python file" -> {{"action": "create_file_with_content", "target": "calculator.py", "instruction": "create a calculator", "content_type": "calculator", "confidence": 0.9}}
- "make a web server script" -> {{"action": "create_file_with_content", "target": "server.py", "instruction": "create a web server", "content_type": "web_server", "confidence": 0.9}}
- "delete the old logs folder" -> {{"action": "delete", "target": "logs", "confidence": 0.8}}
- "show me what's in the src directory" -> {{"action": "list", "target": "src", "confidence": 0.9}}
- "review the supermarket checkout code" -> {{"action": "review", "target": "test/supermarket_checkout.py", "confidence": 0.9}}
- "check for errors in app.py" -> {{"action": "review", "target": "app.py", "confidence": 0.9}}
- "fix the supermarket checkout file" -> {{"action": "fix", "target": "test/supermarket_checkout.py", "confidence": 0.9}}
- "fix errors in main.py" -> {{"action": "fix", "target": "main.py", "confidence": 0.9}}

Pay special attention to:
1. Folder/directory creation commands with keywords: "create", "make", "new", "folder", "directory", "dir"
2. File creation with specific functionality: "calculator", "web server", "API", "script", etc.
3. Extract the folder/file name from quotes or after words like "name", "called", "named"
4. Detect when user wants functional code vs empty file

Use "create_file_with_content" when the user specifies what the file should do (calculator, server, etc.)
Use "create_file" for simple empty file creation

Only respond with the JSON object, no other text."""
            
            # Use LLM to interpret the command
            system_prompt = "You are a CLI command interpreter that responds only with valid JSON."
            response = self.llm.generate_text(interpretation_prompt, system_prompt)
            
            # Try to parse the JSON response
            try:
                import json
                # Extract JSON from response if it contains other text
                response_clean = response.strip()
                if response_clean.startswith('```'):
                    lines = response_clean.split('\n')
                    json_lines = []
                    in_json = False
                    for line in lines:
                        if line.strip().startswith('{') or in_json:
                            in_json = True
                            json_lines.append(line)
                            if line.strip().endswith('}'):
                                break
                    response_clean = '\n'.join(json_lines)
                
                # Try to find JSON in the response
                if not response_clean.startswith('{'):
                    # Look for JSON object in the response
                    import re
                    json_match = re.search(r'\{[^}]*\}', response_clean, re.DOTALL)
                    if json_match:
                        response_clean = json_match.group(0)
                    else:
                        raise json.JSONDecodeError("No JSON found", response_clean, 0)
                interpretation = json.loads(response_clean)
                
                action = interpretation.get('action', 'unknown')
                target = interpretation.get('target', '')
                instruction = interpretation.get('instruction', '')
                confidence = interpretation.get('confidence', 0.0)
                
                if confidence < 0.6:
                    print(CLIColors.warning(f"🤖 I'm not confident about interpreting '{user_input}' (confidence: {confidence:.1f})"))
                    print(CLIColors.info("💡 Try being more specific or use 'help' to see available commands."))
                    return False
                
                print(CLIColors.success(f"🤖 Understood: {action} '{target}' (confidence: {confidence:.1f})"))
                
                # Execute the interpreted command
                if action == 'create_folder':
                    return self.create_folder(target)
                elif action == 'create_file':
                    return self.create_file(target)
                elif action == 'create_file_with_content':
                    content_type = interpretation.get('content_type', 'other')
                    return self.create_file_with_content(target, instruction, content_type)
                elif action == 'delete':
                    return self.delete_item(target)
                elif action == 'list':
                    return self.list_files(target or '.')
                elif action == 'edit' and instruction:
                    return self.edit_file(target, instruction)
                elif action == 'run':
                    return self.run_command(target)
                elif action == 'plan':
                    return self.plan_task(target)
                elif action == 'review':
                    return self.review_code(target)
                elif action == 'fix':
                    return self.edit_file(target, "fix errors or issues in the file")
                else:
                    print(CLIColors.warning(f"🤖 I understood you want to '{action}' but I'm not sure how to do that yet."))
                    return False
                    
            except json.JSONDecodeError:
                print(CLIColors.error("🤖 Sorry, I couldn't understand your command. Try being more specific."))
                return False
                
        except Exception as e:
            print(CLIColors.error(f"🤖 Error interpreting command: {str(e)}"))
            return False
    
    def interactive_mode(self):
        """Start interactive CLI mode"""
        # Display VSCODE ASCII art
        ascii_art = """
 ██╗   ██╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗ 
 ██║   ██║██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ 
 ██║   ██║█████╗  ██║     ██║   ██║██║  ██║█████╗  
 ╚██╗ ██╔╝██╔══╝  ██║     ██║   ██║██║  ██║██╔══╝  
  ╚████╔╝ ███████╗╚██████╗╚██████╔╝██████╔╝███████╗ 
   ╚═══╝  ╚══════╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"""
        print(CLIColors.highlight(ascii_art))
        print()
        
        print(CLIColors.highlight("🚀 VSCode AI Agent - Interactive Mode"))
        print(CLIColors.info(f"📁 Project Root: {self.project_root}"))
        print(CLIColors.info("💡 Type 'help' for available commands, 'exit' to quit."))
        print(CLIColors.info("🤖 AI-powered: I can understand natural language commands!"))
        print()
        
        while True:
            try:
                user_input = input(CLIColors.highlight("ai-agent> ")).strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print(CLIColors.success("👋 Goodbye!"))
                    break
                
                if user_input.lower() in ['help', 'h']:
                    self._show_interactive_help()
                    continue
                
                # Parse interactive commands
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if command == 'edit':
                    if not args:
                        print(CLIColors.error("❌ Usage: edit <filepath> <instruction>"))
                        continue
                    
                    edit_parts = args.split(maxsplit=1)
                    if len(edit_parts) < 2:
                        print(CLIColors.error("❌ Usage: edit <filepath> <instruction>"))
                        continue
                    
                    filepath, instruction = edit_parts
                    self.edit_file(filepath, instruction)
                
                elif command == 'ls' or command == 'list':
                    directory = args if args else "."
                    self.list_files(directory)
                
                elif command == 'run':
                    if not args:
                        print(CLIColors.error("❌ Usage: run <command>"))
                        continue
                    self.run_command(args)
                
                elif command == 'plan':
                    if not args:
                        print(CLIColors.error("❌ Usage: plan <task_description>"))
                        continue
                    self.plan_task(args)
                
                elif command in ['mkdir', 'md', 'create-folder', 'create-dir']:
                    if not args:
                        print(CLIColors.error("❌ Usage: mkdir <folder_name>"))
                        continue
                    self.create_folder(args)
                
                elif command in ['touch', 'create-file', 'new-file']:
                    if not args:
                        print(CLIColors.error("❌ Usage: touch <file_name>"))
                        continue
                    self.create_file(args)
                
                elif command == 'review':
                    if not args:
                        print(CLIColors.error("❌ Usage: review <filepath> [--fix]"))
                        continue
                    
                    # Parse review command arguments
                    review_args = args.split()
                    auto_fix = '--fix' in review_args
                    if auto_fix:
                        review_args.remove('--fix')
                    
                    if not review_args:
                        print(CLIColors.error("❌ Usage: review <filepath> [--fix]"))
                        continue
                    
                    file_path = ' '.join(review_args)
                    self.review_code(file_path, auto_fix)
                
                elif command == 'fix':
                    if not args:
                        print(CLIColors.error("❌ Usage: fix <filepath>"))
                        continue
                    self.edit_file(args, "fix errors or issues in the file")
                
                elif command in ['rm', 'delete', 'remove']:
                    if not args:
                        print(CLIColors.error("❌ Usage: rm <file_or_folder>"))
                        continue
                    self.delete_item(args)
                
                else:
                    # Try AI-powered natural language interpretation
                    if not self._handle_natural_language_command(user_input):
                        print(CLIColors.error(f"❌ Unknown command: {command}"))
                        print(CLIColors.info("💡 Type 'help' for available commands."))
                
                print()  # Add spacing between commands
                
            except KeyboardInterrupt:
                print("\n" + CLIColors.success("👋 Goodbye!"))
                break
            except EOFError:
                print("\n" + CLIColors.success("👋 Goodbye!"))
                break
    
    def _show_interactive_help(self):
        """Show help for interactive mode"""
        help_text = """
🔧 Available Commands:

  edit <filepath> <instruction>  - Edit a file with AI assistance
  fix <filepath>                 - Fix errors or issues in a file
  ls [directory]                 - List files in directory (default: current)
  list [directory]               - Alias for 'ls'
  run <command>                  - Execute a terminal command
  plan <task_description>        - Create a plan for a task
  mkdir <folder_name>            - Create a new folder
  touch <file_name>              - Create a new file
  rm <file_or_folder>            - Delete a file or folder
  review <filepath> [--fix]      - Review code for errors and quality (use --fix to auto-fix issues)
  help                          - Show this help message
  exit                          - Exit interactive mode

🤖 AI-Powered Natural Language:
  You can also use natural language! Try commands like:
  "make new folder called test"
  "create a file named readme.txt"
  "delete the old logs folder"
  "show me what's in the src directory"
  "review the supermarket checkout code"
  "check for errors in my Python file"

📝 Examples:
  edit main.py "add error handling"
  ls src/
  run "npm install"
  plan "create a REST API for user management"
  mkdir "my new project"
  touch config.json
  review app.py
"""
        print(CLIColors.info(help_text))

def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="VSCode AI Agent CLI - AI-powered development assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s edit main.py "add error handling to the main function"
  %(prog)s list src/
  %(prog)s run "npm test"
  %(prog)s plan "implement user authentication"
  %(prog)s interactive

For more information, visit: https://github.com/your-repo/vscode-ai-agent
"""
    )
    
    parser.add_argument(
        "--project-root", "-p",
        type=str,
        help="Project root directory (default: current directory)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit a file with AI assistance")
    edit_parser.add_argument("filepath", help="Path to the file to edit")
    edit_parser.add_argument("instruction", help="Instruction for the AI on how to edit the file")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List files in a directory")
    list_parser.add_argument("directory", nargs="?", default=".", help="Directory to list (default: current)")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Execute a terminal command")
    run_parser.add_argument("cmd", help="Command to execute")
    
    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Create a plan for a task")
    plan_parser.add_argument("task", help="Task description to plan")
    
    # Mkdir command
    mkdir_parser = subparsers.add_parser("mkdir", help="Create a new folder")
    mkdir_parser.add_argument("folder_name", help="Name of the folder to create")
    
    # Touch command
    touch_parser = subparsers.add_parser("touch", help="Create a new file")
    touch_parser.add_argument("file_name", help="Name of the file to create")
    
    # Remove command
    rm_parser = subparsers.add_parser("rm", help="Delete a file or folder")
    rm_parser.add_argument("item_name", help="Name of the file or folder to delete")
    
    # Review command
    review_parser = subparsers.add_parser("review", help="Review code for errors and quality")
    review_parser.add_argument("filepath", help="Path to the file to review")
    
    # Interactive command
    subparsers.add_parser("interactive", help="Start interactive mode")
    
    return parser

def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize CLI
    try:
        cli = VSCodeAICLI(args.project_root)
    except Exception as e:
        print(CLIColors.error(f"❌ Failed to initialize CLI: {str(e)}"))
        sys.exit(1)
    
    # Handle commands
    if not args.command:
        # No command provided, show help
        parser.print_help()
        sys.exit(0)
    
    success = True
    
    if args.command == "edit":
        success = cli.edit_file(args.filepath, args.instruction)
    
    elif args.command == "list":
        success = cli.list_files(args.directory)
    
    elif args.command == "run":
        success = cli.run_command(args.cmd)
    
    elif args.command == "plan":
        success = cli.plan_task(args.task)
    
    elif args.command == "mkdir":
        success = cli.create_folder(args.folder_name)
    
    elif args.command == "touch":
        success = cli.create_file(args.file_name)
    
    elif args.command == "rm":
        success = cli.delete_item(args.item_name)
    
    elif args.command == "review":
        success = cli.review_code(args.filepath)
    
    elif args.command == "interactive":
        cli.interactive_mode()
        success = True
    
    else:
        print(CLIColors.error(f"❌ Unknown command: {args.command}"))
        parser.print_help()
        success = False
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()