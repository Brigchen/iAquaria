# iAqua 传感器支架（可制造版）

**严格尺寸与孔位见 [dimensions.md](dimensions.md)**。参数在 `build_sensor_mounts.py` 顶部常量，与 dimensions 同步。

## STL 清单（10 件）

| 文件 | 功能 |
|------|------|
| `Bulkhead_Outer.stl` | 120×100×8；M4 通孔 + 沉头；密封槽；4 传感器孔 |
| `Bulkhead_Inner.stl` | 120×100×6；M4 通孔 + 六角螺母腔；密封槽 |
| `DrillGuide.stl` | 3 mm 钻孔模板（玻璃 **Ø4.2 / 6 / 12 / 12.5**） |
| `Gland_Body_6mm.stl` / `Gland_Ring_6mm.stl` | DS18 Ø6 探头压缩法兰 |
| `RimClip_Base.stl` / `RimClip_Jaw.stl` | 缸沿夹 M5×50 + 20×6 轨槽 |
| `VerticalRail.stl` | 20×128×6；6×M3 沉孔；M4 锁轨螺纹孔 |
| `Mount_SR04.stl` | HC-SR04 45×20 包容 + 2×M3 耳片 |
| `Mount_BH1750.stl` | GY-30 16.5 方腔 + 2×M3 |

## 传感器对应

| 传感器 | 支架 |
|--------|------|
| DS18B20 | Bulkhead TEMP 孔 + Gland |
| pH / TDS | Bulkhead Ø12.5 + 电极锁母 |
| 485 线 | Bulkhead PG7 孔 + **采购 PG7** |
| HC-SR04 | RimClip + Rail + Mount_SR04 |
| GY-30 | RimClip + Rail + Mount_BH1750 |

## 重建模型

Blender MCP 或：

```text
exec(open(r"...\docs\sensor_mounts\build_sensor_mounts.py", encoding="utf-8").read())
```

输出：`stl/`、`iAqua_SensorMounts.blend`。

## 紧固件（每套）

- M4×45 ×4、M4 垫圈 ×4、M4 螺母 ×4（或内板 nut trap）
- M5×50 ×1（缸沿夹）
- M3×8 / M3×10 若干（轨上模块）
- M4 热熔螺母 ×1（轨锁紧，可选）
- 采购 PG7、M10 锁母（DS18 法兰）、O 圈 Ø12

打印：**PETG**，压板 100% 填充，0.2 mm 层高。
