package xyz.kulawams.ams_routine

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.view.View
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetPlugin
import es.antonborri.home_widget.HomeWidgetProvider
import org.json.JSONArray
import org.json.JSONObject

private class WidgetRow(
    val row: Int,
    val line: Int,
    val start: Int,
    val end: Int,
    val bar: Int,
    val title: Int,
    val detail: Int,
)

private val widgetRows = arrayOf(
    WidgetRow(R.id.row_0, R.id.line_0, R.id.start_0, R.id.end_0, R.id.bar_0, R.id.title_0, R.id.detail_0),
    WidgetRow(R.id.row_1, R.id.line_1, R.id.start_1, R.id.end_1, R.id.bar_1, R.id.title_1, R.id.detail_1),
    WidgetRow(R.id.row_2, R.id.line_2, R.id.start_2, R.id.end_2, R.id.bar_2, R.id.title_2, R.id.detail_2),
    WidgetRow(R.id.row_3, R.id.line_3, R.id.start_3, R.id.end_3, R.id.bar_3, R.id.title_3, R.id.detail_3),
    WidgetRow(R.id.row_4, R.id.line_4, R.id.start_4, R.id.end_4, R.id.bar_4, R.id.title_4, R.id.detail_4),
    WidgetRow(R.id.row_5, R.id.line_5, R.id.start_5, R.id.end_5, R.id.bar_5, R.id.title_5, R.id.detail_5),
)

private val barColors = intArrayOf(
    0xFFF5C518.toInt(),
    0xFFF5A623.toInt(),
    0xFFF08A24.toInt(),
    0xFFE07A14.toInt(),
)

private val widgetProviders = listOf(
    RoutineWidgetSmall::class.java to 2,
    RoutineWidgetProvider::class.java to 4,
    RoutineWidgetLarge::class.java to 6,
)

fun updateRoutineWidgets(context: Context) {
    val manager = AppWidgetManager.getInstance(context)
    val prefs = HomeWidgetPlugin.getData(context)
    for ((cls, fallback) in widgetProviders) {
        val ids = manager.getAppWidgetIds(ComponentName(context, cls))
        for (id in ids) {
            renderRoutineWidget(context, manager, id, prefs, fallback)
        }
    }
}

fun renderRoutineWidget(
    context: Context,
    manager: AppWidgetManager,
    widgetId: Int,
    prefs: SharedPreferences,
    fallbackRows: Int,
) {
    try {
        val views = RemoteViews(context.packageName, R.layout.routine_widget)
        openAppIntent(context)?.let { views.setOnClickPendingIntent(R.id.widget_root, it) }
        val raw = prefs.getString("classes_json", null)
        val today = prefs.getString("today_name", "") ?: ""
        val dayPref = prefs.getString("pref_day", "today") ?: "today"
        val chosen = if (dayPref.isBlank() || dayPref == "today") today else dayPref
        views.setTextViewText(R.id.day_title, if (chosen.isBlank()) "Today" else chosen)

        val classes = classesForDay(raw, chosen)
        val limit = rowLimit(manager, widgetId, fallbackRows)
        val shown = classes.take(limit)
        if (shown.isEmpty()) {
            views.setViewVisibility(R.id.empty_text, View.VISIBLE)
            views.setTextViewText(
                R.id.empty_text,
                if (raw.isNullOrBlank()) "অ্যাপে প্রবেশ করুন" else "এই দিনে কোনো ক্লাস নেই",
            )
        } else {
            views.setViewVisibility(R.id.empty_text, View.GONE)
        }
        val titleMode = prefs.getString("pref_title", "name") ?: "name"
        val showRoom = prefs.getBoolean("pref_room", true)
        val showTeacher = prefs.getBoolean("pref_teacher", false)
        val showPart = prefs.getBoolean("pref_part", true)
        widgetRows.forEachIndexed { index, row ->
            if (index >= shown.size) {
                views.setViewVisibility(row.row, View.GONE)
                return@forEachIndexed
            }
            val item = shown[index]
            views.setViewVisibility(row.row, View.VISIBLE)
            views.setViewVisibility(row.line, if (index == 0) View.GONE else View.VISIBLE)
            views.setTextViewText(row.start, item.optString("start"))
            views.setTextViewText(row.end, item.optString("end"))
            views.setTextViewText(row.title, classTitle(item, titleMode))
            views.setTextViewText(row.detail, classDetail(item, showRoom, showTeacher, showPart))
            views.setInt(row.bar, "setBackgroundColor", barColors[index % barColors.size])
        }
        val extra = classes.size - shown.size
        if (extra > 0) {
            views.setViewVisibility(R.id.more_text, View.VISIBLE)
            views.setTextViewText(R.id.more_text, "আরও ${extra}টি")
        } else {
            views.setViewVisibility(R.id.more_text, View.GONE)
        }
        manager.updateAppWidget(widgetId, views)
    } catch (_: Throwable) {
        try {
            val fallback = RemoteViews(context.packageName, R.layout.widget_fallback)
            manager.updateAppWidget(widgetId, fallback)
        } catch (_: Throwable) {
        }
    }
}

