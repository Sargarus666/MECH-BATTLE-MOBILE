package com.sargarus.mechbattle

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.swordfish.libretrodroid.GLRetroView
import com.swordfish.libretrodroid.GLRetroViewData
import com.swordfish.libretrodroid.ShaderConfig
import kotlinx.coroutines.launch
import java.io.File

class MainActivity : AppCompatActivity() {
    private lateinit var root: FrameLayout
    private var retroView: GLRetroView? = null
    private lateinit var hint: TextView

    private val romPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) launchRom(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE

        root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        hint = TextView(this).apply {
            text = "MECH BATTLE MOBILE\n\nВыбери ROM-файл Sega Genesis / Mega Drive"
            setTextColor(Color.WHITE)
            textSize = 20f
            gravity = Gravity.CENTER
        }
        root.addView(hint, FrameLayout.LayoutParams(-1, -1))
        val choose = makeButton("ВЫБРАТЬ ИГРУ") {
            romPicker.launch(arrayOf("*/*"))
        }
        root.addView(choose, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
        setContentView(root)
    }

    private fun launchRom(uri: Uri) {
        try {
            val rom = File(filesDir, "selected_game.bin")
            contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input) { "Не удалось открыть ROM" }.copyTo(rom.outputStream())
            }
            retroView?.let { lifecycle.removeObserver(it); root.removeView(it) }
            val data = GLRetroViewData(this).apply {
                coreFilePath = "libpicodrive_libretro_android.so"
                gameFilePath = rom.absolutePath
                systemDirectory = filesDir.absolutePath
                savesDirectory = File(filesDir, "saves").apply { mkdirs() }.absolutePath
                shader = ShaderConfig.Default
                preferLowLatencyAudio = true
            }
            val view = GLRetroView(this, data)
            retroView = view
            root.removeAllViews()
            root.addView(view, FrameLayout.LayoutParams(-1, -1))
            lifecycle.addObserver(view)
            addOverlayControls()
        } catch (e: Exception) {
            hint.text = "Не удалось открыть игру: ${e.message}"
            root.removeAllViews()
            root.addView(hint, FrameLayout.LayoutParams(-1, -1))
        }
    }

    private fun addOverlayControls() {
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val pick = makeButton("ROM") { romPicker.launch(arrayOf("*/*")) }
        val save = makeButton("SAVE") { saveState() }
        val load = makeButton("LOAD") { loadState() }
        top.addView(pick); top.addView(save); top.addView(load)
        root.addView(top, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.CENTER_HORIZONTAL))

        val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        val up = padButton("▲", 4); val mid = LinearLayout(this).apply { gravity = Gravity.CENTER }
        val down = padButton("▼", 5)
        mid.addView(padButton("◀", 6)); mid.addView(TextView(this).apply { text = " "; width = 42 }); mid.addView(padButton("▶", 7))
        left.addView(up); left.addView(mid); left.addView(down)
        root.addView(left, FrameLayout.LayoutParams(-2, -2, Gravity.START or Gravity.BOTTOM).apply { leftMargin = 16; bottomMargin = 12 })

        val right = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        val row1 = LinearLayout(this).apply { gravity = Gravity.CENTER }
        row1.addView(padButton("B", 0)); row1.addView(padButton("C", 1))
        val row2 = LinearLayout(this).apply { gravity = Gravity.CENTER }
        row2.addView(padButton("A", 8)); row2.addView(padButton("START", 3))
        right.addView(row1); right.addView(row2)
        root.addView(right, FrameLayout.LayoutParams(-2, -2, Gravity.END or Gravity.BOTTOM).apply { rightMargin = 14; bottomMargin = 12 })
    }

    private fun padButton(label: String, key: Int): Button {
        val keyState = PointerKeyState(
            onPressed = { retroView?.sendKeyEvent(android.view.KeyEvent.ACTION_DOWN, key) },
            onReleased = { retroView?.sendKeyEvent(android.view.KeyEvent.ACTION_UP, key) }
        )
        return makeButton(label) {}.apply {
            setOnTouchListener { view, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN ->
                        keyState.pointerDown(event.getPointerId(event.actionIndex))
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP ->
                        keyState.pointerUp(event.getPointerId(event.actionIndex))
                    MotionEvent.ACTION_CANCEL -> keyState.cancel()
                }
                view.isPressed = keyState.isPressed
                true
            }
        }
    }

    private fun makeButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 12f
            alpha = 0.78f
            setTextColor(Color.WHITE)
            setBackgroundColor(0xCC263238.toInt())
            setPadding(10, 4, 10, 4)
            setOnClickListener { action() }
        }

    private fun saveState() {
        try {
            val bytes = retroView?.serializeState() ?: return
            File(filesDir, "slot1.state").writeBytes(bytes)
        } catch (_: Exception) { }
    }

    private fun loadState() {
        try {
            val file = File(filesDir, "slot1.state")
            if (file.exists()) retroView?.unserializeState(file.readBytes())
        } catch (_: Exception) { }
    }

    override fun onPause() {
        try {
            retroView?.let { File(filesDir, "save.srm").writeBytes(it.serializeSRAM()) }
        } catch (_: Exception) { }
        super.onPause()
    }

    override fun onDestroy() {
        retroView?.let { lifecycle.removeObserver(it) }
        super.onDestroy()
    }
}
