/// 设备控制面板（概览页·历史趋势板下方）。
///
/// 与设备 Web 面板同源同约定：
/// - 每通道（CO2 电磁阀/水族灯/加热棒/补水泵）三段切换：自动 / 开 / 关
///   「开/关」= 手动接管（ctrl on），「自动」= 交还策略（ctrl mode:auto）
/// - 底部：投喂一次（feed 脉冲）
/// - 局域网断开时经云端 MQTT 下行通道（/cmd）下发应急控制命令（设备白名单
///   仅放行 ctrl/feed），执行结果通过 30s 周期遥测帧 act[] 回传，反馈有延迟
library;

import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../models/telemetry.dart';
import '../services/device_service.dart';

/// 展示名（跳过 feed 通道）
const _chNames = <String, String>{
  'co2': 'CO2 电磁阀',
  'light': '水族灯',
  'heater': '加热棒',
  'pump': '补水泵',
};

class DeviceControlPanel extends StatelessWidget {
  const DeviceControlPanel({super.key, required this.tel, required this.linkState});

  final Telemetry tel;
  final String linkState; // connected / cloud(-connecting/-error) / disconnected / manual …

  /// 云端链路（连接中/已连接/云失败重试/无数据提示）：控制命令改经云端 /cmd
  /// 主题下发（设备白名单 ctrl/feed），界面提示反馈延迟，但不再只读置灰
  bool get _cloudLink =>
      linkState == 'cloud' ||
      linkState == 'cloud-connecting' ||
      linkState.startsWith('cloud-error') ||
      linkState.startsWith('cloud-nodata');

  void _ctrl(String ch, {bool? on, bool auto = false}) {
    DeviceService.instance.ctrl(ch, on: on, auto: auto);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题行
          Row(
            children: [
              const Text('设备控制',
                  style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  _cloudLink
                      ? '（云端模式：命令经云端下发，状态约 30 秒内更新）'
                      : '（点「开/关」手动接管，点「自动」交还策略）',
                  style: const TextStyle(fontSize: 11, color: AppTheme.muted),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // 四个执行器通道行（跳过 feed）
          for (final ch in Telemetry.kChannels)
            if (ch != 'feed') _row(ch),
          const SizedBox(height: 6),
          // 底部操作：投喂
          Row(
            children: [
              FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.tealDark,
                  disabledBackgroundColor: const Color(0xFFcbd5e1),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                onPressed: () => DeviceService.instance.feed(),
                icon: const Icon(Icons.rice_bowl_outlined, size: 16),
                label: const Text('投喂一次', style: TextStyle(fontSize: 12.5)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// 单通道行：名称 + 状态文字 + 三段按钮（自动 | 开 | 关）
  Widget _row(String ch) {
    final idx = Telemetry.kChannels.indexOf(ch);
    final on = idx >= 0 && idx < tel.act.length ? tel.act[idx] : false;
    final manual = idx >= 0 && idx < tel.man.length ? tel.man[idx] : false;
    final stText = on ? (manual ? '手动·开' : '自动·开') : (manual ? '手动·关' : '自动·关');

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(_chNames[ch] ?? ch,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          ),
          Expanded(
            child: Text(stText,
                style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
          ),
          // 三段选择组（与 Web 面板一致：自动/开/关）
          ToggleButtons(
            isSelected: [!manual, manual && on, manual && !on],
            onPressed: (i) {
              if (i == 0) {
                _ctrl(ch, auto: true);
              } else {
                _ctrl(ch, on: i == 1);
              }
            },
            borderRadius: BorderRadius.circular(8),
            selectedColor: Colors.white,
            fillColor: AppTheme.tealDark,
            color: AppTheme.tealDark,
            borderColor: AppTheme.tealDark,
            selectedBorderColor: AppTheme.tealDark,
            disabledColor: AppTheme.muted,
            constraints: const BoxConstraints(minHeight: 30, minWidth: 50),
            textStyle: const TextStyle(fontSize: 12),
            children: const [Text('自动'), Text('开'), Text('关')],
          ),
        ],
      ),
    );
  }
}
