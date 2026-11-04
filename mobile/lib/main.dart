import 'package:flutter/material.dart';

import 'package:flutter/services.dart';

import 'src/api.dart';
import 'src/models.dart';
import 'src/session.dart';
import 'src/site_page.dart';
import 'src/theme.dart';
import 'src/widget_sync.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await prepareHomeWidget();
  runApp(const RoutineApp());
}

class RoutineApp extends StatefulWidget {
  const RoutineApp({super.key});

  @override
  State<RoutineApp> createState() => _RoutineAppState();
}

class _RoutineAppState extends State<RoutineApp> {
  final _store = SessionStore();
  final _api = RoutineApi();
  Session? _session;
  var _ready = false;
  var _server = defaultServerUrl;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final session = await _store.read();
    final server = await _store.readServerUrl();
    if (!mounted) return;
    setState(() {
      _session = session;
      _server = server;
      _ready = true;
    });
    if (session != null) {
      _refreshWidget(session);
    }
  }

  Future<void> _refreshWidget(Session session) async {
    try {
      final feed = await _api.routine(serverUrl: session.serverUrl, token: session.token);
      await _store.saveRoutine(feed);
      await pushRoutineWidget(feed);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: appFullName,
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: !_ready
          ? const _BootScreen()
          : SitePage(serverUrl: _server, token: _session?.token),
    );
  }
}

class _BootScreen extends StatelessWidget {
  const _BootScreen();

  @override
  Widget build(BuildContext context) {
    return const AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: AppColors.navy,
        body: Center(child: CircularProgressIndicator(color: AppColors.gold)),
      ),
    );
  }
}
