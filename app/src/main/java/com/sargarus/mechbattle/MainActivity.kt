package com.sargarus.mechbattle

import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.swordfish.libretrodroid.GLRetroView
import com.swordfish.libretrodroid.GLRetroViewData
import com.swordfish.libretrodroid.ShaderConfig
import java.io.File

class MainActivity : AppCompatActivity() {
    private lateinit var root: FrameLayout
    private var retroView: GLRetroView? = null
    private var touchOverlay: TouchOverlayView? = null
    private lateinit var hint: TextView
    private val romPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) launchRom(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor=Color.BLACK
        window.navigationBarColor=Color.BLACK
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility=View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        root=FrameLayout(this).apply{setBackgroundColor(Color.BLACK)}
        hint=TextView(this).apply{
            text="MECH BATTLE MOBILE\n\nВыбери ROM-файл Sega Genesis / Mega Drive"
            setTextColor(Color.WHITE);textSize=20f;gravity=Gravity.CENTER
        }
        root.addView(hint,FrameLayout.LayoutParams(-1,-1))
        val choose=TextView(this).apply{
            text="ВЫБРАТЬ ИГРУ";textSize=13f;setTextColor(Color.WHITE);gravity=Gravity.CENTER
            setPadding(28,16,28,16);setBackgroundColor(0xCC263238.toInt())
            setOnClickListener{romPicker.launch(arrayOf("*/*"))}
        }
        root.addView(choose,FrameLayout.LayoutParams(-2,-2,Gravity.CENTER).apply{topMargin=104})
        setContentView(root)
    }

    private fun launchRom(uri:Uri) {
        try {
            val rom=File(filesDir,"selected_game.bin")
            contentResolver.openInputStream(uri).use{input->requireNotNull(input){"Не удалось открыть ROM"}.copyTo(rom.outputStream())}
            retroView?.let{lifecycle.removeObserver(it)}
            root.removeAllViews()
            val data=GLRetroViewData(this).apply{
                coreFilePath="libpicodrive_libretro_android.so";gameFilePath=rom.absolutePath
                systemDirectory=filesDir.absolutePath;savesDirectory=File(filesDir,"saves").apply{mkdirs()}.absolutePath
                shader=ShaderConfig.Default;preferLowLatencyAudio=true
            }
            val view=GLRetroView(this,data);retroView=view
            root.addView(view,FrameLayout.LayoutParams(-1,-1));lifecycle.addObserver(view)
            val overlay=TouchOverlayView(this,{action,key->view.sendKeyEvent(action,key)},{action->
                when(action){"ROM"->romPicker.launch(arrayOf("*/*"));"SAVE"->saveState();"LOAD"->loadState()}
            })
            touchOverlay=overlay;root.addView(overlay,FrameLayout.LayoutParams(-1,-1))
        } catch(e:Exception) {
            hint.text="Не удалось открыть игру: ${e.message}"
            root.removeAllViews();root.addView(hint,FrameLayout.LayoutParams(-1,-1))
        }
    }

    private fun saveState(){try{val bytes=retroView?.serializeState()?:return;File(filesDir,"slot1.state").writeBytes(bytes)}catch(_:Exception){}}
    private fun loadState(){try{val f=File(filesDir,"slot1.state");if(f.exists())retroView?.unserializeState(f.readBytes())}catch(_:Exception){}}
    override fun onPause(){
        touchOverlay?.cancelAll()
        try{retroView?.let{File(filesDir,"save.srm").writeBytes(it.serializeSRAM())}}catch(_:Exception){}
        super.onPause()
    }
    override fun onDestroy(){touchOverlay?.cancelAll();retroView?.let{lifecycle.removeObserver(it)};super.onDestroy()}
}
