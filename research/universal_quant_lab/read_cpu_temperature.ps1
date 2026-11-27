param([string]$Root = 'D:\UniversalQuantLab', [switch]$Once)
$ErrorActionPreference = 'Stop'
$target = Join-Path $Root 'logs\cpu-thermal.json'
do {
    $sensors = @(Get-CimInstance -Namespace root\LibreHardwareMonitor -ClassName Sensor |
        Where-Object { $_.SensorType -eq 'Temperature' -and $_.Identifier -match '^/(intel|amd)cpu/' -and
            $null -ne $_.Value -and $_.Value -gt 0 -and $_.Value -le 125 })
    $package = @($sensors | Where-Object Name -eq 'CPU Package')
    $cores = @($sensors | Where-Object Name -match '^CPU Core #[0-9]+$')
    if (!$package.Count -or !$cores.Count) { throw 'CPU package and individual core temperatures are required' }
    $sample = @{
        updated_utc = [DateTimeOffset]::UtcNow.ToString('o')
        cpu_celsius = (($package + $cores) | Measure-Object Value -Maximum).Maximum
        package_celsius = $package[0].Value
        cores = @($cores | Select-Object Name,Value)
        source = 'LibreHardwareMonitor WMI'
    }
    $temp = "$target.$PID.tmp"
    [IO.File]::WriteAllText($temp, ($sample | ConvertTo-Json -Depth 4))
    if ([IO.File]::Exists($target)) { [IO.File]::Replace($temp,$target,$null) }
    else { [IO.File]::Move($temp,$target) }
    if (!$Once) { Start-Sleep -Seconds 3 }
} while (!$Once)
