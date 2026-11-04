import SwiftUI
import WidgetKit

private let widgetGroupId = "group.xyz.kulawams.amsRoutine"

struct RoutineEntry: TimelineEntry {
    let date: Date
    let title: String
    let subtitle: String
    let body: String
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> RoutineEntry {
        RoutineEntry(date: Date(), title: "আজকের ক্লাস", subtitle: "", body: "ক্লাস দেখতে অ্যাপ খুলুন")
    }

    func getSnapshot(in context: Context, completion: @escaping (RoutineEntry) -> Void) {
        let prefs = UserDefaults(suiteName: widgetGroupId)
        let entry = RoutineEntry(
            date: Date(),
            title: prefs?.string(forKey: "title") ?? "আজকের ক্লাস",
            subtitle: prefs?.string(forKey: "subtitle") ?? "",
            body: prefs?.string(forKey: "body") ?? "ক্লাস দেখতে অ্যাপ খুলুন"
        )
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<RoutineEntry>) -> Void) {
        getSnapshot(in: context) { entry in
            completion(Timeline(entries: [entry], policy: .atEnd))
        }
    }
}

struct RoutineWidgetEntryView: View {
    var entry: RoutineEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(entry.title)
                .font(.headline)
                .foregroundStyle(Color(red: 0.106, green: 0.227, blue: 0.294))
            if !entry.subtitle.isEmpty {
                Text(entry.subtitle)
                    .font(.caption)
                    .foregroundStyle(Color(red: 0.361, green: 0.420, blue: 0.400))
            }
            Text(entry.body)
                .font(.subheadline)
                .foregroundStyle(Color(red: 0.141, green: 0.188, blue: 0.157))
                .padding(.top, 4)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .padding(14)
    }
}

@main
struct RoutineWidget: Widget {
    let kind: String = "RoutineWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            RoutineWidgetEntryView(entry: entry)
                .modifier(RoutineWidgetBackground())
        }
        .configurationDisplayName("আজকের ক্লাস")
        .description("শুধু আপনার আজকের ক্লাস")
        .supportedFamilies([.systemMedium, .systemLarge])
    }
}

struct RoutineWidgetBackground: ViewModifier {
    func body(content: Content) -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            content.containerBackground(Color(red: 0.957, green: 0.945, blue: 0.918), for: .widget)
        } else {
            content.background(Color(red: 0.957, green: 0.945, blue: 0.918))
        }
    }
}
