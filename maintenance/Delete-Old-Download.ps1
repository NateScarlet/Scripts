$folder = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path
Get-ChildItem $folder | Where-Object { $_.LastAccessTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Remove-Item -Recurse $_ }
