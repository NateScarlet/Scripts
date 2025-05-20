<#
.SYNOPSIS
使用现有CA签发新证书

.DESCRIPTION
根据提供的域名生成新的证书，支持通配符

.PARAMETER Domains
要包含在证书中的域名列表（逗号分隔），例如 "*.home.arpa,*.*.home.arpa"

.PARAMETER CertName
输出证书的名称（不含扩展名）

.PARAMETER ValidityDays
证书有效期（天），默认365天

.PARAMETER CaCertPath
CA证书路径，默认".\ca\HomeNetworkCA.crt"

.PARAMETER CaKeyPath
CA私钥路径，默认".\ca\HomeNetworkCA.key"

.EXAMPLE
.\issue_cert.ps1 -Domains "*.home.arpa,*.*.home.arpa" -CertName "wildcard_home_arpa"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Domains,
    
    [Parameter(Mandatory = $true)]
    [string]$CertName,
    
    [int]$ValidityDays = 365,
    
    [string]$CaCertPath = ".\ca\HomeNetworkCA.crt",
    
    [string]$CaKeyPath = ".\ca\HomeNetworkCA.key"
)

# 创建输出目录
$outputDir = ".\certs"
if (-not (Test-Path -Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

# 1. 生成私钥
Write-Host "生成私钥..." -ForegroundColor Cyan
openssl genrsa -out "$outputDir\$CertName.key" 2048

# 2. 准备CSR配置
$primaryDomain = ($Domains -split ",")[0]

$sanEntries = @()
$dnsCount = 1
$ipCount = 1

foreach ($item in $Domains -split ",") {
    if ($item -match '^\d+\.\d+\.\d+\.\d+$') {
        $sanEntries += "IP.$ipCount = $item"
        $ipCount++
    }
    else {
        $sanEntries += "DNS.$dnsCount = $item"
        $dnsCount++
    }
}


$csrConfig = @"
[req]
default_bits = 204
prompt = no
default_md = sha256
distinguished_name = dn

[dn]
CN = $primaryDomain
"@

$csrConfig | Out-File -FilePath "$outputDir\$CertName.csr.conf" -Encoding ascii

# 3. 生成CSR
Write-Host "生成证书签名请求(CSR)..." -ForegroundColor Cyan
openssl req -new -key "$outputDir\$CertName.key" -out "$outputDir\$CertName.csr" -config "$outputDir\$CertName.csr.conf"

# 4. 准备证书扩展配置
$certExtConfig = @"
authorityKeyIdentifier=keyid,issuer
basicConstraints=critical,CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName=critical,@alt_names

[alt_names]
$($sanEntries -replace "^","" -join "`n")
"@

$certExtConfig | Out-File -FilePath "$outputDir\$CertName.ext.conf" -Encoding ascii

# 5. 使用CA签发证书
Write-Host "使用CA签发证书..." -ForegroundColor Cyan
openssl x509 -req -in "$outputDir\$CertName.csr" -CA $CaCertPath -CAkey $CaKeyPath -CAcreateserial `
    -out "$outputDir\$CertName.crt" -days $ValidityDays -sha256 -extfile "$outputDir\$CertName.ext.conf"

# 6. 清理临时文件
# Remove-Item "$outputDir\$CertName.csr"
# Remove-Item "$outputDir\$CertName.csr.conf"
# Remove-Item "$outputDir\$CertName.ext.conf"

# 7. 显示结果
Write-Host "`n证书签发完成！" -ForegroundColor Green
Write-Host "私钥: $outputDir\$CertName.key" -ForegroundColor Yellow
Write-Host "证书: $outputDir\$CertName.crt" -ForegroundColor Yellow

# 8. 验证证书
Write-Host "`n证书信息:" -ForegroundColor Cyan
openssl x509 -in "$outputDir\$CertName.crt" -text -noout | Select-String -Pattern "Subject:|Issuer:|Validity|DNS:" -Context 0, 5
