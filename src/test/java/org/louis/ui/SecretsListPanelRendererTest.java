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
