function ConvertTo-GitRepoUrl {
    <#
    .SYNOPSIS
        将 gh 语义的 repository 参数转换为 HTTPS URL。

    .DESCRIPTION
        支持以下输入形式，与 gh 命令的 repository 参数语义一致：
          - https://host/owner/repo（原样返回）
          - user@host:owner/repo（scp 风格 SSH，转换为 HTTPS）
          - HOST/OWNER/REPO
          - OWNER/REPO（主机取 GH_HOST 或 github.com）
          - REPO（owner 取当前登录用户，仅此形式需要查询登录用户）

    .PARAMETER Repository
        待解析的仓库地址。

    .PARAMETER GetLogin
        接受主机名并返回登录用户名的脚本块，用于解析单段 REPO。
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Repository,

        [Parameter(Mandatory = $true)]
        [scriptblock]$GetLogin
    )

    $Repository = $Repository.Trim()

    # 已带协议头的完整 URL 原样返回
    if ($Repository -match '^https?://') {
        return $Repository
    }

    # scp 风格 SSH 地址：user@host:path
    if ($Repository -match '^[^@/]+@([^:/]+):(.+)$') {
        $sshHost = $Matches[1]
        $sshPath = $Matches[2] -replace '\.git$', ''
        return "https://$sshHost/$sshPath"
    }

    # 按 gh 语义解析 [HOST/]OWNER/REPO 或 REPO
    $segments = $Repository -split '/'
    $defaultHost = if ($env:GH_HOST) { $env:GH_HOST } else { 'github.com' }

    switch ($segments.Count) {
        1 {
            $hostName = $defaultHost
            $owner = & $GetLogin $hostName
            if ([string]::IsNullOrWhiteSpace($owner)) {
                throw "无法确定主机 $hostName 的登录用户，请提供 OWNER/REPO 形式的地址"
            }
            $repoPart = $segments[0]
        }
        2 {
            $hostName = $defaultHost
            $owner = $segments[0]
            $repoPart = $segments[1]
        }
        3 {
            $hostName = $segments[0]
            $owner = $segments[1]
            $repoPart = $segments[2]
        }
        default {
            throw "无法解析仓库地址 '$Repository'：段数过多"
        }
    }

    $repoPart = $repoPart -replace '\.git$', ''
    return "https://$hostName/$owner/$repoPart"
}

function New-GitWorkspace {
    <#
    .SYNOPSIS
        克隆 Git 仓库到工作区，使用分离的 Git 目录。
    
    .DESCRIPTION
        此函数接收一个 Git 仓库地址，将仓库克隆到指定的工作区目录，同时将 Git 目录分离到独立位置。
        工作区目录统一不包含 .git 后缀，Git 目录统一包含 .git 后缀。
        地址参数采用 gh 命令的 repository 语义，非完整 URL 会被自动补全为 HTTPS URL。
        指定 -Depth 时执行浅克隆，只拉取指定数量的提交，适合避免下载历史巨大的仓库
        （git 会同时只跟踪单一分支，默认分支）。
    
    .PARAMETER Url
        Git 仓库地址，语义与 gh 命令的 repository 参数一致：
        支持 https://host/owner/repo、user@host:owner/repo、HOST/OWNER/REPO、OWNER/REPO、REPO。
        非完整 URL 会被自动补全为 HTTPS URL。
    
    .PARAMETER Name
        可选参数，指定工作区目录的名称。如果未提供，则从 URL 中提取仓库名称。
    
    .PARAMETER Depth
        可选参数，浅克隆深度（传给 git clone 的 --depth）。省略或为 0 时执行完整克隆。
    
    .EXAMPLE
        New-GitWorkspace -Url "https://github.com/username/repository.git"
        
        克隆仓库到 C:/Workspaces/repository，Git 目录存储在 $env:LOCAL_GIT_DIR_ROOT/github.com/username/repository.git
    
    .EXAMPLE
        New-GitWorkspace -Url "https://gitlab.example.com:8080/group/project.git" -Name "my-project"
        
        克隆仓库到 C:/Workspaces/my-project，Git 目录存储在 $env:LOCAL_GIT_DIR_ROOT/gitlab.example.com/group/project.git（端口号被移除）
    
    .EXAMPLE
        New-GitWorkspace -Url "cli/cli"
        
        克隆 github.com/cli/cli 仓库
    
    .EXAMPLE
        New-GitWorkspace -Url "myrepo"
        
        克隆当前登录用户（通过 gh auth status 读取）名下的 myrepo 仓库
    
    .EXAMPLE
        New-GitWorkspace -Url "torvalds/linux" -Depth 1
        
        浅克隆 github.com/torvalds/linux，只拉取 1 个提交，避免下载完整历史
    
    .NOTES
        要求环境变量 LOCAL_GIT_ROOT 已定义，否则会抛出错误。
    #>
    
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        
        [Parameter(Mandatory = $false)]
        [string]$Name,
        
        # 0 表示完整克隆（不传 --depth）
        [Parameter(Mandatory = $false)]
        [ValidateRange(0, [int]::MaxValue)]
        [int]$Depth = 0
    )
    
    # 常量定义
    $WorkspacesRoot = $env:LOCAL_WORKSPACES_ROOT ?? "C:/Workspaces"
    
    # 检查必要的环境变量
    if (-not $env:LOCAL_GIT_ROOT) {
        Write-Error "环境变量 LOCAL_GIT_ROOT 未定义"
        return 
    }
    
    # 将 gh 语义的 repository 参数补全为 HTTPS URL
    $Url = ConvertTo-GitRepoUrl -Repository $Url -GetLogin {
        param($hostName)
        $status = gh auth status --hostname $hostName --json hosts 2>$null | ConvertFrom-Json
        if (-not $status) { return $null }
        $status.hosts.$hostName | Where-Object { $_.active } | Select-Object -First 1 -ExpandProperty login
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
    
    if ($Depth -gt 0) {
        Write-Host "克隆深度: $Depth" -ForegroundColor Yellow
    }
    
    # 直接在当前目录执行 git clone，指定完整的目标路径
    $cloneArgs = @('clone')
    if ($Depth -gt 0) {
        $cloneArgs += '--depth', $Depth
    }
    $cloneArgs += "--separate-git-dir=$gitDir", $Url, $workspaceDir
    git @cloneArgs
    
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
