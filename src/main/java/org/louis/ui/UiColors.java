package org.louis.ui;

import com.googlecode.lanterna.TextColor;

public final class UiColors {

  public static final TextColor GREEN = new TextColor.RGB(76, 175, 80);
  public static final TextColor ORANGE = new TextColor.RGB(255, 152, 0);
  public static final TextColor RED = new TextColor.RGB(244, 67, 54);
  public static final TextColor DIM = new TextColor.RGB(140, 140, 140);
  public static final TextColor BLUE = new TextColor.RGB(92, 124, 250);
  public static final TextColor BRIGHT = new TextColor.RGB(235, 235, 235);
  // Theme-respecting "default" background: use ANSI.DEFAULT so the terminal keeps its own bg.
  public static final TextColor BG = TextColor.ANSI.DEFAULT;
  // Subtle blue tint used to mark the selected row.
  public static final TextColor BG_SELECTED = new TextColor.RGB(35, 50, 90);

  private UiColors() {}
}
