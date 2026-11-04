import 'package:flutter/material.dart';
import 'package:home_widget/home_widget.dart';

import 'models.dart';
import 'theme.dart';
import 'widget_sync.dart';

class WidgetSettingsCard extends StatefulWidget {
  const WidgetSettingsCard({super.key});

  @override
  State<WidgetSettingsCard> createState() => _WidgetSettingsCardState();
}

class _WidgetSettingsCardState extends State<WidgetSettingsCard> {
  String _day = 'today';
  String _titleMode = 'name';
  var _room = true;
  var _teacher = false;
  var _part = true;
  var _ready = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final day = await HomeWidget.getWidgetData<String>('pref_day');
      final title = await HomeWidget.getWidgetData<String>('pref_title');
      final room = await HomeWidget.getWidgetData<bool>('pref_room');
      final teacher = await HomeWidget.getWidgetData<bool>('pref_teacher');
      final part = await HomeWidget.getWidgetData<bool>('pref_part');
      if (!mounted) return;
      setState(() {
        _day = day ?? 'today';
        _titleMode = title ?? 'name';
        _room = room ?? true;
        _teacher = teacher ?? false;
        _part = part ?? true;
        _ready = true;
      });
    } catch (_) {
      if (mounted) setState(() => _ready = true);
    }
  }

  Future<void> _save() async {
    await saveWidgetChoices(
      day: _day,
      titleMode: _titleMode,
      showRoom: _room,
      showTeacher: _teacher,
      showPart: _part,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('উইজেট আপডেট হয়েছে।')));
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('উইজেটে যা দেখাবেন', style: TextStyle(fontWeight: FontWeight.w800, color: AppColors.navy)),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: widgetDayChoices.any((item) => item.$1 == _day) ? _day : 'today',
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'দিন'),
            items: [
              for (final choice in widgetDayChoices)
                DropdownMenuItem(value: choice.$1, child: Text(choice.$2)),
            ],
            onChanged: (value) {
              if (value == null) return;
              setState(() => _day = value);
              _save();
            },
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _titleMode == 'code' ? 'code' : 'name',
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'শিরোনাম'),
            items: const [
              DropdownMenuItem(value: 'name', child: Text('কোর্সের নাম')),
              DropdownMenuItem(value: 'code', child: Text('কোর্স কোড')),
            ],
            onChanged: (value) {
              if (value == null) return;
              setState(() => _titleMode = value);
              _save();
            },
          ),
          Wrap(
            spacing: 8,
            children: [
              FilterChip(
                label: const Text('রুম'),
                selected: _room,
                onSelected: (value) {
                  setState(() => _room = value);
                  _save();
                },
              ),
              FilterChip(
                label: const Text('শিক্ষক'),
                selected: _teacher,
                onSelected: (value) {
                  setState(() => _teacher = value);
                  _save();
                },
              ),
              FilterChip(
                label: const Text('পার্ট'),
                selected: _part,
                onSelected: (value) {
                  setState(() => _part = value);
                  _save();
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}
