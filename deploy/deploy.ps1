param(
    [string]$Server = "root@45.79.124.28",
    [string]$RemoteDir = "/opt/jazversememory"
)

$ErrorActionPreference = "Stop"

ssh $Server "mkdir -p $RemoteDir"
scp -r pyproject.toml README.md .env.example src tests deploy "${Server}:${RemoteDir}/"
ssh $Server "cd $RemoteDir && bash deploy/install_on_server.sh"
