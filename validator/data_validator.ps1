# Filename: ValidateStudentData.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

function Update-ProgressBar {
    param ($percent)
    Write-Progress -Activity "Validating File" -PercentComplete $percent
}

function Validate-CSV {
    param ($data)
    $rows = Import-Csv -Path $data
    Validate-Data $rows
}

function Validate-XLSX {
    param ($data)
    if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
        Write-Host "ImportExcel module not found. Installing..."
        Install-Module -Name ImportExcel -Scope CurrentUser -Force
    }
    Import-Module ImportExcel
    $rows = Import-Excel -Path $data
    Validate-Data $rows
}

function Validate-JSON {
    param ($data)
    $jsonContent = Get-Content -Path $data -Raw | ConvertFrom-Json
    $rows = $jsonContent | ForEach-Object { [PSCustomObject]$_ }
    Validate-Data $rows
}

function Validate-Data {
    param ($rows)
    $errors = @()
    $rowNumber = 1

    # Validate headers (trim spaces and make comparison case-insensitive)
    $headers = $rows[0].PSObject.Properties.Name | ForEach-Object { $_.Trim().ToLower() }
    $expectedHeaders = @("student-id", "dosage", "pre-test", "post-test")

    # Sort and compare headers by joining them into strings
    $headersString = ($headers | Sort-Object) -join ','
    $expectedHeadersString = ($expectedHeaders | Sort-Object) -join ','

    if ($headersString -ne $expectedHeadersString) {
        Write-Host "Invalid Headers. Expected headers: $($expectedHeaders -join ', ')"
        Write-Host "Found headers: $($headers -join ', ')"
        return
    }

    # Validate rows
    foreach ($row in $rows) {
        $rowNumber++

        $studentId = $row."student-id"
        $dosage = $row."dosage"
        $preTest = $row."pre-test"
        $postTest = $row."post-test"

        # Validate Student ID
        if (-not $studentId -match "^\d{6}$") {
            $errors += "Row $($rowNumber): Invalid Student ID '$studentId'"
        }

        # Validate Dosage (convert to float)
        try {
            $dosageFloat = [float]$dosage
            if ($dosageFloat -lt 0 -or $dosageFloat -gt 1) {
                $errors += "Row $($rowNumber): Invalid Dosage % '$dosage'"
            }
        } catch {
            $errors += "Row $($rowNumber): Invalid Dosage % '$dosage'"
        }

        # Validate Pre-Test Score (convert to integer)
        try {
            $preTestInt = [int]$preTest
            if ($preTestInt -lt 0 -or $preTestInt -gt 100) {
                $errors += "Row $($rowNumber): Invalid Pre-Test Score '$preTest'"
            }
        } catch {
            $errors += "Row $($rowNumber): Invalid Pre-Test Score '$preTest'"
        }

        # Validate Post-Test Score (convert to integer)
        try {
            $postTestInt = [int]$postTest
            if ($postTestInt -lt 0 -or $postTestInt -gt 100) {
                $errors += "Row $($rowNumber): Invalid Post-Test Score '$postTest'"
            }
        } catch {
            $errors += "Row $($rowNumber): Invalid Post-Test Score '$postTest'"
        }
    }

    if ($errors.Count -gt 0) {
        Write-Host "Errors Found:"
        $errors | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "Congratulations! Your data are valid."
    }
}

# Main script
if (-not (Test-Path $FilePath)) {
    Write-Host "File does not exist: $FilePath"
    exit 1
}

$fileType = [System.IO.Path]::GetExtension($FilePath).ToLower()

Update-ProgressBar -percent 10

switch ($fileType) {
    ".csv" { Validate-CSV -data $FilePath }
    ".xlsx" { Validate-XLSX -data $FilePath }
    ".json" { Validate-JSON -data $FilePath }
    default { Write-Host "Unsupported file type: $fileType" }
}

Update-ProgressBar -percent 100