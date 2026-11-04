import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class Session {
  const Session({
    required this.token,
    required this.serverUrl,
    required this.username,
    required this.name,
    required this.role,
  });

  final String token;
  final String serverUrl;
  final String username;
  final String name;
  final String role;
}

class SessionStore {
  SessionStore({FlutterSecureStorage? secure}) : _secure = secure ?? const FlutterSecureStorage();

  static const _tokenKey = 'mobile_token';
  static const _serverKey = 'server_url';
  static const _usernameKey = 'username';
  static const _nameKey = 'display_name';
  static const _roleKey = 'role';
  static const _routineKey = 'routine_cache';

  final FlutterSecureStorage _secure;

  Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

  Future<String> readServerUrl() async {
    final prefs = await _prefs();
    final stored = prefs.getString(_serverKey);
    if (stored == null || stored.trim().isEmpty) return defaultServerUrl;
    return stored;
  }

  Future<Session?> read() async {
    final token = await _secure.read(key: _tokenKey);
    if (token == null || token.isEmpty) return null;
    final prefs = await _prefs();
    return Session(
      token: token,
      serverUrl: prefs.getString(_serverKey) ?? defaultServerUrl,
      username: prefs.getString(_usernameKey) ?? '',
      name: prefs.getString(_nameKey) ?? '',
      role: prefs.getString(_roleKey) ?? '',
    );
  }

  Future<void> save({
    required String token,
    required String serverUrl,
    required String username,
    required String name,
    required String role,
  }) async {
    final prefs = await _prefs();
    await prefs.setString(_serverKey, serverUrl);
    await prefs.setString(_usernameKey, username);
    await prefs.setString(_nameKey, name);
    await prefs.setString(_roleKey, role);
    await _secure.write(key: _tokenKey, value: token);
  }

  Future<RoutineFeed?> readRoutine() async {
    final prefs = await _prefs();
    final raw = prefs.getString(_routineKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return RoutineFeed.fromJson(decoded);
    } catch (_) {}
    return null;
  }

  Future<void> saveRoutine(RoutineFeed feed) async {
    final prefs = await _prefs();
    await prefs.setString(_routineKey, jsonEncode(feed.toJson()));
  }

  Future<void> clear() async {
    await _secure.delete(key: _tokenKey);
    final prefs = await _prefs();
    await prefs.remove(_usernameKey);
    await prefs.remove(_nameKey);
    await prefs.remove(_roleKey);
    await prefs.remove(_routineKey);
  }
}
