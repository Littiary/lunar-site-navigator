"""Talks to the editor's MCP server (Unreal MCP plugin, http://127.0.0.1:8000/mcp) directly.

A small client of the MCP streamable-HTTP transport with the standard library only, for
checking the connection from a terminal and for scripted editor steps:

    python mcp_probe.py list                      # toolsets of the editor
    python mcp_probe.py describe <toolset>        # tools of one toolset
    python mcp_probe.py call <tool> '<json args>' # call one tool

The editor must have been opened with Scripts/open_editor.ps1.
"""

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8000/mcp"


class Client:
    def __init__(self):
        self.session = None
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "lsn-mcp-probe", "version": "1"}})
        self.request("notifications/initialized", None, notify=True)

    def request(self, method, params, notify=False):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            self.next_id += 1
            body["id"] = self.next_id
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as response:
            self.session = response.headers.get("Mcp-Session-Id") or self.session
            text = response.read().decode("utf-8", errors="replace")
        if notify or not text.strip():
            return None
        if text.lstrip().startswith("{"):
            return json.loads(text)
        # Server-sent events: the last "data:" line holds the reply.
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1]) if data else None

    def call(self, tool, arguments):
        return self.request("tools/call", {"name": tool, "arguments": arguments})


def show(reply, limit=6000):
    text = json.dumps(reply, indent=1)
    print(text if len(text) <= limit else text[:limit] + f"\n... ({len(text)} characters)")


def main():
    client = Client()
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "tools":
        show(client.request("tools/list", {}))
    elif command == "list":
        show(client.call("list_toolsets", {}))
    elif command == "names":
        # One line per tool of a toolset: its name and what it takes.
        reply = client.call("describe_toolset", {"toolset_name": sys.argv[2]})
        for tool in json.loads(reply["result"]["content"][0]["text"])["tools"]:
            first = tool.get("description", "").strip().splitlines()[0] if tool.get("description") else ""
            print(f"{tool['name'].rsplit('.', 1)[-1]}({', '.join(tool.get('inputSchema', {}).get('properties', {}))})  {first}")
    elif command == "capture":
        # Saves the level viewport as the editor shows it: python mcp_probe.py capture <file.png>
        import base64
        reply = client.call("call_tool", {"toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport", "arguments": {"bShowUI": False}})
        saved = False
        for item in reply.get("result", {}).get("content", []):
            if item.get("type") == "image":
                with open(sys.argv[2], "wb") as handle:
                    handle.write(base64.b64decode(item["data"]))
                print(f"viewport capture saved: {sys.argv[2]} ({item.get('mimeType')}, {len(item['data']) * 3 // 4} bytes)")
                saved = True
            elif item.get("type") == "text":
                print(item["text"][:600])
        if not saved:
            show(reply, 1500)
    elif command == "describe":
        show(client.call("describe_toolset", {"toolset_name": sys.argv[2]}), 200000)
    elif command == "call":
        show(client.call(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}), 20000)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
