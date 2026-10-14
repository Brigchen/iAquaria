// parseBioList 单元测试：覆盖 AI 实际可能输出的各种格式
import 'package:flutter_test/flutter_test.dart';

import 'package:iaquaria/models/bio.dart';

void main() {
  test('标准单行新格式', () {
    const r = '这是一些识别说明。\n生物清单：鱼|斑马鱼|5, 水草|莫斯|3';
    final out = parseBioList(r);
    expect(out.length, 2);
    expect(out[0].group, '鱼');
    expect(out[0].name, '斑马鱼');
    expect(out[0].count, 5);
    expect(out[1].group, '水草');
    expect(out[1].count, 3);
  });

  test('标记独占一行、条目跨行列（核心 bug 场景）', () {
    const r = '识别结果如下：\n生物清单：\n鱼|孔雀鱼|8\n甲壳|黑壳虾|20';
    final out = parseBioList(r);
    expect(out.length, 2);
    expect(out[0].name, '孔雀鱼');
    expect(out[0].count, 8);
    expect(out[1].group, '甲壳');
    expect(out[1].count, 20);
  });

  test('Markdown 加粗与表格形式', () {
    const r = '**生物清单：**\n'
        '| 类群 | 种名 | 数量 |\n'
        '| --- | --- | --- |\n'
        '| 鱼 | 红绿灯 | 12 |\n'
        '| 软体 | 斑马螺 | 3 |';
    final out = parseBioList(r);
    expect(out.length, 2);
    expect(out[0].name, '红绿灯');
    expect(out[0].count, 12);
    expect(out[1].group, '软体');
    expect(out[1].name, '斑马螺');
  });

  test('全角竖线与数量带量词', () {
    const r = '生物清单：鱼｜金鱼｜2只，水草｜水榕｜1棵';
    final out = parseBioList(r);
    expect(out.length, 2);
    expect(out[0].count, 2);
    expect(out[1].count, 1);
  });

  test('标记别名', () {
    const r = '生物汇总：甲壳|大和藻虾|6';
    expect(parseBioList(r).single.name, '大和藻虾');
    const r2 = '识别清单：鱼|斗鱼|1';
    expect(parseBioList(r2).single.count, 1);
  });

  test('无标记时全文兜底匹配三段式', () {
    const r = '照片里能看到 鱼|宝莲灯|10 在游动，另外有 水草|莫斯|2。';
    final out = parseBioList(r);
    expect(out.length, 2);
  });

  test('旧格式 ×n 兼容（缺类群按鱼）', () {
    const r = '生物清单：斑马鱼×5，黑壳虾×20';
    final out = parseBioList(r);
    expect(out.length, 2);
    expect(out[0].group, '鱼');
    expect(out[0].count, 5);
  });

  test('非预定类群归一化为鱼', () {
    const r = '生物清单：两栖|六角恐龙|1';
    final out = parseBioList(r);
    expect(out.single.group, '鱼');
  });

  test('无任何清单内容返回空表', () {
    expect(parseBioList('这缸水看着不错，继续保持。'), isEmpty);
    expect(parseBioList(''), isEmpty);
  });

  test('mergeBio：同名更新数量、未提及保留、新种追加', () {
    final current = [
      BioSpecies(name: '斑马鱼', count: 5, group: '鱼'),
      BioSpecies(name: '莫斯', count: 3, group: '水草'),
    ];
    final found = [
      BioSpecies(name: '斑马鱼', count: 6, group: '鱼'),
      BioSpecies(name: '黑壳虾', count: 10, group: '甲壳'),
    ];
    final merged = mergeBio(current, found);
    expect(merged.length, 3);
    expect(merged.firstWhere((e) => e.name == '斑马鱼').count, 6);
    expect(merged.firstWhere((e) => e.name == '莫斯').count, 3);
    expect(merged.firstWhere((e) => e.name == '黑壳虾').count, 10);
  });
}
