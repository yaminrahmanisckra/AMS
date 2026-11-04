package xyz.kulawams.ams_routine

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import es.antonborri.home_widget.HomeWidgetPlugin

class WidgetSettingsActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val widgetId = intent?.extras?.getInt(
            AppWidgetManager.EXTRA_APPWIDGET_ID,
            AppWidgetManager.INVALID_APPWIDGET_ID,
        ) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        val result = Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId)
        setResult(RESULT_CANCELED, result)
        if (widgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish()
            return
        }

        val prefs = HomeWidgetPlugin.getData(this)
        val days = listOf(
            "today" to "আজ",
            "Sunday" to "রবিবার",
            "Monday" to "সোমবার",
            "Tuesday" to "মঙ্গলবার",
            "Wednesday" to "বুধবার",
            "Thursday" to "বৃহস্পতিবার",
            "Friday" to "শুক্রবার",
            "Saturday" to "শনিবার",
        )
        val currentDay = prefs.getString("pref_day", "today") ?: "today"
        val titleMode = prefs.getString("pref_title", "name") ?: "name"

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = dp(20)
            setPadding(pad, pad, pad, pad)
        }
        root.addView(label("উইজেটে যা দেখাবেন", 18f, true))
        root.addView(label("দিন", 14f, false))
        val spinner = Spinner(this)
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, days.map { it.second })
        spinner.setSelection(days.indexOfFirst { it.first == currentDay }.coerceAtLeast(0))
        root.addView(spinner)

        root.addView(label("শিরোনাম", 14f, false))
        val nameButton = RadioButton(this).apply { text = "কোর্সের নাম"; id = View.generateViewId() }
        val codeButton = RadioButton(this).apply { text = "কোর্স কোড"; id = View.generateViewId() }
        val titleGroup = RadioGroup(this).apply {
            addView(nameButton)
            addView(codeButton)
            check(if (titleMode == "code") codeButton.id else nameButton.id)
        }
        root.addView(titleGroup)

        val roomBox = CheckBox(this).apply {
            text = "রুম"
            isChecked = prefs.getBoolean("pref_room", true)
        }
        val teacherBox = CheckBox(this).apply {
            text = "শিক্ষক"
            isChecked = prefs.getBoolean("pref_teacher", false)
        }
        val partBox = CheckBox(this).apply {
            text = "পার্ট"
            isChecked = prefs.getBoolean("pref_part", true)
        }
        root.addView(roomBox)
        root.addView(teacherBox)
        root.addView(partBox)

        val save = Button(this).apply { text = "রাখুন" }
        save.setOnClickListener {
            prefs.edit()
                .putString("pref_day", days[spinner.selectedItemPosition].first)
                .putString("pref_title", if (titleGroup.checkedRadioButtonId == codeButton.id) "code" else "name")
                .putBoolean("pref_room", roomBox.isChecked)
                .putBoolean("pref_teacher", teacherBox.isChecked)
                .putBoolean("pref_part", partBox.isChecked)
                .commit()
            updateRoutineWidgets(this)
            setResult(RESULT_OK, result)
            finish()
        }
        root.addView(save)
        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun label(text: String, size: Float, bold: Boolean): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = size
            if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(0, dp(8), 0, dp(4))
        }
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).toInt()
    }
}
