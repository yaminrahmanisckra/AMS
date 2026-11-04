import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'models.dart';

class ApiException implements Exception {
  ApiException(this.code, this.message, {this.status = 0});

  final String code;
  final String message;
  final int status;

  @override
  String toString() => message;
}

class SignedInUser {
  const SignedInUser({
    required this.token,
    required this.username,
    required this.name,
    required this.role,
  });

  final String token;
  final String username;
  final String name;
  final String role;
}

class RoutineApi {
  RoutineApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<SignedInUser> login({
    required String serverUrl,
    required String username,
    required String password,
  }) async {
    final body = await _send(
      serverUrl: serverUrl,
      path: '/api/mobile/v1/login',
      method: 'POST',
      jsonBody: {'username': username, 'password': password},
    );
    final user = body['user'];
    final token = body['token'];
    if (token is! String || token.isEmpty || user is! Map<String, dynamic>) {
      throw ApiException('bad_response', 'সার্ভারের উত্তর পড়া যায়নি।');
    }
    return SignedInUser(
      token: token,
      username: _text(user['username']),
      name: _text(user['name']),
      role: _text(user['role']),
    );
  }

  Future<RoutineFeed> routine({
    required String serverUrl,
    required String token,
  }) async {
    final body = await _send(
      serverUrl: serverUrl,
      path: '/api/mobile/v1/routine',
      method: 'GET',
      token: token,
    );
    return RoutineFeed.fromJson(body);
  }

  Future<Map<String, dynamic>> _send({
    required String serverUrl,
    required String path,
    required String method,
    String? token,
    Map<String, dynamic>? jsonBody,
  }) async {
    final root = normalizeServerUrl(serverUrl);
    final uri = Uri.parse('$root$path');
    try {
      final response = await _client
          .send(_request(uri, method: method, token: token, jsonBody: jsonBody))
          .timeout(const Duration(seconds: 20));
      final raw = await response.stream.bytesToString();
      Map<String, dynamic> body = const {};
      if (raw.isNotEmpty) {
        final decoded = jsonDecode(raw);
        if (decoded is Map<String, dynamic>) {
          body = decoded;
        }
      }
      if (response.statusCode >= 200 && response.statusCode < 300 && body['ok'] == true) {
        return body;
      }
      final code = _text(body['error']);
      final fallback = _text(body['message']);
      throw ApiException(
        code.isEmpty ? 'request_failed' : code,
        messageForErrorCode(code, fallback),
        status: response.statusCode,
      );
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw ApiException('timeout', 'সার্ভার সাড়া দিচ্ছে না।');
    } on SocketException {
      throw ApiException('offline', 'ইন্টারনেট বা সার্ভার ঠিকানা যাচাই করুন।');
    } on FormatException {
      throw ApiException('bad_response', 'সার্ভারের উত্তর পড়া যায়নি।');
    } on http.ClientException {
      throw ApiException('offline', 'ইন্টারনেট বা সার্ভার ঠিকানা যাচাই করুন।');
    }
  }

  http.Request _request(
    Uri uri, {
    required String method,
    String? token,
    Map<String, dynamic>? jsonBody,
  }) {
    final request = http.Request(method, uri);
    request.headers['Accept'] = 'application/json';
    if (token != null && token.isNotEmpty) {
      request.headers['Authorization'] = 'Bearer $token';
    }
    if (jsonBody != null) {
      request.headers['Content-Type'] = 'application/json; charset=utf-8';
      request.body = jsonEncode(jsonBody);
    }
    return request;
  }
}

String _text(Object? value) {
  if (value == null) return '';
  return value.toString();
}
