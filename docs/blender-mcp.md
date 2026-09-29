# 使用 Blender MCP 建模

本仓库的 Blender 模型由 `docs/<模型目录>/build_*.py` 参数化脚本构建。Codex 通过 MCP 连接正在运行的 Blender 后，可以检查当前场景、执行这些脚本并继续调整。MCP 服务端通过 `uvx mcp-for-blender` 启动，Blender 插件负责将命令转发给 Blender。

> 本配置适用于本地 Codex 桌面端/CLI 和本地 Blender。MCP 插件可在 Blender 中执行 Python；只对可信的模型脚本和指令操作，建模前保存当前 `.blend` 文件。

## 一次性安装

1. 安装 Blender 5.1 或更新版本，并安装 Astral `uv`（提供 `uvx` 命令）。确保 `uvx` 在 Codex 启动环境的 `PATH` 中。
2. 在 PowerShell 运行以下命令，将 MCP 插件安装到本机 Blender 插件目录：

   ```powershell
   uvx mcp-for-blender install-addon
   ```

3. 打开 Blender，在 **Edit → Preferences → Add-ons** 中启用 **Interface: Blender MCP**。
4. 在 3D Viewport 中按 `N` 打开侧栏，切换到 **Blender MCP** 面板，然后点击 **Start MCP Server**。
5. 在 Codex 中信任并重新打开本仓库。仓库的 `.codex/config.toml` 会注册名为 `blender` 的项目级 MCP 服务。若当前会话未加载新配置，重启 Codex 本地任务后检查 Blender 工具是否可用。

项目级 MCP 配置内容：

```toml
[mcp_servers.blender]
command = "uvx"
args = ["mcp-for-blender"]
env = { DISABLE_TELEMETRY = "true" }
```

若 Codex 找不到 `uvx`，将 `command` 改成 `uvx.exe` 的绝对路径。可以在 PowerShell 中运行 `Get-Command uvx` 查看路径。MCP 插件可执行 Blender Python；它不应连接到不可信的 MCP 客户端，运行前保存当前模型。

## 用 MCP 重建仓库模型

每次建模前按以下顺序操作：

1. 阅读该模型目录的 `README.md`、`dimensions.md` 和 `build_*.py`，确认尺寸约束、输出文件及脚本对当前 Blender 版本的要求。
2. 确认 Blender 插件已启动，并在 Codex 中检查 `blender` MCP 工具可用。
3. 要求 Codex 读取所选 `build_*.py` 的完整内容，并通过 Blender MCP 的 `execute_blender_code` 工具将脚本内容提交给 Blender 执行。先用 Codex 读取本地文件，再把 Python 源码传给 MCP；不要让 Blender 中的 Python 通过 `open()` 从磁盘读取脚本。

   也可让 Codex 先从 MCP 查询场景，再执行脚本并报告异常和输出文件。不要把终端中的 `blender --python` 命令当作 Blender MCP 工具调用。
4. 脚本运行后，让 Codex 使用 MCP 检查对象和尺寸，并确认脚本声明的 `.blend` / STL 文件输出存在；检查完再继续修改模型。

`execute_blender_code` 是执行任意 Python 的能力。仓库脚本会按各自逻辑写出 Blender 文件或 STL；运行前确认目标是仓库中对应的模型目录，避免覆盖其他场景或文件。

## 直接向 Blender 提出建模要求

描述模型目录、要修改的部件、毫米尺寸、装配关系、输出格式和是否需要保留原场景。例如：

> 使用 Blender MCP 检查 `docs/sr04_bracket` 的 README、dimensions 和构建脚本。保持现有孔位及 1 mm 单位约定，将横板宽度改为 36 mm；先说明参数改动，再运行构建脚本。最后检查 STL 与 blend 输出。

## 排查连接问题

- Codex 中看不到 Blender 工具：检查仓库是否在 Codex 中标记为可信，确认 `.codex/config.toml` 已加载，重启本地 Codex 任务，并检查 `uvx` 是否能从 Codex 进程的 `PATH` 找到。
- 服务无法连接：确认 Blender 插件已启用且 **Start MCP Server** 状态正常；仅运行一个连接该 Blender 插件的 MCP 客户端。
- 脚本执行失败：先让 MCP 查询 Blender 版本、场景和错误信息，再对照模型 README 与尺寸文件处理；不要仅凭错误猜测并覆盖成品文件。
- Blender 版本或插件升级后异常：更新 MCP 插件并重启 Blender，然后重新建立 Codex 会话。

## 参考

- [Codex 配置基础（项目级 `.codex/config.toml`）](https://learn.chatgpt.com/docs/config-file/config-basic)
- [Codex MCP 配置说明](https://learn.chatgpt.com/docs/extend/mcp)
- [`mcp-for-blender` 安装、Codex 配置和工具说明](https://github.com/ahujasid/mcp-for-blender)
- [Blender Lab MCP Server 安全说明](https://www.blender.org/lab/mcp-server/)
