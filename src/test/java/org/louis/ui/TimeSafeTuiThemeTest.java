package org.louis.ui;

import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.Test;

/**
 * Locks in the rule that the Lanterna theme installed on the GUI uses {@code SGR.BOLD}. macOS
 * Terminal and many others gate "bright" foreground colour rendering on the bold attribute —
 * without it, even RGB(255,255,255) shows up as a muted tint on themed terminals (the dim
 * appearance the user repeatedly reported).
 */
public class TimeSafeTuiThemeTest {

  @Test
  public void guiThemeIncludesBoldStyle() throws IOException {
    String src = Files.readString(Path.of("src/main/java/org/louis/ui/TimeSafeTui.java"));
    // Match either the constructor form (new SimpleTheme(..., SGR.BOLD)) or any future helper —
    // as long as SGR.BOLD is wired into the gui.setTheme call site.
    int themeIdx = src.indexOf("gui.setTheme");
    assertTrue("TimeSafeTui must call gui.setTheme(...)", themeIdx > 0);
    int semi = src.indexOf(';', themeIdx);
    String themeCall = src.substring(themeIdx, semi);
    assertTrue(
        "gui.setTheme(...) must wire in SGR.BOLD so labels render at full brightness, was:\n"
            + themeCall,
        themeCall.contains("SGR.BOLD"));
  }
}
