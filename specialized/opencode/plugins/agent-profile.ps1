# Agent shell profile
# Runs before every bash-tool command (injected by the agent-profile plugin, since opencode launches pwsh with -NoProfile).
# Customize the agent's shell environment here: encoding, aliases, PSDefaultParameterValues, env vars, etc.

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
