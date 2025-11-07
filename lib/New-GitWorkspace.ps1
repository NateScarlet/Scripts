function New-GitWorkspace {
    <#
    .SYNOPSIS
        克隆 Git 仓库到工作区，使用分离的 Git 目录。
    
    .DESCRIPTION
        此函数接收一个 Git HTTP URL，将仓库克隆到指定的工作区目录，同时将 Git 目录分离到独立位置。
        工作区目录统一不包含 .git 后缀，Git 目录统一包含 .git 后缀。
    
    .PARAMETER Url
        Git 仓库的 HTTP 或 HTTPS URL。
    
    .PARAMETER Name
        可选参数，指定工作区目录的名称。如果未提供，则从 URL 中提取仓库名称。
    
    .EXAMPLE
        New-GitWorkspace -Url "https://github.com/username/repository.git"
        
        克隆仓库到 C:/Workspaces/repository，Git 目录存储在 $env:LOCAL_GIT_DIR_ROOT/github.com/username/repository.git
    
    .EXAMPLE
        New-GitWorkspace -Url "https://gitlab.example.com:8080/group/project.git" -Name "my-project"
        
        克隆仓库到 C:/Workspaces/my-project，Git 目录存储在 $env:LOCAL_GIT_DIR_ROOT/gitlab.example.com/group/project.git（端口号被移除）
    
    .NOTES
        要求环境变量 LOCAL_GIT_ROOT 已定义，否则会抛出错误。
    #>
    
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        
        [Parameter(Mandatory = $false)]
        [string]$Name
    )
    
    # 常量定义
    $WorkspacesRoot = $env:LOCAL_WORKSPACES_ROOT ?? "C:/Workspaces"
    
    # 检查必要的环境变量
    if (-not $env:LOCAL_GIT_ROOT) {
        Write-Error "环境变量 LOCAL_GIT_ROOT 未定义"
        return 
    }
    
    # 验证 URL 格式
    if ($Url -notmatch '^https?://') {
        Write-Error "URL 格式不正确，必须以 http:// 或 https:// 开头"
        return
    }
    
    # 解析 URL
    $uri = [System.Uri]$Url
    
    # 检查路径部分是否为空
    $pathPart = $uri.AbsolutePath.Trim('/')
    if ([string]::IsNullOrEmpty($pathPart)) {
        Write-Error "URL 路径部分不能为空，必须指定具体的仓库路径"
        return
    }
    
    # 构建 git dir 路径（去掉协议头和端口号）
    $hostPart = $uri.Host
    if ($pathPart.EndsWith('.git')) {
        $pathPart = $pathPart.Substring(0, $pathPart.Length - 4)
    }
    
    $gitDirPath = Join-Path $hostPart $pathPart
    $gitDir = Join-Path $env:LOCAL_GIT_ROOT "$gitDirPath.git"
    
    # 确定仓库名称
    if ($Name) {
        $repoName = $Name
    }
    else {
        # 从 URL 中提取仓库名称
        $repoName = $pathPart.Split('/')[-1]
    }
    
    # 工作区目录（确保没有 .git 后缀）
    if ($repoName.EndsWith('.git')) {
        $repoName = $repoName.Substring(0, $repoName.Length - 4)
    }
    $workspaceDir = Join-Path $WorkspacesRoot $repoName
    
    # 创建必要的目录
    $gitDirParent = Split-Path $gitDir -Parent
    if (-not (Test-Path $gitDirParent)) {
        New-Item -ItemType Directory -Path $gitDirParent -Force | Out-Null
        Write-Host "已创建 Git 目录父路径: $gitDirParent" -ForegroundColor Gray
    }
    
    if (-not (Test-Path $WorkspacesRoot)) {
        New-Item -ItemType Directory -Path $WorkspacesRoot -Force | Out-Null
        Write-Host "已创建工作区根目录: $WorkspacesRoot" -ForegroundColor Gray
    }
    
    # 检查目标目录是否已存在
    if (Test-Path $workspaceDir) {
        Write-Error "工作区目录已存在: $workspaceDir"
        return
    }
    
    if (Test-Path $gitDir) {
        Write-Error "Git 目录已存在: $gitDir"
        return
    }
    
    # 执行 git clone
    Write-Host "正在克隆仓库..." -ForegroundColor Green
    Write-Host "URL: $Url" -ForegroundColor Yellow
    Write-Host "工作区: $workspaceDir" -ForegroundColor Yellow
    Write-Host "Git目录: $gitDir" -ForegroundColor Yellow
    
    if ($Name) {
        Write-Host "自定义工作区名称: $Name" -ForegroundColor Yellow
    }
    
    # 直接在当前目录执行 git clone，指定完整的目标路径
    git clone --separate-git-dir="$gitDir" "$Url" "$workspaceDir"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "克隆成功！" -ForegroundColor Green
        Write-Host "工作区: $workspaceDir" -ForegroundColor Cyan
        Write-Host "Git目录: $gitDir" -ForegroundColor Cyan
        
        # 返回克隆信息
        return [PSCustomObject]@{
            Workspace = $workspaceDir
            GitDir    = $gitDir
            RepoName  = $repoName
        }
    }
    else {
        Write-Error "git clone 执行失败，退出码: $LASTEXITCODE"
        return
    }
}
