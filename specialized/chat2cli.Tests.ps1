
# chat2cli.ps1 的 Pester 测试。
#
# 重点覆盖 watch 循环的决策逻辑 Get-Chat2CLIWatchDecision：
# - 内容未变 → 整轮跳过
# - 生成内容 / 指令提示 → 记录后跳过
# - 新内容需要处理 → 处理并清空标记（允许重新复制同一请求再次执行）
# - 新内容不需要处理 → 记录后跳过

BeforeAll {
    . "$PSScriptRoot/chat2cli.ps1"
}

Describe 'Get-Chat2CLIWatchDecision' {
    BeforeAll {
        # 测试用委托：指定是否需要处理。
        # 在 BeforeAll 内定义，确保 It 运行时可见（Pester 6 作用域要求）。
        $needs = { param($t) $true }
        $notNeeds = { param($t) $false }
    }

    It '内容与上一轮相同则跳过，且标记不变' {
        $d = Get-Chat2CLIWatchDecision -Current 'SAME' -LastCheckedText 'SAME' `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $needs
        $d.ShouldProcess | Should -BeFalse
        $d.NextLastCheckedText | Should -Be 'SAME'
    }

    It '生成内容跳过，并记录为已处理输入' {
        $d = Get-Chat2CLIWatchDecision -Current 'OUTPUT' -LastCheckedText $null `
            -IsGenerated $true -IsInstruction $false -CheckNeedsProcessing $needs
        $d.ShouldProcess | Should -BeFalse
        $d.NextLastCheckedText | Should -Be 'OUTPUT'
    }

    It '指令提示跳过，并记录为已处理输入' {
        $d = Get-Chat2CLIWatchDecision -Current '<chat2cli_instruction>...</chat2cli_instruction>' `
            -LastCheckedText $null -IsGenerated $false -IsInstruction $true -CheckNeedsProcessing $needs
        $d.ShouldProcess | Should -BeFalse
        $d.NextLastCheckedText | Should -Be '<chat2cli_instruction>...</chat2cli_instruction>'
    }

    It '新内容需要处理时执行，并清空标记' {
        $d = Get-Chat2CLIWatchDecision -Current 'REQUEST' -LastCheckedText $null `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $needs
        $d.ShouldProcess | Should -BeTrue
        $d.NextLastCheckedText | Should -BeNullOrEmpty
    }

    It '新内容不需要处理时跳过，并记录' {
        $d = Get-Chat2CLIWatchDecision -Current 'plain talk' -LastCheckedText $null `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $notNeeds
        $d.ShouldProcess | Should -BeFalse
        $d.NextLastCheckedText | Should -Be 'plain talk'
    }

    It '处理成功后重新复制同一请求应再次处理' {
        # 第一轮：新请求，需要处理 → 清空标记
        $d1 = Get-Chat2CLIWatchDecision -Current 'V' -LastCheckedText $null `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $needs
        $d1.ShouldProcess | Should -BeTrue
        $mark = $d1.NextLastCheckedText
        $mark | Should -BeNullOrEmpty

        # 第二轮：剪贴板变为输出，跳过并记录
        $d2 = Get-Chat2CLIWatchDecision -Current 'OUTPUT' -LastCheckedText $mark `
            -IsGenerated $true -IsInstruction $false -CheckNeedsProcessing $needs
        $d2.ShouldProcess | Should -BeFalse
        $mark = $d2.NextLastCheckedText

        # 第三轮：用户重新复制相同的 V，标记已推进到 OUTPUT，应再次处理
        $d3 = Get-Chat2CLIWatchDecision -Current 'V' -LastCheckedText $mark `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $needs
        $d3.ShouldProcess | Should -BeTrue
    }

    It '不调用 CheckNeedsProcessing（内容未变时）' {
        $called = $false
        $probe = { param($t) $script:called = $true; $true }
        $d = Get-Chat2CLIWatchDecision -Current 'SAME' -LastCheckedText 'SAME' `
            -IsGenerated $false -IsInstruction $false -CheckNeedsProcessing $probe
        $script:called | Should -BeFalse
    }
}