private fun classesForDay(raw: String?, chosen: String): List<JSONObject> {
    if (raw.isNullOrBlank()) return emptyList()
    val array = try {
        JSONArray(raw)
    } catch (_: Throwable) {
        return emptyList()
    }
    val items = mutableListOf<JSONObject>()
    for (index in 0 until array.length()) {
        val item = array.optJSONObject(index) ?: continue
        val day = item.optString("day")
        if (chosen.isNotBlank() && !day.equals(chosen, ignoreCase = true)) continue
        items.add(item)
    }
    return items
}

private fun classTitle(item: JSONObject, mode: String): String {
    val name = item.optString("name")
    val code = item.optString("code")
    return if (mode == "code") code.ifBlank { name } else name.ifBlank { code }
}

private fun classDetail(item: JSONObject, room: Boolean, teacher: Boolean, part: Boolean): String {
    val bits = mutableListOf<String>()
    if (room) item.optString("room").takeIf { it.isNotBlank() }?.let { bits.add(it) }
    if (teacher) item.optString("teacher").takeIf { it.isNotBlank() }?.let { bits.add(it) }
    if (part) {
        val value = item.optString("part")
        if (value.isNotBlank() && !value.equals("Full", ignoreCase = true)) bits.add(value)
    }
    return bits.joinToString(" - ")
}

private fun rowLimit(manager: AppWidgetManager, widgetId: Int, fallbackRows: Int): Int {
    val options = manager.getAppWidgetOptions(widgetId)
    val height = maxOf(
        options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0),
        options.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0),
    )
    if (height <= 0) return fallbackRows.coerceIn(1, widgetRows.size)
    val rows = (height - 46) / 54
    return rows.coerceIn(1, widgetRows.size)
}

private fun openAppIntent(context: Context): PendingIntent? {
    return try {
        val intent = Intent(context, MainActivity::class.java).apply {
            action = "es.antonborri.home_widget.action.LAUNCH"
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        var flags = PendingIntent.FLAG_UPDATE_CURRENT
        if (Build.VERSION.SDK_INT >= 23) {
            flags = flags or PendingIntent.FLAG_IMMUTABLE
        }
        PendingIntent.getActivity(context, 0, intent, flags)
    } catch (_: Throwable) {
        null
    }
}

open class RoutineWidgetProvider : HomeWidgetProvider() {
    open val fallbackRows: Int = 4

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
        widgetData: SharedPreferences,
    ) {
        appWidgetIds.forEach { widgetId ->
            renderRoutineWidget(context, appWidgetManager, widgetId, widgetData, fallbackRows)
        }
    }

    override fun onAppWidgetOptionsChanged(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int,
        newOptions: android.os.Bundle,
    ) {
        renderRoutineWidget(
            context,
            appWidgetManager,
            appWidgetId,
            HomeWidgetPlugin.getData(context),
            fallbackRows,
        )
    }
}

class RoutineWidgetSmall : RoutineWidgetProvider() {
    override val fallbackRows: Int = 2
}

class RoutineWidgetLarge : RoutineWidgetProvider() {
    override val fallbackRows: Int = 6
}
