# 按 .gitattributes 声明的 eol 重写工作区文件的行尾。
#
# 为什么不能指望 git 自己做：git 比较内容前会先规范化行尾，LF 和 CRLF 在它眼中
# 是同一份内容 —— git status 不报告差异；更糟的是，当索引里记录的 stat 与磁盘
# 文件一致时，git checkout / checkout-index -f 会直接跳过写入，行尾永远修不回来。
# 但 cmd.exe 只认 CRLF，LF 行尾的 .cmd/.bat 会解析失败，因此部署时必须自己强制重写。
function Update-GitWorktreeEol {
    param(
        # 要处理的工作树路径
        [Parameter(Mandatory)]
        [string]$WorktreePath,

        # 传给 git ls-files 的 pathspec，例如 '*.cmd', '*.bat'，只在这些文件里筛选
        [Parameter(Mandatory)]
        [string[]]$Pathspec
    )

    # 关闭 quotepath，避免中文文件名被转义成 \3xx 形式
    $files = @(git -c core.quotepath=false -C $WorktreePath ls-files -- @Pathspec)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files 失败 (exit $LASTEXITCODE)"
    }
    if ($files.Count -eq 0) {
        return @()
    }

    # 只处理 .gitattributes 明确要求 eol=crlf 的文件；其余（lf、未设置）保持原样
    # -z 用 NUL 分隔输出 path / 属性名 / 属性值，避免文件名里的冒号或空格干扰解析
    $attrOutput = git -c core.quotepath=false -C $WorktreePath check-attr -z eol -- @files
    if ($LASTEXITCODE -ne 0) {
        throw "git check-attr 失败 (exit $LASTEXITCODE)"
    }
    $attrParts = ($attrOutput -join "`n").Split([char]0)
    $crlfFiles = [System.Collections.Generic.List[string]]::new()
    for ($i = 0; $i + 2 -lt $attrParts.Count; $i += 3) {
        if ($attrParts[$i + 2] -eq 'crlf') {
            $crlfFiles.Add($attrParts[$i])
        }
    }

    $rewritten = [System.Collections.Generic.List[string]]::new()
    foreach ($rel in $crlfFiles) {
        $path = Join-Path $WorktreePath $rel
        $bytes = [System.IO.File]::ReadAllBytes($path)

        # 找出裸 LF（前面不是 CR）；只按字节处理，避免改动 BOM、编码等其他内容
        $hasBareLf = $false
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 10 -and ($i -eq 0 -or $bytes[$i - 1] -ne 13)) {
                $hasBareLf = $true
                break
            }
        }
        if (-not $hasBareLf) {
            continue
        }

        $out = [System.Collections.Generic.List[byte]]::new($bytes.Length + 64)
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            $b = $bytes[$i]
            if ($b -eq 10 -and ($i -eq 0 -or $bytes[$i - 1] -ne 13)) {
                $out.Add([byte]13)
            }
            $out.Add($b)
        }
        [System.IO.File]::WriteAllBytes($path, $out.ToArray())
        $rewritten.Add($rel)
    }

    return $rewritten.ToArray()
}
