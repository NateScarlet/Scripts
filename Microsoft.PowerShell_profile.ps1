$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
