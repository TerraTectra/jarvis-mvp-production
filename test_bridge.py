import json
import subprocess
import sys
import time

def send_command(command, **params):
    # Prepare the command data
    command_data = {"command": command, "params": params}
    command_json = json.dumps(command_data, ensure_ascii=False) + "\n"
    
    # Start the Node.js bridge process
    process = subprocess.Popen(
        ["node", "scripts/kwork_node_bridge.js"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Send the command
    print(f"Sending command: {command_json.strip()}")
    process.stdin.write(command_json)
    process.stdin.flush()
    
    # Read the response
    print("Waiting for response...")
    response = process.stdout.readline()
    print(f"Response: {response}")
    
    # Clean up
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    
    return response

if __name__ == "__main__":
    # Test the bridge with a simple command
    response = send_command("ping")
    print(f"Test response: {response}")
