/// 摄像头服务：ESP32-CAM 抓拍（HTTP /capture 单帧 JPEG）+ 手机系统相机拍照。
///
/// 说明：
/// - 在线摄像头：纯 Dart HTTP 拉取 ESP32-CAM 的 /capture 帧，地址存缸档案 camUrl；
/// - 手机相机：image_picker 经系统相机 Intent 拍照（人工缸/无监控时识图识别用），
///   鸿蒙无平台实现，抛 UnsupportedError 由调用方提示；
/// - ESP32-CAM 服务：/ 状态、/capture 单帧 JPEG、:81/stream MJPEG；
/// - 摄像头地址保存在缸档案 camUrl，如 http://192.168.3.191。
library;

import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

class CameraService {
  CameraService._();
  static final CameraService instance = CameraService._();

  final Dio _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 8),
    responseType: ResponseType.bytes,
  ));

  /// 抓拍一帧 JPEG；失败抛异常（调用方提示）
  Future<Uint8List> capture(String camBase) async {
    // 规范化地址：允许用户只填 IP（如 192.168.3.191），自动补 http://
    var base = camBase.trim();
    if (!base.startsWith('http://') && !base.startsWith('https://')) {
      base = 'http://$base';
    }
    final url = base.endsWith('/') ? '${base}capture' : '$base/capture';
    final res = await _dio.get<List<int>>(url);
    final data = res.data;
    if (data == null || data.isEmpty) {
      throw StateError('抓拍失败：空响应');
    }
    return Uint8List.fromList(data);
  }

  /// 调起手机系统相机拍照，返回 JPEG 字节。
  /// 用户取消返回 null；平台不支持（鸿蒙）抛 UnsupportedError。
  Future<Uint8List?> pickFromPhoneCamera() async {
    try {
      final XFile? f = await ImagePicker().pickImage(
        source: ImageSource.camera,
        imageQuality: 80, // 压缩：控制多模态请求体积
        maxWidth: 1920,
      );
      if (f == null) return null;
      return await f.readAsBytes();
    } on UnsupportedError {
      rethrow;
    } catch (e) {
      // MissingPluginException（鸿蒙）等 → 统一转不支持异常，调用方友好提示
      throw UnsupportedError('当前平台不支持手机相机：$e');
    }
  }
}
