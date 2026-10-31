# gen_keyfile.ps1 —— 生成 MongoDB 副本集/分片集群内部认证用的 keyFile（756 字节 base64）
# 用法（PowerShell）：.\gen_keyfile.ps1                    默认写到本目录 keyfile.txt
#                     .\gen_keyfile.ps1 -Out D:\x\kf.txt   写到指定路径
param([string]$Out = (Join-Path $PSScriptRoot "keyfile.txt"))
$bytes = New-Object 'System.Byte[]' 756
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[Convert]::ToBase64String($bytes) | Set-Content -Path $Out -NoNewline -Encoding ascii
Write-Host "已生成 keyFile：$Out（756 字节 base64，集群内所有 mongod / mongos 必须用同一个文件）"
