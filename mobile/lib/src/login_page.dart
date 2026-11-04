import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'models.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({
    super.key,
    required this.initialServer,
    required this.onSubmit,
  });

  final String initialServer;
  final Future<void> Function(String server, String username, String password) onSubmit;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  late final TextEditingController _server;
  var _busy = false;
  var _obscure = true;
  var _other = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final initial = normalizeServerUrl(widget.initialServer);
    final known = amsTenants.any((tenant) => normalizeServerUrl(tenant.url) == initial);
    _other = initial.isNotEmpty && !known;
    _server = TextEditingController(text: _other ? initial : '');
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _server.dispose();
    super.dispose();
  }

  String get _activeServer {
    if (_other) return normalizeServerUrl(_server.text);
    return defaultServerUrl;
  }

  Future<void> _submit() async {
    final username = _username.text.trim();
    final password = _password.text;
    final server = _activeServer;
    if (_other && !isHttpUrl(server)) {
      setState(() => _error = 'Institution address must start with http or https.');
      return;
    }
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter your username and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.onSubmit(server, username, password);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not sign in. Try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        body: DecoratedBox(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF667EEA), Color(0xFF764BA2), Color(0xFFF093FB)],
            ),
          ),
          child: SafeArea(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
              children: [
                  const _UniversityHeader(),
                  Text(
                    tenantNameForUrl(_activeServer),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(height: 18),
                  _LoginCard(
                    username: _username,
                    password: _password,
                    server: _server,
                    obscure: _obscure,
                    other: _other,
                    busy: _busy,
                    error: _error,
                    onToggleObscure: () => setState(() => _obscure = !_obscure),
                    onToggleOther: () => setState(() {
                      _other = !_other;
                      _error = null;
                    }),
                    onServerChanged: () => setState(() {}),
                    onSubmit: _busy ? null : _submit,
                  ),
                ],
            ),
          ),
        ),
      ),
    );
  }
}

class _UniversityHeader extends StatelessWidget {
  const _UniversityHeader();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Image.asset('assets/ku_logo.png', width: 92, fit: BoxFit.contain),
        const SizedBox(height: 12),
        const Text(
          appFullName,
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600, height: 1.35),
        ),
        const SizedBox(height: 4),
      ],
    );
  }
}

class _LoginCard extends StatelessWidget {
  const _LoginCard({
    required this.username,
    required this.password,
    required this.server,
    required this.obscure,
    required this.other,
    required this.busy,
    required this.error,
    required this.onToggleObscure,
    required this.onToggleOther,
    required this.onServerChanged,
    required this.onSubmit,
  });

  final TextEditingController username;
  final TextEditingController password;
  final TextEditingController server;
  final bool obscure;
  final bool other;
  final bool busy;
  final String? error;
  final VoidCallback onToggleObscure;
  final VoidCallback onToggleOther;
  final VoidCallback onServerChanged;
  final VoidCallback? onSubmit;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 360),
      decoration: BoxDecoration(
        color: const Color(0xFAFFFFFF),
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: Column(
        children: [
          Container(
            height: 5,
            decoration: const BoxDecoration(
              borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              gradient: LinearGradient(colors: [Color(0xFF667EEA), Color(0xFF764BA2), Color(0xFFF093FB)]),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      gradient: const LinearGradient(colors: [Color(0xFF667EEA), Color(0xFF764BA2)]),
                      boxShadow: const [BoxShadow(color: Color(0x4D667EEA), blurRadius: 12, offset: Offset(0, 6))],
                    ),
                    child: const Icon(Icons.school_rounded, color: Colors.white, size: 22),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Welcome Back',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Color(0xFF2D3748), fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 2),
                const Text(
                  'Sign in to your account',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Color(0xFF718096), fontSize: 13),
                ),
                const SizedBox(height: 14),
                if (other) ...[
                  const _FieldLabel(icon: Icons.account_balance_outlined, text: 'Institution'),
                  TextField(
                    controller: server,
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    onChanged: (_) => onServerChanged(),
                    decoration: _fieldDecoration('https://'),
                  ),
                  const SizedBox(height: 12),
                ],
                const _FieldLabel(icon: Icons.person_outline, text: 'Username'),
                TextField(
                  controller: username,
                  autocorrect: false,
                  enableSuggestions: false,
                  textInputAction: TextInputAction.next,
                  decoration: _fieldDecoration('Enter your username'),
                ),
                const SizedBox(height: 12),
                const _FieldLabel(icon: Icons.lock_outline, text: 'Password'),
                TextField(
                  controller: password,
                  obscureText: obscure,
                  onSubmitted: (_) => onSubmit?.call(),
                  decoration: _fieldDecoration('Enter your password').copyWith(
                    suffixIcon: IconButton(
                      onPressed: onToggleObscure,
                      icon: Icon(obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                    ),
                  ),
                ),
                if (error != null) ...[
                  const SizedBox(height: 10),
                  Text(error!, style: const TextStyle(color: Color(0xFFC53030), fontSize: 13)),
                ],
                const SizedBox(height: 16),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [Color(0xFF667EEA), Color(0xFF764BA2)]),
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: const [BoxShadow(color: Color(0x66667EEA), blurRadius: 12, offset: Offset(0, 4))],
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: onSubmit,
                      borderRadius: BorderRadius.circular(10),
                      child: SizedBox(
                        height: 44,
                        child: Center(
                          child: busy
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                )
                              : const Text(
                                  'Sign In',
                                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                                ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.center,
                  child: TextButton(
                    onPressed: onToggleOther,
                    child: Text(other ? 'Use Law Discipline' : 'Other institution'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FieldLabel extends StatelessWidget {
  const _FieldLabel({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(icon, size: 14, color: Color(0xFF667EEA)),
          const SizedBox(width: 6),
          Text(text, style: const TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.w600, fontSize: 13)),
        ],
      ),
    );
  }
}

InputDecoration _fieldDecoration(String hint) {
  return InputDecoration(
    hintText: hint,
    isDense: true,
    filled: true,
    fillColor: const Color(0xFFF7FAFC),
    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
    hintStyle: const TextStyle(color: Color(0xFFA0AEC0), fontSize: 13),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: const BorderSide(color: Color(0xFFE2E8F0), width: 2),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: const BorderSide(color: Color(0xFF667EEA), width: 2),
    ),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
  );
}
