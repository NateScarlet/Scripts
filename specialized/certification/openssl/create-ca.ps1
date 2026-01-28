<#
.SYNOPSIS
创建根CA证书（长期使用，只需执行一次）

.DESCRIPTION
生成CA私钥和自签名根证书，支持从Git配置获取创建者信息，
并在覆盖已有CA文件前自动备份。

.EXAMPLE
.\create_ca.ps1
.\create_ca.ps1 -Force  # 强制覆盖已有CA（自动备份）
#>

param(
    [switch]$Force = $false  # 强制覆盖模式
)

# 配置参数
$caName = "HomeNetworkCA"
$validityDays = 3650  # CA有效期（10年）
$keyLength = 4096     # 密钥长度
$outputDir = ".\ca"   # 输出目录
$backupDir = ".\ca\backup"  # 备份目录

# 尝试从Git获取用户信息
try {
    $gitUserName = git config --global user.name
    $gitUserEmail = git config --global user.email
}
catch {
    Write-Host "未找到Git配置，将不使用创建者信息" -ForegroundColor Yellow
    $gitUserName = $null
    $gitUserEmail = $null
}

# 创建输出目录
if (-not (Test-Path -Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

# 检查CA文件是否已存在
$caKeyPath = "$outputDir\$caName.key"
$caCertPath = "$outputDir\$caName.crt"
$caSerialPath = "$outputDir\$caName.srl"

$caFilesExist = (Test-Path $caKeyPath) -or (Test-Path $caCertPath)

if ($caFilesExist -and -not $Force) {
    Write-Host "检测到已有CA文件存在！" -ForegroundColor Red
    Write-Host "请使用 -Force 参数强制覆盖（将自动备份原有文件）"
    exit 1
}

# 备份现有CA文件
if ($caFilesExist) {
    Write-Host "正在备份原有CA文件..." -ForegroundColor Yellow
    
    # 创建备份目录（带时间戳）
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $currentBackupDir = "$backupDir\$timestamp"
    
    if (-not (Test-Path -Path $currentBackupDir)) {
        New-Item -ItemType Directory -Path $currentBackupDir | Out-Null
    }
    
    # 备份所有CA相关文件
    $filesToBackup = @($caKeyPath, $caCertPath, $caSerialPath) | Where-Object { Test-Path $_ }
    
    if ($filesToBackup.Count -gt 0) {
        Copy-Item -Path $filesToBackup -Destination $currentBackupDir
        Write-Host "已备份到: $currentBackupDir" -ForegroundColor Green
    }
    else {
        Write-Host "未找到可备份的CA文件" -ForegroundColor Yellow
    }
}

# 构建证书主题（根据可用信息）
$subjectParts = @("/CN=$caName")

if ($gitUserName) {
    $subjectParts += "/O=$gitUserName"
}

if ($gitUserEmail) {
    $subjectParts += "/emailAddress=$gitUserEmail"
}

$subject = $subjectParts -join ""

# 1. 生成CA私钥
Write-Host "`n生成CA私钥..." -ForegroundColor Cyan
openssl genrsa -out $caKeyPath $keyLength

# 2. 初始化序列号文件
Write-Host "初始化序列号文件..." -ForegroundColor Cyan
"01" | Out-File -FilePath $caSerialPath -Encoding ASCII

# 3. 生成自签名CA证书
Write-Host "生成CA证书..." -ForegroundColor Cyan
openssl req -x509 -new -nodes -key $caKeyPath -sha256 -days $validityDays `
    -out $caCertPath -subj $subject `
    -addext "keyUsage=critical,digitalSignature,keyCertSign"

# 4. 验证生成的CA证书
Write-Host "`nCA证书信息:" -ForegroundColor Green
openssl x509 -in $caCertPath -text -noout | Select-String -Pattern "Subject:|Issuer:|Validity|emailAddress" -Context 0, 2

# 5. 显示重要提示
Write-Host @"

===================== 重要安全提示 =====================
1. 请妥善保管以下文件（它们是整个PKI体系的基础）:
   - CA私钥: $caKeyPath
   - CA证书: $caCertPath
   - 序列号文件: $caSerialPath

2. 建议将这些文件:
   - 存储在安全位置
   - 加密备份
   - 不要共享私钥

3. 下次签发证书时使用:
   .\issue-cert.ps1 -Domains "your.domains" -CertName "cert_name"
"@ -ForegroundColor Magenta

# 6. 设置文件权限（可选）
try {
    # 限制CA私钥的访问权限
    icacls $caKeyPath /inheritance:r /grant:r "$env:USERNAME:(R)"
    Write-Host "已设置CA私钥文件权限" -ForegroundColor Cyan
}
catch {
    Write-Host "无法设置文件权限（非Windows系统？）" -ForegroundColor Yellow
}
