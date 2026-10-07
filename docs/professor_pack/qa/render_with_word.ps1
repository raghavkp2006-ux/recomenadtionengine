$ErrorActionPreference = 'Stop'
$taskPackPath = Split-Path -Parent $PSScriptRoot
$taskInputPath = Join-Path $taskPackPath 'PolyTaste_Project_Explanation_and_Viva.docx'
$taskPdfPath = Join-Path $PSScriptRoot 'word_render.pdf'
$taskWordApp = $null
$taskWordDoc = $null
try {
    $taskWordApp = New-Object -ComObject Word.Application
    $taskWordApp.Visible = $false
    $taskWordApp.DisplayAlerts = 0
    $taskWordDoc = $taskWordApp.Documents.Open($taskInputPath, $false, $true, $false)
    $taskWordDoc.ExportAsFixedFormat($taskPdfPath, 17)
    Write-Output "Rendered document to $taskPdfPath"
} finally {
    if ($null -ne $taskWordDoc) { $taskWordDoc.Close(0); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskWordDoc) }
    if ($null -ne $taskWordApp) { $taskWordApp.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskWordApp) }
}
