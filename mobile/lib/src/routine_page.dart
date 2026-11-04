import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'models.dart';
import 'session.dart';
import 'site_page.dart';
import 'theme.dart';
import 'widget_settings.dart';
import 'widget_sync.dart';

class RoutinePage extends StatefulWidget {
  const RoutinePage({
    super.key,
    required this.session,
    required this.api,
    required this.store,
    required this.onSignOut,
  });

  final Session session;
  final RoutineApi api;
  final SessionStore store;
  final Future<void> Function() onSignOut;

  @override
  State<RoutinePage> createState() => _RoutinePageState();
}

class _RoutinePageState extends State<RoutinePage> with WidgetsBindingObserver {
  RoutineFeed? _feed;
  String? _error;
  var _loading = true;
  var _signingOut = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _load(quiet: true);
    }
  }

  Future<void> _load({bool quiet = false}) async {
    if (!quiet && _feed == null) {
      final cached = await widget.store.readRoutine();
      if (!mounted) return;
      if (cached != null) {
        setState(() {
          _feed = cached;
          _loading = false;
        });
        await _pushWidget(cached);
      } else {
        setState(() {
          _loading = true;
          _error = null;
        });
      }
    }
    try {
      final feed = await widget.api.routine(
        serverUrl: widget.session.serverUrl,
        token: widget.session.token,
      );
      await widget.store.saveRoutine(feed);
      await _pushWidget(feed);
      if (!mounted) return;
      setState(() {
        _feed = feed;
        _error = null;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = _feed == null ? error.message : 'শেষ সেভ করা ক্লাস দেখানো হচ্ছে।';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = _feed == null ? 'রুটিন আনা যায়নি।' : 'শেষ সেভ করা ক্লাস দেখানো হচ্ছে।';
        _loading = false;
      });
    }
  }

  Future<void> _pushWidget(RoutineFeed feed) async {
    try {
      await pushRoutineWidget(feed);
    } catch (_) {}
  }

  Future<void> _signOut() async {
    final leave = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.card,
        title: const Text('প্রস্থান করবেন?'),
        content: const Text('প্রস্থান করলে হোমস্ক্রিনের উইজেট থেকে ক্লাস মুছে যাবে।'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('থাকুন')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('প্রস্থান')),
        ],
      ),
    );
    if (leave != true || !mounted) return;
    setState(() => _signingOut = true);
    await widget.onSignOut();
  }

  Future<void> _addWidget() async {
    final pinned = await pinRoutineWidget();
    if (!mounted) return;
    final message = pinned
        ? 'হোমস্ক্রিনে উইজেট যোগ করার অনুমতি চাওয়া হয়েছে।'
        : 'হোমস্ক্রিনে কিছুক্ষণ চেপে ধরুন, তারপর উইজেট থেকে «আজকের ক্লাস» যোগ করুন। আইফোনে + চাপুন।';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final feed = _feed;
    final name = feed?.displayName.isNotEmpty == true ? feed!.displayName : widget.session.name;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: AppColors.cream,
        body: RefreshIndicator(
          color: AppColors.teal,
          onRefresh: () => _load(quiet: true),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.zero,
            children: [
              _Header(
                name: name,
                role: roleLabel(widget.session.role),
                loading: _loading,
                signingOut: _signingOut,
                onRefresh: () => _load(),
                onSignOut: _signOut,
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 18, 16, 36),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_loading && feed == null)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 48),
                        child: Center(child: CircularProgressIndicator(color: AppColors.teal)),
                      )
                    else ...[
                      if (_error != null) ...[
                        _SoftNote(message: _error!),
                        const SizedBox(height: 12),
                      ],
                      _TodayPanel(feed: feed),
                      const SizedBox(height: 14),
                      FilledButton.icon(
                        onPressed: () {
                          Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => SitePage(
                                serverUrl: widget.session.serverUrl,
                                token: widget.session.token,
                              ),
                            ),
                          );
                        },
                        icon: const Icon(Icons.language_rounded),
                        label: const Text('ওয়েব অ্যাপের সব ফিচার'),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'এই বোতামে মূল ওয়েবসাইট খোলে। ওয়েবে যা বদলাবে, এখানেই দেখা যাবে।',
                        style: TextStyle(color: AppColors.muted, fontSize: 12.5, height: 1.35),
                      ),
                      const SizedBox(height: 14),
                      _WidgetButton(onPressed: _addWidget),
                      const SizedBox(height: 10),
                      const WidgetSettingsCard(),
                      const SizedBox(height: 8),
                      const Text(
                        'উইজেট অ্যাপ খুললে আপডেট হয়। নেট না থাকলে শেষ সেভ করা ক্লাসই থাকে।',
                        style: TextStyle(color: AppColors.muted, fontSize: 12.5, height: 1.35),
                      ),
                      const SizedBox(height: 22),
                      const _SectionTitle(title: 'সপ্তাহ'),
                      const SizedBox(height: 10),
                      if (feed == null || feed.classes.isEmpty)
                        _EmptyWeek(notice: feed?.notice ?? '')
                      else
                        for (final day in feed.days) ...[
                          _DayLabel(day: day.day, today: feed.today),
                          for (var i = 0; i < day.slots.length; i++)
                            _ClassCard(slot: day.slots[i], accent: accentFor(day.day, i)),
                          const SizedBox(height: 6),
                        ],
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.name,
    required this.role,
    required this.loading,
    required this.signingOut,
    required this.onRefresh,
    required this.onSignOut,
  });

  final String name;
  final String role;
  final bool loading;
  final bool signingOut;
  final VoidCallback onRefresh;
  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.navyDeep, AppColors.navy, Color(0xFF145E56)],
        ),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 12, 22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Text(
                    'AMS',
                    style: TextStyle(color: Color(0xFFE7E1D4), fontSize: 14, fontWeight: FontWeight.w600),
                  ),
                  const Spacer(),
                  _RoundIcon(
                    tooltip: 'রিফ্রেশ',
                    icon: Icons.refresh_rounded,
                    onPressed: loading ? null : onRefresh,
                  ),
                  _RoundIcon(
                    tooltip: 'প্রস্থান',
                    icon: Icons.logout_rounded,
                    onPressed: signingOut ? null : onSignOut,
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppColors.gold,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(
                      _initials(name),
                      style: const TextStyle(
                        color: AppColors.navy,
                        fontWeight: FontWeight.w800,
                        fontSize: 18,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name.isEmpty ? 'আমার রুটিন' : name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            height: 1.15,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0x33FFFFFF),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: const Color(0x55D4A017)),
                          ),
                          child: Text(role, style: const TextStyle(color: AppColors.goldSoft, fontSize: 12)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoundIcon extends StatelessWidget {
  const _RoundIcon({required this.tooltip, required this.icon, required this.onPressed});

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: Icon(icon, color: Colors.white),
    );
  }
}

