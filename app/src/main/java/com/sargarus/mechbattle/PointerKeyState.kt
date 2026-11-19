package com.sargarus.mechbattle

/**
 * Holds one logical controller key while at least one touch pointer owns it.
 * Separate instances let the D-pad and A/B/C/Start stay independent.
 */
internal class PointerKeyState(
    private val onPressed: () -> Unit,
    private val onReleased: () -> Unit
) {
    private val pointerIds = mutableSetOf<Int>()

    val isPressed: Boolean
        get() = pointerIds.isNotEmpty()

    fun pointerDown(pointerId: Int) {
        if (pointerIds.add(pointerId) && pointerIds.size == 1) {
            onPressed()
        }
    }

    fun pointerUp(pointerId: Int) {
        if (pointerIds.remove(pointerId) && pointerIds.isEmpty()) {
            onReleased()
        }
    }

    fun cancel() {
        if (pointerIds.isNotEmpty()) {
            pointerIds.clear()
            onReleased()
        }
    }
}
