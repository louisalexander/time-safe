package org.louis.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.Test;

/**
 * Guards Step 3 of the Add Secret flow against re-introducing Ctrl+Enter as the submit gesture.
 * Ctrl+Enter doesn't pass through macOS Terminal by default — the Save Button + Tab navigation is
 * the cross-platform substitute. This is a source-text invariant rather than a behavioural one
 * because the step-3 panel is constructed inline inside a deeply-nested closure that is awkward to
 * exercise from a unit test.
 */
public class AddSecretPanelStep3Test {

  private static final Path SOURCE = Path.of("src/main/java/org/louis/ui/AddSecretPanel.java");

  @Test
  public void step3HasSaveButton() throws IOException {
    String src = Files.readString(SOURCE);
    assertTrue(
        "AddSecretPanel must build step 3 with `new Button(\"Save\", ...)`",
        src.contains("new Button(\n                    \"Save\",")
            || src.contains("new Button(\"Save\","));
  }

  @Test
  public void step3DoesNotRelyOnCtrlEnter() throws IOException {
    String src = Files.readString(SOURCE);
    // The literal user-facing hint must not advertise Ctrl+Enter, and the handler must not branch
    // on isCtrlDown(). Either would resurrect the macOS-broken keystroke.
    assertFalse(
        "Step 3 hint bar must not advertise Ctrl+Enter as the save gesture",
        src.contains("Ctrl+Enter save"));
    assertFalse(
        "Step 3 must not branch on isCtrlDown() — the Save button is the submit gesture",
        src.contains("isCtrlDown"));
  }

  @Test
  public void step3HintMentionsTabToSave() throws IOException {
    String src = Files.readString(SOURCE);
    assertTrue("Step 3 hint must teach the user the new gesture", src.contains("Tab to Save"));
  }
}
