# iAquaria App 功能模块自动截图（鸿蒙无线调试）
# 用法: .\capture_screens.ps1 [-Target 192.168.3.170:34319] [-Out ..\screens]
# 前提: 手机与电脑同局域网；开发者选项→无线调试已开（端口变化时改 -Target）
# 流程: 连接→唤醒→拉起 App→按底部 Tab 逐页截屏→二级页(AI/设置/生物清单)截屏
param(
  [string]$Target = "192.168.3.170:34319",
  [string]$Out = "$PSScriptRoot"
)
$ErrorActionPreference = "Continue"
$hdc = "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"
if (-not (Test-Path $hdc)) { $hdc = "$env:ProgramFiles\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe" }

function Shot([string]$name) {
  Start-Sleep 2
  & $hdc -t $Target shell snapshot_display -f /data/local/tmp/s.jpeg | Out-Null
  & $hdc -t $Target file recv /data/local/tmp/s.jpeg "$Out\$name.jpeg" | Out-Null
  Write-Host "  [ok] $name.jpeg"
}
function Tap([int]$x, [int]$y) { & $hdc -t $Target shell uitest uiInput click $x $y }
function Back() { & $hdc -t $Target shell uitest uiInput keyEvent Back }

& $hdc tconn $Target
& $hdc -t $Target shell "power-shell wakeup; power-shell setmode 602" | Out-Null
& $hdc -t $Target shell uitest uiInput swipe 540 2200 540 900 400   # 上滑解锁（无密码时）
& $hdc -t $Target shell aa start -a EntryAbility -b com.iaquaria.smartaquarium
Start-Sleep 6

# 分辨率 1080x2440；底部 Tab y=2180，x: 概览135/日志407/计划665/鱼缸940
$tabs = @{ "01_概览" = 135; "02_日志" = 407; "03_计划" = 665; "04_鱼缸" = 940 }
foreach ($k in $tabs.Keys) { Tap $tabs[$k] 2180; Shot $k }

# 二级页（概览页右上角 ✨=AI(834,208)、⚙=设置(997,208)；生物概览卡片(324,1537)）
Tap 135 2180            # 回概览
Tap 834 208; Shot "05_AI智能分析"; Back
Tap 997 208; Shot "06_设置"; Back
Tap 324 1537; Shot "07_生物概览"; Back

Write-Host "完成：$Out"
