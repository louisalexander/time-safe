package org.louis.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.Test;

/**
 * Guards the invariant that the secrets-list renderer never sets a background color. Claude Code's
 * minimal aesthetic has no row background tint — only the "›" cursor and the BRIGHT/DIM foreground
 * contrast mark the selection. A regression here means our list will paint over the user's terminal
 * theme.
 *
 * <p>This is a source-text assertion rather than a behavioural one because {@link
 * com.googlecode.lanterna.gui2.TextGUIGraphics} is a 50+ method interface that's prohibitively
 * verbose to mock. The renderer is short enough that grepping its source is reliable.
 */
public class SecretsListPanelRendererTest {

  private static final Path SOURCE = Path.of("src/main/java/org/louis/ui/SecretsListPanel.java");

  @Test
  public void rendererSourceNeverSetsBackgroundColor() throws IOException {
    String source = readSource();
    String renderer = extractRendererBlock(source);

    Pattern p = Pattern.compile("graphics\\.setBackgroundColor\\s*\\(");
    Matcher m = p.matcher(renderer);
    if (m.find()) {
      fail(
          "buildListRenderer() must not call graphics.setBackgroundColor — "
              + "the terminal's own background should show through. Found call at offset "
              + m.start()
              + " in the renderer block.");
    }
  }

  @Test
  public void rendererSourceUsesCursorPrefix() throws IOException {
    String source = readSource();
    String renderer = extractRendererBlock(source);
    // U+203A SINGLE RIGHT-POINTING ANGLE QUOTATION MARK — used as the cursor on the selected row.
    String chevron = "›";
    assertTrue(
        "Renderer should draw the \"" + chevron + "\" cursor prefix for the selected row",
        renderer.contains(chevron));
  }

  @Test
  public void rendererClearsInheritedModifiers() throws IOException {
    String source = readSource();
    String renderer = extractRendererBlock(source);
    // Without clearModifiers(), an ambient bold/faint from the parent component's theme can
    // leak in and tint the renderer's text, producing the "dim" look the user reported.
    assertTrue(
        "Renderer must call graphics.clearModifiers() before drawing",
        renderer.contains("clearModifiers"));
  }

  @Test
  public void rendererEnablesBoldForBrightColorRendering() throws IOException {
    String renderer = extractRendererBlock(readSource());
    // macOS Terminal (and many others) selects between "regular" and "bright" colour variants
    // based on the bold attribute. Without BOLD, even RGB(255,255,255) renders as a muted hue.
    assertTrue(
        "Renderer must enable SGR.BOLD so terminal colours render at full brightness",
        renderer.contains("enableModifiers(SGR.BOLD)"));
  }

  @Test
  public void rendererNeverFallsBackToAnsiDefaultForeground() throws IOException {
    // Setting foreground to ANSI.DEFAULT tells the terminal "use your default foreground", which
    // renders as a muted hue on tinted themes — the source of the user's "dim" complaint.
    // Every foreground must be an explicit colour (BLUE / BRIGHT / GREEN / ORANGE / RED).
    String renderer = extractRendererBlock(readSource());
    assertFalse(
        "Renderer must not use TextColor.ANSI.DEFAULT as a foreground colour. Use an explicit "
            + "UiColors.* value instead.",
        renderer.matches(
            "(?s).*setForegroundColor\\s*\\(\\s*TextColor\\s*\\.\\s*ANSI\\s*\\.\\s*DEFAULT.*"));
  }

  @Test
  public void noBackgroundConstantsLingerInUiColors() throws IOException {
    String src = Files.readString(Path.of("src/main/java/org/louis/ui/UiColors.java"));
    // We do not expose BG / BG_SELECTED constants — those would tempt re-introducing the tint.
    assertFalse(
        "UiColors must not expose BG_SELECTED — selection is conveyed by foreground only",
        src.contains("BG_SELECTED"));
    assertFalse(
        "UiColors must not expose BG",
        src.matches("(?s).*\\bpublic static final TextColor BG\\b.*"));
  }

  @Test
  public void dimIsNeverUsedAndUiColorsDoesNotExposeIt() throws IOException {
    // Dimming has been eliminated everywhere. The UiColors palette must not expose a DIM constant,
    // and no source file may reference UiColors.DIM. Selection contrast is conveyed by the BLUE
    // "›" cursor + BRIGHT name on the selected row, and by the terminal default on other rows.
    Path[] uiSources = {
      Path.of("src/main/java/org/louis/ui/UiColors.java"),
      Path.of("src/main/java/org/louis/ui/UiComponents.java"),
      Path.of("src/main/java/org/louis/ui/SecretsListPanel.java"),
      Path.of("src/main/java/org/louis/ui/SecretDetailPanel.java"),
      Path.of("src/main/java/org/louis/ui/DecryptPanel.java"),
      Path.of("src/main/java/org/louis/ui/ExtendLockPanel.java"),
      Path.of("src/main/java/org/louis/ui/DeletePanel.java"),
      Path.of("src/main/java/org/louis/ui/AddSecretPanel.java"),
      Path.of("src/main/java/org/louis/ui/SetupPanel.java"),
      Path.of("src/main/java/org/louis/ui/TimeSafeTui.java"),
    };
    for (Path p : uiSources) {
      String src = Files.readString(p);
      assertFalse(
          p.getFileName() + " must not reference UiColors.DIM — dimming has been eliminated",
          src.contains("UiColors.DIM"));
    }

    String palette = Files.readString(Path.of("src/main/java/org/louis/ui/UiColors.java"));
    assertFalse(
        "UiColors must not expose a DIM constant",
        palette.matches("(?s).*\\bpublic static final TextColor DIM\\b.*"));
  }

  private String readSource() throws IOException {
    if (!Files.exists(SOURCE)) {
      fail("Source file not found: " + SOURCE.toAbsolutePath());
    }
    return Files.readString(SOURCE);
  }

  /** Extract the body of buildListRenderer() so we don't accidentally match unrelated calls. */
  private String extractRendererBlock(String source) {
    // Match the method *definition*, not the call site.
    int start = source.indexOf("InteractableRenderer<ActionListBox> buildListRenderer()");
    assertTrue("buildListRenderer method definition must exist", start > 0);
    int braceStart = source.indexOf('{', start);
    assertTrue(braceStart > 0);
    int depth = 0;
    int i = braceStart;
    for (; i < source.length(); i++) {
      char c = source.charAt(i);
      if (c == '{') depth++;
      else if (c == '}') {
        depth--;
        if (depth == 0) {
          return source.substring(braceStart, i + 1);
        }
      }
    }
    fail("Could not find matching close brace for buildListRenderer()");
    return ""; // unreachable
  }
}