class _TodayPanel extends StatelessWidget {
  const _TodayPanel({required this.feed});

  final RoutineFeed? feed;

  @override
  Widget build(BuildContext context) {
    final slots = feed?.todayClasses ?? const <ClassSlot>[];
    final clock = feed == null ? '' : updatedClock(feed!.generatedAt);
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE8D7A8)),
        boxShadow: const [
          BoxShadow(color: Color(0x140F2438), blurRadius: 18, offset: Offset(0, 8)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            decoration: const BoxDecoration(
              gradient: LinearGradient(colors: [Color(0xFF14685C), AppColors.teal]),
              borderRadius: BorderRadius.vertical(top: Radius.circular(21)),
            ),
            child: Row(
              children: [
                const Icon(Icons.wb_sunny_rounded, color: AppColors.gold, size: 22),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    feed == null ? 'আজকের ক্লাস' : 'আজ · ${banglaDay(feed!.today)}',
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                ),
                if (clock.isNotEmpty)
                  Text('সর্বশেষ $clock', style: const TextStyle(color: Color(0xFFE7F6F2), fontSize: 12)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
            child: slots.isEmpty
                ? Padding(
                    padding: const EdgeInsets.fromLTRB(4, 4, 4, 12),
                    child: Text(
                      feed?.notice.isNotEmpty == true ? feed!.notice : 'আজ কোনো ক্লাস নেই',
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  )
                : Column(
                    children: [
                      for (var i = 0; i < slots.length; i++)
                        _ClassCard(slot: slots[i], accent: accentFor(slots[i].day, i), compact: true),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _ClassCard extends StatelessWidget {
  const _ClassCard({required this.slot, required this.accent, this.compact = false});

  final ClassSlot slot;
  final Color accent;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final title = slot.courseCode.isNotEmpty ? slot.courseCode : slot.courseName;
    final chips = <String>[
      if (slot.room.isNotEmpty) slot.room,
      if (slot.teacher.isNotEmpty) slot.teacher,
      if (slot.part.isNotEmpty && slot.part != 'Full') slot.part,
      if (slot.shared) 'শেয়ার্ড',
    ];
    return Container(
      margin: EdgeInsets.only(bottom: compact ? 8 : 10),
      decoration: BoxDecoration(
        color: compact ? const Color(0xFFF8F5EE) : AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: compact ? null : Border.all(color: AppColors.line),
        boxShadow: compact
            ? null
            : const [BoxShadow(color: Color(0x0F10243F), blurRadius: 10, offset: Offset(0, 4))],
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 6,
              decoration: BoxDecoration(
                color: accent,
                borderRadius: const BorderRadius.horizontal(left: Radius.circular(16)),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700, fontSize: 15),
                    ),
                    if (slot.courseName.isNotEmpty && slot.courseName != title) ...[
                      const SizedBox(height: 2),
                      Text(slot.courseName, style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                    ],
                    if (chips.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [for (final chip in chips) _Chip(label: chip, color: accent)],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(0, 12, 12, 12),
              child: Align(
                alignment: Alignment.topCenter,
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 108),
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    slot.time,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: accent, fontWeight: FontWeight.w700, fontSize: 11.5, height: 1.25),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 11.5, fontWeight: FontWeight.w600)),
    );
  }
}

class _DayLabel extends StatelessWidget {
  const _DayLabel({required this.day, required this.today});

  final String day;
  final String today;

  @override
  Widget build(BuildContext context) {
    final isToday = day.toLowerCase() == today.toLowerCase();
    final color = accentFor(day, 0);
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 8),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(
            banglaDay(day),
            style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700, fontSize: 15),
          ),
          if (isToday) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.goldSoft,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Text(
                'আজ',
                style: TextStyle(color: Color(0xFF8A6508), fontSize: 11, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.navy)),
        const SizedBox(width: 10),
        const Expanded(child: Divider(color: AppColors.line, thickness: 1.2)),
      ],
    );
  }
}

class _WidgetButton extends StatelessWidget {
  const _WidgetButton({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.tealDeep,
        side: const BorderSide(color: AppColors.teal),
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      icon: const Icon(Icons.widgets_rounded),
      label: const Text('হোমস্ক্রিনে আজকের ক্লাস রাখুন', style: TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}

class _SoftNote extends StatelessWidget {
  const _SoftNote({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.goldSoft,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 18, color: Color(0xFF8A6508)),
          const SizedBox(width: 8),
          Expanded(child: Text(message, style: const TextStyle(color: Color(0xFF6E5310)))),
        ],
      ),
    );
  }
}

class _EmptyWeek extends StatelessWidget {
  const _EmptyWeek({required this.notice});

  final String notice;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line),
      ),
      child: Text(
        notice.isNotEmpty ? notice : 'কোনো ক্লাস নেই।',
        style: const TextStyle(color: AppColors.muted),
      ),
    );
  }
}

const _dayKeys = <String>[
  'sunday',
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
];

Color accentFor(String day, int index) {
  final dayIndex = _dayKeys.indexOf(day.trim().toLowerCase());
  final base = dayIndex < 0 ? index : dayIndex + index;
  return AppColors.accents[base % AppColors.accents.length];
}

String _initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+')).where((part) => part.isNotEmpty).toList();
  if (parts.isEmpty) return 'ক';
  String letter(String word) {
    final cleaned = word.replaceAll('.', '');
    if (cleaned.isEmpty) return '';
    return cleaned[0].toUpperCase();
  }

  if (parts.length == 1) {
    final one = letter(parts.first);
    return one.isEmpty ? 'ক' : one;
  }
  return '${letter(parts.first)}${letter(parts.last)}';
}
