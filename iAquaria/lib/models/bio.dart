/// 生物监测数据与 AI 分析记录模型。
///
/// 生物条目带二级分类（预定类群：鱼/水草/珊瑚/软体/甲壳），由 AI 识别回写
/// 或手动录入；鱼只计数只统计「鱼」类群。AI 可能误判，用户可在概览页
/// 生物面板中修正分类、名称与数量。分析记录按缸保存，供按日期时间回看。
library;

/// 预定类群（二级分类）
const kBioGroups = <String>['鱼', '水草', '珊瑚', '软体', '甲壳'];

/// 一个生物条目（二级分类 + 种名 + 数量）
class BioSpecies {
  BioSpecies({required this.name, this.count = 0, this.group = '鱼'});

  /// 二级分类（限 kBioGroups 内；旧数据缺省按「鱼」）
  String group;

  String name;
  int count;

  Map<String, dynamic> toJson() =>
      {'group': group, 'name': name, 'count': count};

  factory BioSpecies.fromJson(Map<String, dynamic> j) => BioSpecies(
        group: '${j['group'] ?? '鱼'}',
        name: '${j['name'] ?? ''}',
        count: (j['count'] as num?)?.toInt() ?? 0,
      );

  static List<BioSpecies> listFromJson(List<dynamic> arr) => arr
      .map((e) => BioSpecies.fromJson(Map<String, dynamic>.from(e as Map)))
      .toList();

  static List<Map<String, dynamic>> listToJson(List<BioSpecies> list) =>
      list.map((e) => e.toJson()).toList();

  /// 归一化：不在预定类群内的归「鱼」
  void normalizeGroup() {
    if (!kBioGroups.contains(group)) group = '鱼';
  }
}

/// 一条 AI 分析记录（含请求摘要与回复全文）
class AnalysisRecord {
  AnalysisRecord({
    required this.ts,
    required this.req,
    required this.reply,
    this.hasImage = false,
  });

  final int ts; // 毫秒时间戳
  final String req; // 用户请求（摘要）
  final String reply; // AI 回复全文
  final bool hasImage; // 是否附带抓拍图

  Map<String, dynamic> toJson() =>
      {'ts': ts, 'req': req, 'reply': reply, 'img': hasImage};

  factory AnalysisRecord.fromJson(Map<String, dynamic> j) => AnalysisRecord(
        ts: (j['ts'] as num?)?.toInt() ?? 0,
        req: '${j['req'] ?? ''}',
        reply: '${j['reply'] ?? ''}',
        hasImage: j['img'] == true,
      );
}

/// 从 AI 回复文本中解析生物清单。
///
/// 新格式（二级分类|种名|计数）：`生物清单：鱼|斑马鱼|5, 水草|莫斯|3`
/// 兼容：
/// - 标记后跨行列条目（AI 常把「生物清单：」独占一行，下面逐条列出）；
/// - 标记别名（生物列表/识别清单/清单汇总/生物汇总）与 Markdown 加粗、表格；
/// - 旧格式（种名×计数，缺分类按「鱼」，可手动改）。
/// 找不到标记时在全文兜底匹配三段式（竖线三段式在普通文本中极少误判）。
/// 返回解析出的条目（失败返回空表，不抛异常）。
List<BioSpecies> parseBioList(String reply) {
  if (reply.trim().isEmpty) return const [];

  // 1) 定位清单标记，取标记之后的全部文本（允许跨行）
  var body = reply;
  final mark = RegExp(r'(?:生物清单|生物列表|识别清单|清单汇总|生物汇总)'
          r'\s*[：:＊*]*')
      .firstMatch(reply);
  if (mark != null) body = reply.substring(mark.end);

  // 2) 清理 Markdown 噪音：加粗/反引号/标题符、行首项目符号与编号
  final cleaned = body
      .replaceAll(RegExp(r'[*`#>]+'), '')
      .replaceAll(RegExp(r'^\s*[-•·]+\s*', multiLine: true), '')
      .replaceAll(RegExp(r'^\s*\d+[.、)]\s*', multiLine: true), '');

  final out = <BioSpecies>[];

  // 3) 新格式：类群 | 种名 | 数量（跨行逐条；兼容全角竖线与表格首尾竖线）
  final tri = RegExp(r'([一-龥A-Za-z]{1,6})\s*[|｜]\s*'
      r'([一-龥A-Za-z0-9·（）()\-]+?)\s*[|｜]\s*(\d+)');
  for (final match in tri.allMatches(cleaned)) {
    final group = match.group(1)!.trim();
    final name = match.group(2)!.trim();
    final count = int.tryParse(match.group(3)!) ?? 0;
    if (name.isNotEmpty && count > 0) {
      final item = BioSpecies(name: name, count: count, group: group);
      item.normalizeGroup(); // 非预定类群（AI 幻觉）归「鱼」
      if (!out.any((e) => e.group == item.group && e.name == item.name)) {
        out.add(item); // AI 可能在正文与清单行重复
      }
    }
  }
  if (out.isNotEmpty) return out;

  // 4) 旧格式兼容：种名 × 数量
  for (final match
      in RegExp(r'([一-龥A-Za-z0-9·]+)\s*[×xX*]\s*(\d+)').allMatches(cleaned)) {
    final name = match.group(1)!.trim();
    final count = int.tryParse(match.group(2)!) ?? 0;
    if (name.isNotEmpty && count > 0 && !out.any((e) => e.name == name)) {
      out.add(BioSpecies(name: name, count: count));
    }
  }
  return out;
}

/// 把 AI 识别清单合并进现有生物数据：
/// 同名（同组优先，其次任意组名互相包含视为同种）更新数量，新条目追加；
/// 已有但 AI 未提及的条目保留（可能只是没拍到），由用户手动删除。
List<BioSpecies> mergeBio(List<BioSpecies> current, List<BioSpecies> found) {
  final list = List<BioSpecies>.from(current);
  for (final f in found) {
    var idx = list.indexWhere((e) => e.group == f.group && e.name == f.name);
    if (idx < 0) {
      // 同组未找到 → 名称匹配任意组（互相包含视为同种）
      idx = list.indexWhere((e) =>
          e.name == f.name ||
          e.name.contains(f.name) ||
          f.name.contains(e.name));
    }
    if (idx >= 0) {
      list[idx].count = f.count; // 组分类保留用户手改结果
    } else {
      list.add(BioSpecies(name: f.name, count: f.count, group: f.group));
    }
  }
  return list;
}
