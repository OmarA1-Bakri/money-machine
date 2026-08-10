param(
    [Parameter(Mandatory = $true)]
    [string]$Packet
)

$ErrorActionPreference = "Stop"
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Invoke-MoneyMachine {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & $PythonBin -m money_machine.cli.main @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Money Machine command failed with exit code $LASTEXITCODE"
    }
    return ($output | Select-Object -Last 1)
}

Invoke-MoneyMachine db migrate --json | Write-Output
$importReceipt = Invoke-MoneyMachine research import --packet $Packet --json
$importReceipt | Write-Output
$packetId = ($importReceipt | ConvertFrom-Json).packet_id

$startReceipt = Invoke-MoneyMachine workflow start first-product --packet-id $packetId --json
$startReceipt | Write-Output
$workflowId = ($startReceipt | ConvertFrom-Json).workflow_run_id

Invoke-MoneyMachine worker drain --max-jobs 20 --json | Write-Output
$statusReceipt = Invoke-MoneyMachine workflow status $workflowId --json
$statusReceipt | Write-Output
$state = ($statusReceipt | ConvertFrom-Json).state
if ($state -ne "DRAFT_READY") {
    throw "Workflow ended in $state"
}

Invoke-MoneyMachine artifacts inspect $workflowId --json | Write-Output
