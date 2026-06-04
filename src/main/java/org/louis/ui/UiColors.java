package org.louis.ui;

import com.googlecode.lanterna.TextColor;

public final class UiColors {

  public static final TextColor GREEN = new TextColor.RGB(76, 175, 80);
  public static final TextColor ORANGE = new TextColor.RGB(255, 152, 0);
  public static final TextColor RED = new TextColor.RGB(244, 67, 54);
  // Normal opacity (not "faded"): readable against light, dark, and tinted backgrounds.
  public static final TextColor DIM = new TextColor.RGB(200, 200, 200);
  public static final TextColor BLUE = new TextColor.RGB(92, 124, 250);
  public static final TextColor BRIGHT = new TextColor.RGB(255, 255, 255);

  private UiColors() {}
}
