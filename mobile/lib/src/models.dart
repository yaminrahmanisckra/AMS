const defaultServerUrl = 'https://kulawams.xyz';
const appShortName = 'AMS';
const appFullName = 'Academic Management System';

class AmsTenant {
  const AmsTenant({required this.name, required this.url});

  final String name;
  final String url;
}

const amsTenants = <AmsTenant>[
  AmsTenant(name: 'Law Discipline', url: defaultServerUrl),
];

String tenantNameForUrl(String url) {
  final normalized = normalizeServerUrl(url);
  for (final tenant in amsTenants) {
    if (normalizeServerUrl(tenant.url) == normalized) return tenant.name;
  }
  return 'Khulna University';
}

const dayLabels = <String, String>{
  'sunday': 'রবিবার',
  'monday': 'সোমবার',
  'tuesday': 'মঙ্গলবার',
  'wednesday': 'বুধবার',
  'thursday': 'বৃহস্পতিবার',
  'friday': 'শুক্রবার',
  'saturday': 'শনিবার',
};

const _dayOrder = <String>[
  'sunday',
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
];

String banglaDay(String english) {
  final key = english.trim().toLowerCase();
  return dayLabels[key] ?? english;
}

String normalizeServerUrl(String raw) {
  var value = raw.trim();
  while (value.endsWith('/')) {
    value = value.substring(0, value.length - 1);
  }
  return value;
}

bool isHttpUrl(String value) {
  final uri = Uri.tryParse(value);
  if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
    return false;
  }
  return uri.scheme == 'https' || uri.scheme == 'http';
}

String messageForErrorCode(String code, String fallback) {
  switch (code) {
    case 'invalid_login':
      return 'ইউজারনেম বা পাসওয়ার্ড মিলছে না।';
    case 'password_change_required':
      return 'আগে ওয়েবসাইটে পাসওয়ার্ড বদলান, তারপর এখানে প্রবেশ করুন।';
    case 'role_not_supported':
      return 'এই অ্যাপ শিক্ষক ও শিক্ষার্থীদের জন্য।';
    case 'feature_disabled':
      return 'রুটিন এখন বন্ধ আছে।';
    case 'too_many_attempts':
      return 'অনেকবার চেষ্টা হয়েছে। একটু পরে আবার চেষ্টা করুন।';
    case 'invalid_token':
      return 'আবার প্রবেশ করুন।';
    case 'invalid_body':
      return 'ইউজারনেম ও পাসওয়ার্ড দিন।';
    default:
      return fallback.isEmpty ? 'কাজটি হয়নি। আবার চেষ্টা করুন।' : fallback;
  }
}

String banglaNotice(String? notice) {
  switch (notice) {
    case null:
    case '':
      return '';
    case 'No published routine yet.':
      return 'এখনো কোনো রুটিন প্রকাশিত হয়নি।';
    case 'None of your classes are in the published routine.':
      return 'প্রকাশিত রুটিনে আপনার কোনো ক্লাস নেই।';
    case 'Your account is not linked to a teacher profile.':
      return 'এই অ্যাকাউন্ট কোনো শিক্ষকের সাথে যুক্ত নয়।';
    case 'No student record is linked to this account.':
      return 'এই অ্যাকাউন্টের শিক্ষার্থী তথ্য পাওয়া যায়নি।';
    default:
      return notice;
  }
}

String roleLabel(String role) {
  if (role == 'student') return 'শিক্ষার্থী';
  if (role == 'teacher') return 'শিক্ষক';
  return role;
}

class ClassSlot {
  const ClassSlot({
    required this.day,
    required this.time,
    required this.courseCode,
    required this.courseName,
    required this.room,
    required this.teacher,
    required this.part,
    required this.shared,
    required this.year,
    required this.term,
    required this.windowName,
  });

  final String day;
  final String time;
  final String courseCode;
  final String courseName;
  final String room;
  final String teacher;
  final String part;
  final bool shared;
  final String year;
  final String term;
  final String windowName;

  factory ClassSlot.fromJson(Map<String, dynamic> json) {
    return ClassSlot(
      day: _text(json['day']),
      time: _text(json['time']),
      courseCode: _text(json['course_code']),
      courseName: _text(json['course_name']),
      room: _text(json['room']),
      teacher: _text(json['teacher']),
      part: _text(json['part']),
      shared: json['shared'] == true,
      year: _text(json['year']),
      term: _text(json['term']),
      windowName: _text(json['window_name']),
    );
  }

  Map<String, dynamic> toJson() => {
        'day': day,
        'time': time,
        'course_code': courseCode,
        'course_name': courseName,
        'room': room,
        'teacher': teacher,
        'part': part,
        'shared': shared,
        'year': year,
        'term': term,
        'window_name': windowName,
      };
}

class WidgetLine {
  const WidgetLine({
    required this.time,
    required this.courseCode,
    required this.courseName,
    required this.detail,
  });

  final String time;
  final String courseCode;
  final String courseName;
  final String detail;

  factory WidgetLine.fromJson(Map<String, dynamic> json) {
    return WidgetLine(
      time: _text(json['time']),
      courseCode: _text(json['course_code']),
      courseName: _text(json['course_name']),
      detail: _text(json['detail']),
    );
  }

  Map<String, dynamic> toJson() => {
        'time': time,
        'course_code': courseCode,
        'course_name': courseName,
        'detail': detail,
      };
}

