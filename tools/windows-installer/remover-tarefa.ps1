# Usado pelo desinstalador (e antes de atualizar): encerra o monitor, o editor e o PresentMon desta instalação
# e, se não for -KeepTask, remove a tarefa agendada. Fica na pasta do programa ($PSScriptRoot).
param([switch]$KeepTask)
$ErrorActionPreference = 'SilentlyContinue'
Get-Process -Name 'main', 'editor', 'configure', 'iniciar-monitor', 'PresentMon' |
    Where-Object { $_.Path -and $_.Path.StartsWith($PSScriptRoot, [StringComparison]::OrdinalIgnoreCase) } |
    Stop-Process -Force
if (-not $KeepTask) {
    Unregister-ScheduledTask -TaskName 'Monitor da Tela Turing' -Confirm:$false
}
