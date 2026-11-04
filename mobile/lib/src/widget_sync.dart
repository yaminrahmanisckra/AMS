import 'dart:convert';
import 'dart:io';

import 'package:home_widget/home_widget.dart';

import 'models.dart';

const widgetAppGroupId = 'group.xyz.kulawams.amsRoutine';
const widgetAndroidProvider = 'xyz.kulawams.ams_routine.RoutineWidgetProvider';
const widgetIosKind = 'RoutineWidget';

const _androidProviders = <String>[
  'xyz.kulawams.ams_routine.RoutineWidgetSmall',
  widgetAndroidProvider,
  'xyz.kulawams.ams_routine.RoutineWidgetLarge',
];

Future<void> prepareHomeWidget() async {
  if (Platform.isIOS) {
    await HomeWidget.setAppGroupId(widgetAppGroupId);
  }
}

Future<void> pushRoutineWidget(RoutineFeed feed) async {
  final clock = updatedClock(feed.generatedAt);
  final subtitle = clock.isEmpty ? feed.today : '${feed.today} · $clock';
  await _write(
    classesJson: jsonEncode(widgetClassMaps(feed)),
    todayName: feed.today,
    title: appShortName,
    subtitle: subtitle,
    body: widgetBody(feed),
  );
}

Future<void> clearRoutineWidget() async {
  await _write(
    classesJson: '[]',
    todayName: '',
    title: appShortName,
    subtitle: '',
    body: 'অ্যাপে প্রবেশ করুন',
  );
}

Future<void> saveWidgetChoices({
  required String day,
  required String titleMode,
  required bool showRoom,
  required bool showTeacher,
  required bool showPart,
}) async {
  await prepareHomeWidget();
  await HomeWidget.saveWidgetData<String>('pref_day', day);
  await HomeWidget.saveWidgetData<String>('pref_title', titleMode);
  await HomeWidget.saveWidgetData<bool>('pref_room', showRoom);
  await HomeWidget.saveWidgetData<bool>('pref_teacher', showTeacher);
  await HomeWidget.saveWidgetData<bool>('pref_part', showPart);
  await _updateAll();
}

Future<bool> pinRoutineWidget() async {
  final supported = await HomeWidget.isRequestPinWidgetSupported();
  if (supported != true) return false;
  await HomeWidget.requestPinWidget(qualifiedAndroidName: widgetAndroidProvider);
  return true;
}

Future<void> _write({
  required String classesJson,
  required String todayName,
  required String title,
  required String subtitle,
  required String body,
}) async {
  await prepareHomeWidget();
  await HomeWidget.saveWidgetData<String>('classes_json', classesJson);
  await HomeWidget.saveWidgetData<String>('today_name', todayName);
  await HomeWidget.saveWidgetData<String>('title', title);
  await HomeWidget.saveWidgetData<String>('subtitle', subtitle);
  await HomeWidget.saveWidgetData<String>('body', body);
  await _updateAll();
}

Future<void> _updateAll() async {
  for (final provider in _androidProviders) {
    await HomeWidget.updateWidget(qualifiedAndroidName: provider, iOSName: widgetIosKind);
  }
}
