import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'models.dart';
import 'widget_sync.dart';

/// Full-screen copy of the website. The pages are the live site, not a redraw.
class SitePage extends StatefulWidget {
  const SitePage({super.key, required this.serverUrl, this.token});

  final String serverUrl;
  final String? token;

  @override
  State<SitePage> createState() => _SitePageState();
}

class _SitePageState extends State<SitePage> {
  late final WebViewController _controller;
  var _loading = true;
  String? _error;
  var _bridgeFailed = false;

  String get _root => normalizeServerUrl(widget.serverUrl);

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF0F2F5))
      ..addJavaScriptChannel(
        'RoutineChannel',
        onMessageReceived: (message) => _applyRoutine(message.message),
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) {
            if (mounted) setState(() => _error = null);
          },
          onPageFinished: (url) {
            if (!_bridgeFailed && url.contains('/api/mobile/v1/web-session')) {
              _bridgeFailed = true;
              _controller.loadRequest(Uri.parse('$_root/'));
              return;
            }
            if (mounted) setState(() => _loading = false);
            if (!url.contains('/api/')) {
              _controller.runJavaScript(_routinePull);
            }
          },
          onWebResourceError: (error) {
            if (error.isForMainFrame != true) return;
            if (mounted) {
              setState(() {
                _loading = false;
                _error = 'সাইট খোলা যায়নি। ইন্টারনেট দেখে আবার চেষ্টা করুন।';
              });
            }
          },
        ),
      );
    _open();
  }

  Future<void> _open() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final token = widget.token;
    if (token != null && token.isNotEmpty && !_bridgeFailed) {
      await _controller.loadRequest(
        Uri.parse('$_root/api/mobile/v1/web-session'),
        headers: {'Authorization': 'Bearer $token'},
      );
      return;
    }
    await _controller.loadRequest(Uri.parse('$_root/'));
  }

  Future<void> _applyRoutine(String raw) async {
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map || decoded['ok'] != true) return;
      final feed = RoutineFeed.fromJson(Map<String, dynamic>.from(decoded));
      await pushRoutineWidget(feed);
    } catch (_) {}
  }

  Future<void> _back() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
      return;
    }
    SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _back();
      },
      child: Scaffold(
        backgroundColor: const Color(0xFFF0F2F5),
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (_error != null)
                ColoredBox(
                  color: const Color(0xFFF0F2F5),
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(_error!, textAlign: TextAlign.center),
                          const SizedBox(height: 16),
                          FilledButton(onPressed: _open, child: const Text('আবার চেষ্টা')),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

const _routinePull = '''
(function() {
  fetch('/api/mobile/v1/routine-web', {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
    .then(function(response) { return response.json(); })
    .then(function(data) {
      if (window.RoutineChannel && data && data.ok) {
        RoutineChannel.postMessage(JSON.stringify(data));
      }
    })
    .catch(function() {});
})();
''';
