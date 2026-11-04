import 'package:ams_routine/src/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('routine json keeps only the signed-in classes and widget lines', () {
    final feed = RoutineFeed.fromJson({
      'viewer': 'teacher',
      'display_name': 'Test Teacher',
      'today': 'Sunday',
      'generated_at': '2026-10-18T09:00:00+06:00',
      'notice': null,
      'classes': [
        {
          'day': 'Monday',
          'time': '11:10 AM - 12:00 PM',
          'course_code': 'LAW 2103',
          'course_name': 'Contract',
          'room': '203',
          'teacher': 'TT',
          'part': 'Full',
          'shared': false,
        },
        {
          'day': 'Sunday',
          'time': '09:10 AM - 10:00 AM',
          'course_code': 'LAW 2101',
          'course_name': 'Legal History',
          'room': '201',
          'teacher': 'TT',
          'part': 'Full',
          'shared': false,
        },
      ],
      'today_classes': [
        {
          'day': 'Sunday',
          'time': '09:10 AM - 10:00 AM',
          'course_code': 'LAW 2101',
          'course_name': 'Legal History',
          'room': '201',
          'teacher': 'TT',
        },
      ],
      'widget': {
        'lines': [
          {
            'time': '9:10–10:00 AM',
            'course_code': 'LAW 2101',
            'course_name': 'Legal History',
            'detail': '201',
          },
        ],
        'more_count': 0,
      },
    });

    expect(feed.days.map((day) => day.day).toList(), ['Sunday', 'Monday']);
    expect(feed.todayClasses.single.courseCode, 'LAW 2101');
    expect(widgetBody(feed), '9:10–10:00 AM  LAW 2101\n201');
    expect(banglaDay('Sunday'), 'রবিবার');
  });

  test('empty today and known notices are in Bangla', () {
    final feed = RoutineFeed.fromJson({
      'notice': 'No published routine yet.',
      'classes': [],
      'today_classes': [],
      'widget': {'lines': [], 'more_count': 2},
    });
    expect(feed.notice, 'এখনো কোনো রুটিন প্রকাশিত হয়নি।');
    expect(widgetBody(feed), 'আজ কোনো ক্লাস নেই');
    expect(messageForErrorCode('invalid_login', ''), 'ইউজারনেম বা পাসওয়ার্ড মিলছে না।');
    expect(normalizeServerUrl('https://kulawams.xyz/'), 'https://kulawams.xyz');
    expect(isHttpUrl('kulawams.xyz'), isFalse);
    expect(splitClassTime('10:45 AM - 11:30 AM'), ('10:45 AM', '11:30 AM'));
    expect(splitClassTime('9:10–10:00 AM'), ('9:10 AM', '10:00 AM'));
    expect(tenantNameForUrl(defaultServerUrl), 'Law Discipline');
  });
}