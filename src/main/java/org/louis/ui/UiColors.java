package org.louis.ui;

import com.googlecode.lanterna.TextColor;

public final class UiColors {

  public static final TextColor GREEN = new TextColor.RGB(76, 175, 80); // ● ready
  public static final TextColor ORANGE = new TextColor.RGB(255, 152, 0); // soon
  public static final TextColor RED = new TextColor.RGB(244, 67, 54); // error / delete
  public static final TextColor DIM = TextColor.ANSI.WHITE; // countdown, dim labels (gray)
  public static final TextColor BLUE =
      new TextColor.RGB(92, 124, 250); // cursor ›, keys, breadcrumb
  public static final TextColor BRIGHT = TextColor.ANSI.WHITE_BRIGHT; // selected name, headings

  private UiColors() {}
}
