// 冒烟测试：验证 App 根组件可构建。
// 注意：AppStore.init 依赖 shared_preferences 插件，这里不触发它，
// 仅测试 IaquaApp 的 build。
import 'package:flutter_test/flutter_test.dart';

import 'package:iaquaria/main.dart';

void main() {
  testWidgets('IaquaApp 可构建', (tester) async {
    await tester.pumpWidget(const IaquaApp());
    expect(find.byType(IaquaApp), findsOneWidget);
  });
}
