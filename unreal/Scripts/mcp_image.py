"""Calls an image-returning tool of the editor's MCP server and saves the picture.

    python mcp_image.py editor <file.png>      # the whole editor window, as the user sees it (shows a running play session)

Uses the client of mcp_probe.py. The editor must have been opened with Scripts/open_editor.ps1.
"""
import base64
import json
import re
import sys

from mcp_probe import Client


def main():
    client = Client()
    tool = {"editor": "CaptureEditorImage"}[sys.argv[1]]
    reply = client.call("call_tool", {"toolset_name": "EditorToolset.EditorAppToolset", "tool_name": tool, "arguments": {}})
    for item in reply.get("result", {}).get("content", []):
        data = item.get("data") if item.get("type") == "image" else None
        if data is None and item.get("type") == "text":
            found = re.search(r'[A-Za-z0-9+/=]{2000,}', item["text"])
            data = found.group(0) if found else None
        if data:
            with open(sys.argv[2], "wb") as handle:
                handle.write(base64.b64decode(data))
            print(f"saved {sys.argv[2]}")
            return
    print(json.dumps(reply)[:600])


if __name__ == "__main__":
    main()
