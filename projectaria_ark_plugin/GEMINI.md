# Aria ARK Development Guide

> **ARK** = Aria Research Kit — the developer toolset for Project Aria smart glasses.

## Tool Mapping

Skills use Claude Code tool names. When you encounter these in a skill, use your Gemini CLI equivalent:

| Skill references | Gemini CLI equivalent |
|-----------------|----------------------|
| `Read` (file reading) | `read_file` |
| `Write` (file creation) | `write_file` |
| `Edit` (file editing) | `replace` |
| `Bash` (run commands) | `run_shell_command` |
| `Grep` (search file content) | `grep_search` |
| `Glob` (search files by name) | `glob` |
| `WebSearch` | `google_web_search` |
| `WebFetch` | `web_fetch` |

## Skills

@./skills/aria-knowledge/SKILL.md
@./skills/client-sdk/SKILL.md
@./skills/client-sdk-ros2-integration/SKILL.md
@./skills/cloud-streaming/SKILL.md
@./skills/custom-profile/SKILL.md
@./skills/mps/SKILL.md
@./skills/pilot-dataset/SKILL.md
@./skills/projectaria-tools/SKILL.md
@./skills/vrs-cli/SKILL.md
@./skills/vrs-health-check/SKILL.md
@./skills/web-app-creator/SKILL.md
