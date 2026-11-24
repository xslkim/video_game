# 长安灯妖录 · Windows 三节点试玩

解压整个 Windows x64 试玩包，双击 `Changan.exe`。标题画面点「开始巡街」或按 Enter。请把同目录的 DLL、`assets`、`worlds` 保留在一起。试玩包可离线启动。

当前试玩包是 `Changan-Market-Windows-x64.zip`。开场可以立即施符，也可以先看左摊两名行人走近摊位。整条街的动作约 7.3 秒，随后停在末帧。期间怪物再次攻击、青火被拦截和狐妖连续受击都不会重播行人的动作。按 Esc 可以同时暂停街景与战斗。

| 操作 | 按键 |
|---|---|
| 施符 | 鼠标左键 |
| 换匣 | 鼠标右键或 R |
| 雷符 | 鼠标中键或空格，满槽时可施放 |
| 暂停 / 继续 | Esc |
| 开始、重玩 | Enter |
| 全屏 | F11 |
| 查看判定区、片名和帧号 | F3 |

**试玩路线。** 先看左边摊位的横移灯笼妖，试着等它动起来再打。右侧青火出现后先等它发射，用左键打掉飞出的球，再净化回到原位的青火。巷心狐火妖需要三次命中，等每次短暂受击结束后再打。通关后按 Enter 可以重试另一种时机。

普通难度从三条生命、八支符箭和零雷符能量开始。纯转场可以换匣，射击会等待下一个目标开放。雷符满槽需 20 次有效命中，这个短遭遇可在下列回放里验证雷符。

**开发与回放。** 开发环境从仓库根目录执行 `.\tools\player\build_changan.ps1 -VcpkgRoot C:/vcpkg`，需要 Visual Studio 2022、vcpkg、CMake、Python、FFprobe。启动、解码、分支和绘制用同一套代码运行自动回放。用下列 PowerShell 命令运行一个回放并输出报告。

```powershell
$output = Join-Path (Get-Location).Path 'build/qa/changan-replay'
$p = Start-Process -FilePath .\dist\Changan-Market\Changan.exe -ArgumentList '--smoke', ('"' + $output + '"'), '--scenario', 'intercept-last' -WindowStyle Hidden -Wait -PassThru
if ($p.ExitCode) { throw "Replay failed ($($p.ExitCode))" }
Get-Content -Encoding UTF8 (Join-Path $output 'playthrough.json')
```

用 `street-hold` 可复现故意承受两次攻击后再通关的路线，`fx-reload` 在首次命中后立即换匣，`intercept-last` 展示青火贴近地面时被拦下的效果。其他路线有 `normal`、`early`、`late`、`intercept-first`、`intercept-middle`、`impact`、`thunder`、`thunder-finish`、`recovery`。传入 `--capture` 可以把运行中的画面保存为 BMP 序列。程序从自身所在目录读取资源，开发时可用 `--root <目录>` 指定素材根目录。
