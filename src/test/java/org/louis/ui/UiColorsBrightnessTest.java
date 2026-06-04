package org.louis.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.googlecode.lanterna.TextColor;
import org.junit.Test;

/**
 * Locks in the spec palette: GREEN / ORANGE / RED / DIM / BLUE / BRIGHT. DIM and BRIGHT use ANSI
 * variants so the terminal renders them as gray / bright-white per its theme (the spec's intent).
 */
public class UiColorsBrightnessTest {

  @Test
  public void greenIsSpecValue() {
    assertEquals(new TextColor.RGB(76, 175, 80), UiColors.GREEN);
  }

  @Test
  public void orangeIsSpecValue() {
    assertEquals(new TextColor.RGB(255, 152, 0), UiColors.ORANGE);
  }

  @Test
  public void redIsSpecValue() {
    assertEquals(new TextColor.RGB(244, 67, 54), UiColors.RED);
  }

  @Test
  public void blueIsSpecValue() {
    assertEquals(new TextColor.RGB(92, 124, 250), UiColors.BLUE);
  }

  @Test
  public void dimIsAnsiWhite() {
    // ANSI.WHITE renders as gray on terminals that distinguish regular vs bright variants.
    assertEquals(TextColor.ANSI.WHITE, UiColors.DIM);
  }

  @Test
  public void brightIsAnsiWhiteBright() {
    // ANSI.WHITE_BRIGHT renders as the terminal's bright-white.
    assertEquals(TextColor.ANSI.WHITE_BRIGHT, UiColors.BRIGHT);
  }

  @Test
  public void dimIsDistinctFromBright() {
    // Without a real distinction here, the spec's DIM-vs-BRIGHT hierarchy collapses.
    assertTrue(
        "DIM and BRIGHT must be different colour constants", !UiColors.DIM.equals(UiColors.BRIGHT));
  }
}