class RoutineFeed {
  const RoutineFeed({
    required this.viewer,
    required this.displayName,
    required this.today,
    required this.generatedAt,
    required this.notice,
    required this.classes,
    required this.todayClasses,
    required this.widgetLines,
    required this.moreCount,
  });

  final String viewer;
  final String displayName;
  final String today;
  final String generatedAt;
  final String notice;
  final List<ClassSlot> classes;
  final List<ClassSlot> todayClasses;
  final List<WidgetLine> widgetLines;
  final int moreCount;

  factory RoutineFeed.fromJson(Map<String, dynamic> json) {
    final widget = json['widget'];
    final widgetMap = widget is Map<String, dynamic> ? widget : <String, dynamic>{};
    return RoutineFeed(
      viewer: _text(json['viewer']),
      displayName: _text(json['display_name']),
      today: _text(json['today']),
      generatedAt: _text(json['generated_at']),
      notice: banglaNotice(_text(json['notice'])),
      classes: _slots(json['classes']),
      todayClasses: _slots(json['today_classes']),
      widgetLines: _lines(widgetMap['lines']),
      moreCount: widgetMap['more_count'] is int ? widgetMap['more_count'] as int : 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'viewer': viewer,
        'display_name': displayName,
        'today': today,
        'generated_at': generatedAt,
        'notice': notice,
        'classes': [for (final slot in classes) slot.toJson()],
        'today_classes': [for (final slot in todayClasses) slot.toJson()],
        'widget': {
          'lines': [for (final line in widgetLines) line.toJson()],
          'more_count': moreCount,
        },
      };

  List<DayGroup> get days {
    final grouped = <String, List<ClassSlot>>{};
    for (final slot in classes) {
      grouped.putIfAbsent(slot.day.toLowerCase(), () => <ClassSlot>[]).add(slot);
    }
    final keys = grouped.keys.toList()
      ..sort((a, b) {
        final ai = _dayOrder.indexOf(a);
        final bi = _dayOrder.indexOf(b);
        return (ai < 0 ? 99 : ai).compareTo(bi < 0 ? 99 : bi);
      });
    return [
      for (final key in keys) DayGroup(day: grouped[key]!.first.day, slots: grouped[key]!),
    ];
  }
}

class DayGroup {
  const DayGroup({required this.day, required this.slots});

  final String day;
  final List<ClassSlot> slots;
}

const widgetDayChoices = <(String, String)>[
  ('today', 'আজ'),
  ('Sunday', 'রবিবার'),
  ('Monday', 'সোমবার'),
  ('Tuesday', 'মঙ্গলবার'),
  ('Wednesday', 'বুধবার'),
  ('Thursday', 'বৃহস্পতিবার'),
  ('Friday', 'শুক্রবার'),
  ('Saturday', 'শনিবার'),
];

(String, String) splitClassTime(String raw) {
  final time = raw.trim();
  if (time.isEmpty) return ('', '');
  final parts = time.split(RegExp(r'\s*[-–—]\s*')).where((part) => part.trim().isNotEmpty).toList();
  if (parts.length < 2) return (time, '');
  var start = parts.first.trim();
  final end = parts.sublist(1).join(' - ').trim();
  final meridian = RegExp(r'\b(AM|PM)\b', caseSensitive: false);
  if (!meridian.hasMatch(start)) {
    final endMeridian = meridian.firstMatch(end);
    if (endMeridian != null) {
      start = '$start ${endMeridian.group(1)}';
    }
  }
  return (start, end);
}

List<Map<String, String>> widgetClassMaps(RoutineFeed feed) {
  return [
    for (final slot in feed.classes)
      () {
        final times = splitClassTime(slot.time);
        return {
          'day': slot.day,
          'start': times.$1,
          'end': times.$2,
          'code': slot.courseCode,
          'name': slot.courseName,
          'room': slot.room,
          'teacher': slot.teacher,
          'part': slot.part,
        };
      }(),
  ];
}

String widgetBody(RoutineFeed feed) {
  if (feed.widgetLines.isEmpty) {
    return 'আজ কোনো ক্লাস নেই';
  }
  final buffer = StringBuffer();
  for (var i = 0; i < feed.widgetLines.length; i++) {
    if (i > 0) buffer.writeln();
    final line = feed.widgetLines[i];
    final course = line.courseCode.isNotEmpty ? line.courseCode : line.courseName;
    buffer.write(line.time);
    if (course.isNotEmpty) {
      buffer.write('  $course');
    }
    if (line.detail.isNotEmpty) {
      buffer.writeln();
      buffer.write(line.detail);
    }
  }
  if (feed.moreCount > 0) {
    buffer.writeln();
    buffer.write('আরও ${feed.moreCount}টি');
  }
  return buffer.toString();
}

String updatedClock(String iso) {
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) return '';
  final local = parsed.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}

String _text(Object? value) {
  if (value == null) return '';
  return value.toString();
}

List<ClassSlot> _slots(Object? value) {
  if (value is! List) return const [];
  return [
    for (final item in value)
      if (item is Map<String, dynamic>) ClassSlot.fromJson(item),
  ];
}

List<WidgetLine> _lines(Object? value) {
  if (value is! List) return const [];
  return [
    for (final item in value)
      if (item is Map<String, dynamic>) WidgetLine.fromJson(item),
  ];
}
