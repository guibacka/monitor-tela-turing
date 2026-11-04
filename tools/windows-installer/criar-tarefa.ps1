# Cria (ou atualiza) a tarefa agendada que inicia o Monitor da Tela Turing ao entrar no Windows, como administrador.
# Usado pelo instalador. A pasta de início precisa ser a do programa: a leitura de sensores procura os arquivos a partir dela.
param(
    [Parameter(Mandatory = $true)][string]$AppDir,
    [string]$User = "$env:USERDOMAIN\$env:USERNAME"
)
$ErrorActionPreference = 'Stop'
$action = New-ScheduledTaskAction -Execute (Join-Path $AppDir 'main.exe') -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$trigger.Delay = 'PT15S'  # dá tempo da tela USB ser reconhecida
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'Monitor da Tela Turing' -Force `
    -Description 'Inicia o Monitor da Tela Turing 3,5" ao entrar no Windows, como administrador (temperaturas, saúde dos SSDs e FPS).' `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
