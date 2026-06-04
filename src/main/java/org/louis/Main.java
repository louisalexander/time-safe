package org.louis;

import org.louis.ui.TimeSafeTui;

public class Main {

  public static void main(String[] args) {
    Log.info("─── TimeSafe starting ───────────────────────────────────────────");
    try {
      new TimeSafeTui().run();
      Log.info("TimeSafe exited normally");
    } catch (Exception e) {
      Log.error("Fatal error", e);
    }
  }
}
