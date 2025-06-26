#!/usr/bin/env python3
"""
Claude Code Agent Implementation - Headless Mode
"""

import subprocess
import json
import os
from typing import Optional
from .base import CodingAgent, AgentResponse
from common.exceptions import AgentTimeoutException
from common.config import config

class ClaudeCodeAgent(CodingAgent):
    """Claude Code agent implementation using headless mode"""
    
    def __init__(self, claude_computer_use):
        super().__init__(claude_computer_use)
        self.repo_dir = os.getcwd()
    
    @property
    def window_name(self) -> str:
        return "Claude Code"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return None  # Not needed for headless mode
    
    @property
    def interface_state_prompt(self) -> str:
        # Not used in headless mode
        return ""
    
    @property
    def resume_button_prompt(self) -> str:
        # Not used in headless mode
        return ""
    
    @property
    def input_field_prompt(self) -> str:
        # Not used in headless mode
        return ""

    def _display_claude_progress(self, json_obj: dict) -> None:
        """Display Claude's progress based on JSON streaming output"""
        if json_obj.get('type') == 'system':
            if json_obj.get('subtype') == 'init':
                print(f"Initializing Claude session...")
                print(f"   Model: {json_obj.get('model', 'unknown')}")
                tools = json_obj.get('tools', [])
                if tools:
                    print(f"   Available tools: {', '.join(tools[:5])}{'...' if len(tools) > 5 else ''}")
        
        elif json_obj.get('type') == 'assistant':
            message = json_obj.get('message', {})
            content = message.get('content', [])
            
            for content_item in content:
                if content_item.get('type') == 'text':
                    text = content_item.get('text', '')
                    if text.strip():
                        print(f"\n{text}")
                
                elif content_item.get('type') == 'tool_use':
                    tool_name = content_item.get('name', 'unknown')
                    print(f"\nUsing tool: {tool_name}")
                    
                    # Show some details about the tool use
                    if tool_name == 'Write':
                        input_data = content_item.get('input', {})
                        file_path = input_data.get('file_path', '')
                        if file_path:
                            print(f"   Creating file: {os.path.basename(file_path)}")
                    elif tool_name == 'Edit':
                        input_data = content_item.get('input', {})
                        file_path = input_data.get('file_path', '')
                        if file_path:
                            print(f"   Editing file: {os.path.basename(file_path)}")
                    elif tool_name == 'Read':
                        input_data = content_item.get('input', {})
                        file_path = input_data.get('file_path', '')
                        if file_path:
                            print(f"   Reading file: {os.path.basename(file_path)}")
                    elif tool_name == 'Bash':
                        input_data = content_item.get('input', {})
                        command = input_data.get('command', '')
                        if command:
                            print(f"   Running: {command[:50]}{'...' if len(command) > 50 else ''}")
        
        elif json_obj.get('type') == 'user':
            message = json_obj.get('message', {})
            content = message.get('content', [])
            
            for content_item in content:
                if content_item.get('type') == 'tool_result':
                    result_content = content_item.get('content', '')
                    if 'successfully' in result_content.lower():
                        print(f"   Success")
                    elif 'error' in result_content.lower() or 'failed' in result_content.lower():
                        print(f"   Error: {result_content[:100]}...")
                    else:
                        print(f"   {result_content[:100]}{'...' if len(result_content) > 100 else ''}")
        
        elif json_obj.get('type') == 'result':
            if json_obj.get('subtype') == 'success':
                result = json_obj.get('result', '')  
                cost = json_obj.get('cost_usd', 0)
                duration = json_obj.get('duration_ms', 0)
                print(f"\nTask completed successfully!")
                if result:
                    print(f"   Result: {result}")
                print(f"   Duration: {duration/1000:.1f}s, Cost: ${cost:.4f}")
            else:
                print(f"\nTask failed: {json_obj.get('error', 'Unknown error')}")

    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute prompt in headless mode with file output"""
        print("\nWARNING: This will execute Claude with --dangerously-skip-permissions")
        print("This gives Claude full access to execute commands in the repository directory")
        approval = input("Do you want to continue? (y/n): ")
        if approval.lower() != 'y':
            return AgentResponse(
                content="Operation cancelled by user",
                success=False,
                error_message="User did not approve execution with dangerous permissions"
            )

        try:
            # Combine the original prompt with instruction to save output
            combined_prompt = f"""{prompt}\n\nAfter completing the above task, please save a comprehensive summary of everything you did to a file called '{self.output_file}' in the current directory. Include:\n- All changes made\n- Explanations of what was done.\n\nIMPORTANT: Do NOT create or update any documentation files (such as README.md or docs/*) unless you are explicitly asked to do so in the original prompt. If you believe that creating a documentation file would help you better implement the required coding task, you may create it, but you must delete it once you are finished and before you finish the task."""
            
            # Use claude command with headless mode flags
            cmd = [
                'claude',
                '-p', combined_prompt,
                '--output-format', 'stream-json',
                '--dangerously-skip-permissions'
            ]
            
            print(f"Executing prompt in {self.agent_name} headless mode. Prompt: {prompt}")
            print("Streaming Claude's response in real-time...")
            print("-" * 50)

            # Use Popen for real-time streaming
            process = subprocess.Popen(
                cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Stream output in real-time
            stdout_lines = []
            stderr_lines = []
            
            try:
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        stdout_lines.append(output.strip())
                        # Parse and display JSON streaming output
                        try:
                            json_obj = json.loads(output.strip())
                            self._display_claude_progress(json_obj)
                        except json.JSONDecodeError:
                            # Not JSON, might be regular output
                            if output.strip():
                                print(f"[Output]: {output.strip()}")
                
                # Wait for process to complete and get return code
                timeout_seconds = config.agent_timeout_seconds
                return_code = process.wait(timeout=timeout_seconds)
                
                # Capture any remaining stderr
                stderr_output = process.stderr.read()
                if stderr_output:
                    stderr_lines.append(stderr_output)
                
                print(f"\n{'-' * 50}")
                print(f"Claude execution completed with return code: {return_code}")
                
            except subprocess.TimeoutExpired:
                process.kill()
                raise AgentTimeoutException(self.agent_name, timeout_seconds, "Claude command execution timed out")
            
            if return_code == 0:
                # Now read the output file
                print(f"Reading output from {self.output_file}...")
                content = await self._read_output_file()
                
                return AgentResponse(
                    content=content,
                    success=True
                )
            else:
                error_msg = '\n'.join(stderr_lines) or f"Command failed with return code {return_code}"
                print(f"ERROR: Claude command failed: {error_msg}")
                return AgentResponse(
                    content="",
                    success=False,
                    error_message=error_msg
                )
                
        except subprocess.TimeoutExpired:
            
            raise AgentTimeoutException(self.agent_name, config.agent_timeout_seconds, "Claude command timed out")
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Failed to execute Claude command: {str(e)}"
            )

    async def is_coding_agent_open(self) -> bool:
        """Check if Claude Code is available (command exists and can run)"""
        try:
            # Check if claude command is available
            result = subprocess.run(
                ['which', 'claude'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"SUCCESS: Claude Code command is available at {result.stdout.strip()}")
                return True
            else:
                print(f"INFO: Claude Code command not found in PATH")
                return False
                
        except Exception as e:
            print(f"INFO: Could not check for Claude Code command: {str(e)}")
            return False
    
    def is_ide_open_with_correct_project(self) -> bool:
        """Check if Claude Code is in the correct project directory
        
        For headless mode, this means checking if we're in the correct working directory
        """
        if not self._current_project_name:
            print(f"Warning: No project name set for {self.agent_name}, cannot verify project-specific directory")
            return False
        
        current_dir = os.getcwd()
        current_project = os.path.basename(current_dir)
        
        if self._current_project_name.lower() in current_project.lower():
            print(f"SUCCESS: Claude Code is in the correct project directory '{current_project}'")
            return True
        else:
            print(f"Claude Code is in directory '{current_project}' but expected project '{self._current_project_name}'")
            return False
    
    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if Claude Code is available AND in the correct project directory
        
        This combines command availability checking with project directory verification.
        
        Returns:
            bool: True if Claude Code is available and in the correct project directory, False otherwise
        """
        # First check if the command is available
        if not await self.is_coding_agent_open():
            return False
            
        # Then check if we're in the correct project directory
        if not self.is_ide_open_with_correct_project():
            print(f"{self.agent_name} command is available but not in the correct project directory '{self._current_project_name}'")
            return False
            
        print(f"SUCCESS: {self.agent_name} is available and in the correct project directory '{self._current_project_name}'")
        return True
    
    async def open_coding_interface(self) -> bool:
        """Verify Claude Code is available and ready for headless mode with correct project"""
        print(f"Checking {self.agent_name} availability...")
        
        # Set current project if we have a repo_dir
        if hasattr(self, 'repo_dir') and self.repo_dir:
            self.set_current_project(self.repo_dir)
        
        # Check if available and in correct project
        if await self.is_coding_agent_open_with_project():
            print(f"SUCCESS: {self.agent_name} is ready for headless operation in correct project")
            return True
        else:
            # If command is available but wrong directory, try to change to correct directory
            if await self.is_coding_agent_open():
                if self._current_project_name:
                    print(f"Claude Code is available but not in correct project directory")
                    print(f"Current directory: {os.getcwd()}")
                    print(f"Expected project: {self._current_project_name}")
                    print(f"Note: For headless mode, ensure you're running from the correct project directory")
                return False
            else:
                print(f"ERROR: {self.agent_name} command not available. Please install Claude Code.")
                print("Install instructions: https://github.com/anthropics/claude-code")
                return False
    
    async def close_coding_interface(self) -> bool:
        """Close Claude Code interface (no-op for headless mode)
        
        For headless mode, there's no persistent interface to close.
        This method exists for consistency with other agents.
        """
        print(f"INFO: {self.agent_name} is headless - no interface to close")
        print(f"Headless agents don't maintain persistent interfaces that need closing")
        return True 