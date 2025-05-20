#!/usr/bin/env python3
"""
Test script for the Kwork Node.js bridge.
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('test_node_bridge')

class NodeBridgeTester:
    def __init__(self):
        self.process = None
        self.node_path = self._find_node()
        self.script_path = Path(__file__).parent / 'scripts' / 'kwork_node_bridge.js'
        logger.info(f"Using Node.js at: {self.node_path}")
        logger.info(f"Using bridge script at: {self.script_path}")
    
    def _find_node(self) -> str:
        """Find the Node.js executable."""
        # First try the PATH
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Found Node.js version: {result.stdout.strip()}")
            return 'node'
        except (subprocess.SubprocessError, FileNotFoundError):
            # Try common installation paths
            common_paths = [
                'C:\\Program Files\\nodejs\\node.exe',
                'C:\\Program Files (x86)\\nodejs\\node.exe',
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Found Node.js at: {path}")
                    return path
            
            raise RuntimeError("Node.js not found. Please install Node.js from https://nodejs.org/")
    
    def start(self):
        """Start the Node.js bridge process."""
        if self.process is not None:
            logger.warning("Node.js bridge is already running")
            return
        
        logger.info("Starting Node.js bridge...")
        
        try:
            self.process = subprocess.Popen(
                [self.node_path, str(self.script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            if self.process.poll() is not None:
                _, stderr = self.process.communicate(timeout=5)
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else 'Unknown error'
                raise RuntimeError(f"Failed to start Node.js bridge: {error_msg}")
            
            logger.info("Node.js bridge started successfully")
            
        except Exception as e:
            self.process = None
            logger.error(f"Error starting Node.js bridge: {e}")
            raise
    
    def stop(self):
        """Stop the Node.js bridge process."""
        if self.process is not None:
            try:
                # Try to send a graceful shutdown command
                try:
                    self._send_command('close')
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Error sending close command: {e}")
                
                # Terminate the process
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Force killing Node.js bridge process")
                    self.process.kill()
                    self.process.wait()
                
                logger.info("Node.js bridge stopped")
                
            except Exception as e:
                logger.error(f"Error stopping Node.js bridge: {e}")
            finally:
                self.process = None
    
    def _send_command(self, command: str, **params) -> Dict[str, Any]:
        """Send a command to the Node.js bridge and return the response."""
        if self.process is None:
            raise RuntimeError("Node.js bridge is not running")
        
        if self.process.poll() is not None:
            raise RuntimeError("Node.js bridge process has terminated")
        
        # Prepare the command
        cmd = {
            'command': command,
            'params': params
        }
        
        cmd_json = json.dumps(cmd, ensure_ascii=False)
        logger.debug(f"Sending command: {cmd_json}")
        
        try:
            # Send the command
            self.process.stdin.write(f"{cmd_json}\n".encode('utf-8'))
            self.process.stdin.flush()
            
            # Read the response
            output = self.process.stdout.readline()
            if not output:
                raise RuntimeError("No response from Node.js bridge")
            
            output_str = output.decode('utf-8').strip()
            logger.debug(f"Received response: {output_str}")
            
            # Parse the response
            try:
                response = json.loads(output_str)
                if 'status' in response and response['status'] == 'error':
                    raise RuntimeError(f"Node.js bridge error: {response.get('message', 'Unknown error')}")
                return response.get('data', {})
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response as JSON: {output_str}")
                raise RuntimeError(f"Invalid JSON response: {output_str}")
            
        except Exception as e:
            logger.error(f"Error communicating with Node.js bridge: {e}")
            raise
    
    def test_connection(self):
        """Test the connection to the Node.js bridge."""
        try:
            logger.info("Testing connection to Node.js bridge...")
            response = self._send_command('init')
            logger.info(f"Connection test successful. Response: {response}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

def main():
    """Main function to test the Node.js bridge."""
    tester = NodeBridgeTester()
    
    try:
        # Start the bridge
        tester.start()
        
        # Test the connection
        if not tester.test_connection():
            logger.error("Failed to establish connection with Node.js bridge")
            return 1
        
        logger.info("Node.js bridge is working correctly!")
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    finally:
        # Always stop the bridge when done
        tester.stop()

if __name__ == "__main__":
    sys.exit(main())
