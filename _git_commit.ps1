Set-Location C:\work\xml-feedy\procentov
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Write-Host "=== git status ===" 
git status

Write-Host "`n=== git add ===" 
git add -A

Write-Host "`n=== git status after add ==="
git status --short

Write-Host "`n=== git commit ==="
$msg = @"
M1.1: parser_atos + 12 testu PASS, 2 master + 482 variant Milo

- polotovar/parser_atos.py: parse() dataclass API (ParsedProduct, ParsedOffer)
- polotovar/tests/: 12 testu vc. strukturalnich (test_milo_has_exactly_two_masters)
- polotovar/tests/fixtures/atos_milo_sample.xml: 4 MB Milo vyrez
- config/atos.yaml: variant/parameter whitelist, EAN regex
- M1.1b: item_group_key opraven na cat_path[1] (material je variantni osa)
- DISCOVERY B.3.3: aktualizovan algoritmus slouceni variant
- requirements.txt: lxml, pyyaml, pytest
- .gitignore: throwaway patterns
"@
git commit -m $msg

Write-Host "`n=== git log -1 ==="
git log -1 --oneline

Write-Host "`n=== exit code ==="
Write-Host $LASTEXITCODE
