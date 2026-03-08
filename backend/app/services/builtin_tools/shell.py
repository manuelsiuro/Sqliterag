"""Built-in tool: run_shell — Execute a command in the browser-side Alpine Linux VM.

The actual execution happens on the frontend (v86 emulator) via the frontend
bridge. This builtin returns a JSON fallback if the bridge is not available.
"""

import json


async def run_shell(command: str) -> str:
    """Queue a shell command for execution in the Alpine Linux VM."""
    # This fallback is only reached when the frontend bridge is disabled
    # or unavailable. Normally, agent_base.py intercepts execution_type="frontend"
    # tools before this function is called.
    return json.dumps({
        "type": "shell_result",
        "command": command,
        "output": "",
        "error": "Frontend bridge not available. The Linux VM must be running in the browser.",
    })
