package org.louis.ui;

import static org.junit.Assert.assertTrue;

import com.googlecode.lanterna.TextColor;
import org.junit.Test;

/**
 * Locks in a minimum brightness for foreground colors so the UI doesn't regress to a "faded" look
 * on non-black terminal backgrounds. The minimums come from in-vivo testing against macOS
 * Terminal's default and a blue-tinted theme.
 */
public class UiColorsBrightnessTest {

  private static final int BRIGHT_MIN_BRIGHTNESS = 240;
  // Perceived brightness uses luminance weights — blue channel only contributes 0.114, so even a
  // saturated mid-blue lands around 130. The spec's RGB(92,124,250) measures ~129.
  private static final int BLUE_MIN_BRIGHTNESS = 120;

  @Test
  public void brightIsBrightEnough() {
    assertAverageChannelAtLeast("BRIGHT", UiColors.BRIGHT, BRIGHT_MIN_BRIGHTNESS);
  }

  @Test
  public void blueCursorIsVisibleAgainstDarkAndTintedBackgrounds() {
    int b = perceivedBrightness(UiColors.BLUE);
    assertTrue(
        "BLUE perceived brightness must be ≥ " + BLUE_MIN_BRIGHTNESS + ", was " + b,
        b >= BLUE_MIN_BRIGHTNESS);
  }

  // ── helpers ──────────────────────────────────────────────────────────────────

  private static void assertAverageChannelAtLeast(String name, TextColor color, int minAvg) {
    int b = averageChannel(color);
    assertTrue(name + " average channel must be ≥ " + minAvg + ", was " + b, b >= minAvg);
  }

  /** Mean of R,G,B. Returns 0 for non-RGB colors so the ANSI sentinel triggers the assertion. */
  private static int averageChannel(TextColor color) {
    if (color instanceof TextColor.RGB rgb) {
      return (rgb.getRed() + rgb.getGreen() + rgb.getBlue()) / 3;
    }
    return 0;
  }

  /** Perceived (luminance-weighted) brightness — handles the eye's higher sensitivity to green. */
  private static int perceivedBrightness(TextColor color) {
    if (color instanceof TextColor.RGB rgb) {
      return (int)
          Math.round(0.299 * rgb.getRed() + 0.587 * rgb.getGreen() + 0.114 * rgb.getBlue());
    }
    return 0;
  }
}
