package org.louis.ui;

import com.googlecode.lanterna.TerminalSize;
import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.EmptySpace;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextBox;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

public final class UiComponents {

  private static final DateTimeFormatter DATE_FMT =
      DateTimeFormatter.ofPattern("yyyy-MM-dd").withZone(ZoneId.systemDefault());

  /** "‹ Parent" breadcrumb label in blue. */
  public static Label breadcrumb(String parentLabel) {
    Label l = new Label("‹ " + parentLabel);
    l.setForegroundColor(UiColors.BLUE);
    return l;
  }

  /** Dim section label (e.g. "Secrets — owner/repo"). */
  public static Label sectionLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.DIM);
    return l;
  }

  /** Plain dim label for hints and subtitles. */
  public static Label dimLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.DIM);
    return l;
  }

  /** Bright white label (headings, names). */
  public static Label brightLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.BRIGHT);
    return l;
  }

  /** Horizontal rule of em-dashes, given number of chars wide. */
  public static Label divider(int width) {
    return new Label("─".repeat(width));
  }

  /** Single-line text input. */
  public static TextBox singleLineInput(int width) {
    return new TextBox(new TerminalSize(width, 1));
  }

  /** Single-line password input (masked with *). */
  public static TextBox passwordInput(int width) {
    return new TextBox(new TerminalSize(width, 1)).setMask('*');
  }

  /** Multi-line text input. */
  public static TextBox multiLineInput(int width, int height) {
    return new TextBox(new TerminalSize(width, height), TextBox.Style.MULTI_LINE);
  }

  /** Format an Instant as yyyy-MM-dd in local time. */
  public static String formatDate(Instant instant) {
    return DATE_FMT.format(instant);
  }

  /** Compute the unlock date if locked for {@code days} from now. */
  public static String previewUnlockDate(int days) {
    return formatDate(Instant.now().plusSeconds((long) days * 86400));
  }

  /** Blank vertical spacer. */
  public static EmptySpace spacer() {
    return new EmptySpace(new TerminalSize(1, 1));
  }

  /** Build a simple two-column key/value row panel. */
  public static Panel fieldRow(String key, String value) {
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));
    Label keyLabel = new Label(String.format("%-12s", key));
    keyLabel.setForegroundColor(UiColors.DIM);
    Label valueLabel = new Label(value);
    row.addComponent(keyLabel);
    row.addComponent(valueLabel);
    return row;
  }

  private UiComponents() {}
}
