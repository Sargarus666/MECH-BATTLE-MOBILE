package com.sargarus.mechbattle

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.view.MotionEvent
import android.view.View
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.min

/** Native translucent controller. Each pointer independently owns one or more keys. */
class TouchOverlayView(
    context: Context,
    private val onKeyEvent: (Int, Int) -> Unit,
    private val onAction: (String) -> Unit
) : View(context) {
    private val d = resources.displayMetrics.density
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    private val pointerKeys = mutableMapOf<Int, MutableSet<Int>>()
    private val pointerActions = mutableMapOf<Int, String>()
    private val states = mutableMapOf<Int, PointerKeyState>()
    private val actions = linkedMapOf<String, RectF>()
    private val buttons = linkedMapOf(8 to Pair(.755f,.815f), 0 to Pair(.855f,.690f), 1 to Pair(.935f,.805f))
    private val labels = mapOf(8 to "A", 0 to "B", 1 to "C")
    private val br get() = min(width*.047f,height*.105f)
    private val dr get() = min(width*.145f,height*.285f)
    private val dcx get() = width*.165f
    private val dcy get() = height*.765f
    private val start get() = RectF(width*.865f,height*.905f,width*.985f,height*.985f)

    init { isClickable = true }

    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        if (width == 0 || height == 0) return
        actions.clear()
        listOf("ROM","SAVE","LOAD").forEachIndexed { i, label ->
            val w=54f*d; val h=30f*d; val l=width*.035f+i*(w+7f*d)
            val r=RectF(l,height*.035f,l+w,height*.035f+h); actions[label]=r
            capsule(c,r,label,false,true)
        }
        p.style=Paint.Style.FILL
        p.color=if(listOf(4,5,6,7).any(::pressed)) Color.argb(110,95,175,210) else Color.argb(70,150,195,220)
        c.drawCircle(dcx,dcy,dr*1.1f,p)
        p.style=Paint.Style.STROKE; p.strokeWidth=1.5f*d; p.color=Color.argb(190,250,253,255)
        c.drawCircle(dcx,dcy,dr*1.1f,p)
        p.style=Paint.Style.FILL; p.color=Color.argb(65,255,255,255)
        c.drawRoundRect(dcx-dr*.23f,dcy-dr*.82f,dcx+dr*.23f,dcy+dr*.82f,dr*.16f,dr*.16f,p)
        c.drawRoundRect(dcx-dr*.82f,dcy-dr*.23f,dcx+dr*.82f,dcy+dr*.23f,dr*.16f,dr*.16f,p)
        p.color=Color.argb(170,255,255,255); c.drawCircle(dcx,dcy,dr*.18f,p)
        buttons.forEach { (key,xy) -> circleButton(c,width*xy.first,height*xy.second,br,labels.getValue(key),pressed(key)) }
        capsule(c,start,"START",pressed(3))
    }

    private fun circleButton(c:Canvas,x:Float,y:Float,r:Float,label:String,down:Boolean) {
        p.style=Paint.Style.FILL; p.color=if(down) Color.argb(165,80,175,225) else Color.argb(82,165,205,230)
        c.drawCircle(x,y,r,p); p.style=Paint.Style.STROKE; p.strokeWidth=1.6f*d
        p.color=Color.argb(210,250,253,255); c.drawCircle(x,y,r,p)
        p.style=Paint.Style.FILL; p.color=Color.WHITE; p.textAlign=Paint.Align.CENTER
        p.textSize=r*.82f; p.typeface=android.graphics.Typeface.create("sans-serif-medium",1)
        c.drawText(label,x,y+r*.29f,p)
    }

    private fun capsule(c:Canvas,r:RectF,label:String,down:Boolean,small:Boolean=false) {
        p.style=Paint.Style.FILL; p.color=if(down) Color.argb(150,80,175,225) else Color.argb(76,20,32,43)
        c.drawRoundRect(r,r.height()/2,r.height()/2,p); p.style=Paint.Style.STROKE
        p.strokeWidth=1.2f*d; p.color=Color.argb(180,245,250,255); c.drawRoundRect(r,r.height()/2,r.height()/2,p)
        p.style=Paint.Style.FILL; p.color=Color.WHITE; p.textAlign=Paint.Align.CENTER
        p.textSize=if(small) 10f*d else 11f*d; p.typeface=android.graphics.Typeface.create("sans-serif-medium",1)
        c.drawText(label,r.centerX(),r.centerY()-(p.ascent()+p.descent())/2,p)
    }

    override fun onTouchEvent(e:MotionEvent):Boolean {
        when(e.actionMasked) {
            MotionEvent.ACTION_DOWN,MotionEvent.ACTION_POINTER_DOWN,MotionEvent.ACTION_MOVE ->
                for(i in 0 until e.pointerCount) update(e.getPointerId(i),e.getX(i),e.getY(i))
            MotionEvent.ACTION_POINTER_UP,MotionEvent.ACTION_UP -> {
                val n=e.actionIndex; release(e.getPointerId(n))
                for(i in 0 until e.pointerCount) if(i!=n) update(e.getPointerId(i),e.getX(i),e.getY(i))
                if(e.actionMasked==MotionEvent.ACTION_UP) performClick()
            }
            MotionEvent.ACTION_CANCEL -> cancelAll()
        }
        invalidate(); return true
    }

    private fun update(id:Int,x:Float,y:Float) {
        val action=actions.entries.firstOrNull{it.value.contains(x,y)}?.key
        if(action!=null) { releaseKeys(id); pointerActions[id]=action; return }
        pointerActions.remove(id)
        val next=keysAt(x,y); val old=pointerKeys[id].orEmpty()
        (old-next).forEach{states[it]?.pointerUp(id)}
        (next-old).forEach{key->state(key).pointerDown(id)}
        if(next.isEmpty()) pointerKeys.remove(id) else pointerKeys[id]=next.toMutableSet()
    }

    private fun keysAt(x:Float,y:Float):Set<Int> {
        val out=linkedSetOf<Int>(); val dx=x-dcx; val dy=y-dcy
        if(hypot(dx,dy)<=dr*1.12f) {
            val nx=dx/dr; val ny=dy/dr
            if(abs(nx)>.34f) out+=if(nx<0) 6 else 7
            if(abs(ny)>.34f) out+=if(ny<0) 4 else 5
            return out
        }
        buttons.forEach{(key,xy)->if(hypot(x-width*xy.first,y-height*xy.second)<=br*1.22f)out+=key}
        if(start.contains(x,y))out+=3
        return out
    }

    private fun state(key:Int)=states.getOrPut(key){
        PointerKeyState({onKeyEvent(MotionEvent.ACTION_DOWN,key)},{onKeyEvent(MotionEvent.ACTION_UP,key)})
    }
    private fun pressed(key:Int)=states[key]?.isPressed==true
    private fun releaseKeys(id:Int){pointerKeys.remove(id)?.forEach{states[it]?.pointerUp(id)}}
    private fun release(id:Int){releaseKeys(id);pointerActions.remove(id)?.let(onAction)}
    fun cancelAll(){pointerKeys.keys.toList().forEach(::releaseKeys);pointerActions.clear();states.values.forEach{it.cancel()};invalidate()}
    override fun performClick():Boolean{super.performClick();return true}
    override fun onDetachedFromWindow(){cancelAll();super.onDetachedFromWindow()}
}
