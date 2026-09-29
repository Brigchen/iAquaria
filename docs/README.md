# iAqua 文档与 3D 模型

## 通过 MCP 使用 Blender

Codex 项目级 Blender MCP 配置位于仓库根目录 `.codex/config.toml`。首次使用前，按[Blender MCP 建模指南](blender-mcp.md)安装 `uvx`、Blender 插件并启动 Blender 内的 MCP 服务。配置加载后，Codex 可通过 MCP 检查场景、执行现有建模脚本并在 Blender 中迭代模型。

## 模型目录

各目录包含参数化 Blender Python 构建脚本、尺寸说明，以及可用时的 `.blend`、GLB 或 STL 成品。建模前应先阅读对应目录的 `README.md` 和 `dimensions.md`。

| 模型 | 目录 | 构建脚本 |
|---|---|---|
| USB 摄像头外壳 | [usb_cam_case](usb_cam_case/) | `build_usb_cam_case.py` |
| TDS 缸沿支架 | [tds_h_bracket](tds_h_bracket/) | `build_tds_h_bracket.py` |
| HC-SR04 缸沿支架 | [sr04_bracket](sr04_bracket/) | `build_sr04_bracket.py` |
| 探头缸沿支架 | [probe_h_bracket](probe_h_bracket/) | `build_probe_h_bracket.py` |
| 密封圈与密封帽 | [seal_ring](seal_ring/) | `build_seal_ring.py` |
| 自动喂食器 | [feeder](feeder/) | `build_feeder.py` |
| 摄像头挂架 | [cam_hanger](cam_hanger/) | `build_cam_hanger.py` |
| 传感器安装件 | [sensor_mounts](sensor_mounts/) | `build_sensor_mounts.py` |
| GY-30 光照传感器外壳 | [gy30_case](gy30_case/) | `build_gy30_case.py` |

每个模型的 STL 输出位于对应目录的 `stl/` 子目录。执行脚本会在相应模型目录更新构建产物；尺寸变更以该目录的尺寸说明和脚本参数为准。
