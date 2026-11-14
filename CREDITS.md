# Credits

Every third-party item used in this project gets one row here before it is merged.

## Data

| Name | Provider | Version or product ID | Licence or terms | Source URL | Retrieved (UTC) |
|---|---|---|---|---|---|

## Software libraries

| Name | Version | Licence | Source URL | Used in |
|---|---|---|---|---|
| Unreal Engine (with its ProceduralMeshComponent and Python editor plugins and engine default font) | 5.8.4 | Unreal Engine EULA (not an OSI licence; free to download and use) | https://www.unrealengine.com/eula/unreal | `unreal/` |
| FFmpeg (tool; joins rendered frames into the clips under `docs/unreal/`, not shipped) | 8.1.2 | LGPL 2.1 or later / GPL 2 or later, depending on the build | https://ffmpeg.org/ | `unreal/Scripts/record.ps1` |

## Images, fonts and other assets

| Name | Author or provider | Licence | Source URL | Used in |
|---|---|---|---|---|

## Use of AI tools

| Team member | Tool and model | Used for |
|---|---|---|
| Kaan | Claude Code (Anthropic); on the build machine model `claude-fable-5-2` | Unreal stream (`unreal/`): C++ source, tests, scripts. The two materials in `unreal/Content/Lsn/` were generated in the Unreal editor by the script `unreal/Scripts/make_materials.py`, which the assistant wrote; they contain no image or texture. |
