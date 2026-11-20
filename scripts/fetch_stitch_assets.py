import subprocess
import json
import os
import base64
import sys

OUTPUT_DIR = "/home/kanish/Documents/business-assistant/design"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "screens"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "screenshots"), exist_ok=True)

api_key = os.environ.get("STITCH_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")

cmd = [
    'npx', '-y', 'mcp-remote',
    'https://stitch.googleapis.com/mcp',
    '--header', f'X-Goog-Api-Key: {api_key}'
]

print("Starting Stitch MCP process...")
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

msg_id = 0

def call_mcp(method, params=None):
    global msg_id
    msg_id += 1
    req = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": method
    }
    if params is not None:
        req["params"] = params
    line = json.dumps(req) + "\n"
    p.stdin.write(line)
    p.stdin.flush()
    resp_line = p.stdout.readline()
    if not resp_line:
        err = p.stderr.read()
        raise RuntimeError(f"EOF from Stitch MCP: {err}")
    data = json.loads(resp_line)
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})

def call_tool(name, arguments):
    res = call_mcp("tools/call", {"name": name, "arguments": arguments})
    # content is usually a list of text objects
    content = res.get("content", [])
    if content and "text" in content[0]:
        try:
            return json.loads(content[0]["text"])
        except Exception:
            return content[0]["text"]
    return res

# 1. Initialize
print("Initializing MCP connection...")
call_mcp("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "stitch-asset-fetcher", "version": "1.0"}
})

# notification
p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
p.stdin.flush()

# 2. List Projects
print("Listing projects...")
projects_data = call_tool("list_projects", {})
with open(os.path.join(OUTPUT_DIR, "projects.json"), "w") as f:
    json.dump(projects_data, f, indent=2)

target_project = None
for proj in projects_data.get("projects", []):
    if proj.get("title") == "Live Agent Business Assistant" or "16089620894539968109" in proj.get("name", ""):
        target_project = proj
        break

if not target_project:
    print("Project 'Live Agent Business Assistant' not found!")
    sys.exit(1)

project_name = target_project["name"]
project_id = project_name.replace("projects/", "")
print(f"Target project found: {project_name} (ID: {project_id})")

# 3. Get Project Details
print("Fetching project details...")
proj_details = call_tool("get_project", {"name": project_name})
with open(os.path.join(OUTPUT_DIR, "project_details.json"), "w") as f:
    json.dump(proj_details, f, indent=2)

# Check for designSystem or design.md in project details
if "designSystem" in proj_details:
    print("Found designSystem in project details!")
    with open(os.path.join(OUTPUT_DIR, "design_system.json"), "w") as f:
        json.dump(proj_details["designSystem"], f, indent=2)

# 4. List Design Systems
try:
    print("Listing design systems for project...")
    ds_list = call_tool("list_design_systems", {"projectId": project_id})
    with open(os.path.join(OUTPUT_DIR, "design_systems_list.json"), "w") as f:
        json.dump(ds_list, f, indent=2)
except Exception as e:
    print(f"Notice: list_design_systems: {e}")

# 5. List Screens
print("Listing screens for project...")
screens_data = call_tool("list_screens", {"projectId": project_id})
with open(os.path.join(OUTPUT_DIR, "screens.json"), "w") as f:
    json.dump(screens_data, f, indent=2)

screens = screens_data.get("screens", [])
print(f"Found {len(screens)} screens.")

# 6. For each screen, download details, html, screenshot
for idx, s in enumerate(screens):
    s_name = s.get("name", "")
    s_id = s.get("id", s_name.split("/")[-1])
    s_title = s.get("title", f"screen_{idx}")
    print(f"\n--- Screen [{idx+1}/{len(screens)}]: {s_title} ({s_id}) ---")
    
    # get screen details
    try:
        s_detail = call_tool("get_screen", {"name": s_name})
        with open(os.path.join(OUTPUT_DIR, "screens", f"{s_id}_detail.json"), "w") as f:
            json.dump(s_detail, f, indent=2)
    except Exception as e:
        print(f"Error getting detail for {s_id}: {e}")
        s_detail = s

    # Download HTML
    html_name = None
    if "htmlCode" in s_detail and isinstance(s_detail["htmlCode"], dict):
        html_name = s_detail["htmlCode"].get("name")
    elif "html_code" in s_detail and isinstance(s_detail["html_code"], dict):
        html_name = s_detail["html_code"].get("name")
    elif "fileEntries" in s_detail:
        for fe in s_detail.get("fileEntries", []):
            if fe.get("name", "").endswith("/html") or "html" in fe.get("name", "").lower():
                html_name = fe.get("name")
                break

    if html_name:
        print(f"Downloading HTML for {s_title} ({html_name})...")
        try:
            html_res = call_tool("download_file", {"name": html_name})
            html_content = html_res.get("html", "") if isinstance(html_res, dict) else html_res
            with open(os.path.join(OUTPUT_DIR, "screens", f"{s_id}_{s_title.replace(' ', '_').replace('/', '_')}.html"), "w") as f:
                f.write(html_content)
            print(f"Saved HTML ({len(html_content)} chars)")
        except Exception as e:
            print(f"Error downloading HTML: {e}")

    # Download Screenshot
    screenshot_name = None
    if "screenshot" in s_detail and isinstance(s_detail["screenshot"], dict):
        screenshot_name = s_detail["screenshot"].get("name")
    elif "fileEntries" in s_detail:
        for fe in s_detail.get("fileEntries", []):
            if "screenshot" in fe.get("name", "").lower():
                screenshot_name = fe.get("name")
                break

    if screenshot_name:
        print(f"Downloading Screenshot for {s_title} ({screenshot_name})...")
        try:
            ss_res = call_tool("download_file", {"name": screenshot_name})
            if isinstance(ss_res, dict) and "image" in ss_res:
                img_data = base64.b64decode(ss_res["image"])
                with open(os.path.join(OUTPUT_DIR, "screenshots", f"{s_id}_{s_title.replace(' ', '_').replace('/', '_')}.png"), "wb") as f:
                    f.write(img_data)
                print(f"Saved Screenshot ({len(img_data)} bytes)")
        except Exception as e:
            print(f"Error downloading Screenshot: {e}")

p.terminate()
print("\nDone fetching all Stitch assets!")
