package com.sargarus.mechbattle

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PointerKeyStateTest {
    @Test
    fun keyStaysDownUntilTheLastPointerIsReleased() {
        val events = mutableListOf<String>()
        val state = PointerKeyState(
            onPressed = { events += "down" },
            onReleased = { events += "up" }
        )

        state.pointerDown(3)
        state.pointerDown(9)
        state.pointerUp(3)

        assertEquals(listOf("down"), events)
        assertTrue(state.isPressed)

        state.pointerUp(9)
        assertEquals(listOf("down", "up"), events)
        assertFalse(state.isPressed)
    }

    @Test
    fun duplicateDownAndUnknownPointerUpAreIgnored() {
        val events = mutableListOf<String>()
        val state = PointerKeyState(
            onPressed = { events += "down" },
            onReleased = { events += "up" }
        )

        state.pointerDown(4)
        state.pointerDown(4)
        state.pointerUp(12)
        state.pointerUp(4)

        assertEquals(listOf("down", "up"), events)
    }

    @Test
    fun cancelReleasesOnceAndClearsEveryPointer() {
        val events = mutableListOf<String>()
        val state = PointerKeyState(
            onPressed = { events += "down" },
            onReleased = { events += "up" }
        )

        state.pointerDown(1)
        state.pointerDown(2)
        state.cancel()
        state.cancel()

        assertEquals(listOf("down", "up"), events)
        assertFalse(state.isPressed)
    }

    @Test
    fun separateControlsCanBeHeldAtTheSameTime() {
        val dpadEvents = mutableListOf<String>()
        val weaponEvents = mutableListOf<String>()
        val dpad = PointerKeyState(
            onPressed = { dpadEvents += "down" },
            onReleased = { dpadEvents += "up" }
        )
        val weapon = PointerKeyState(
            onPressed = { weaponEvents += "down" },
            onReleased = { weaponEvents += "up" }
        )

        dpad.pointerDown(7)
        weapon.pointerDown(8)
        dpad.pointerUp(7)

        assertEquals(listOf("down", "up"), dpadEvents)
        assertEquals(listOf("down"), weaponEvents)
        assertTrue(weapon.isPressed)
    }
}
