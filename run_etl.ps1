# Execução do pipeline macroeconômico (Windows / Agendador de Tarefas).
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Ative o virtualenv se existir
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . ".venv\Scripts\Activate.ps1"
}

python src\orquestrador.py
