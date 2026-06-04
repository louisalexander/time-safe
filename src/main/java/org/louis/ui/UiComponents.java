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

  /**
   * Section label (e.g. "Secrets — owner/repo"). Renders at the terminal's default foreground — no
   * dimming. Dimming is reserved for unselected list rows and low-urgency countdowns.
   */
  public static Label sectionLabel(String text) {
    return new Label(text);
  }

  /**
   * Plain label for hints, form sub-text, and instructions. Kept as {@code dimLabel} for API
   * compatibility; renders at the terminal's default foreground. (Historically rendered in DIM.)
   */
  public static Label dimLabel(String text) {
    return new Label(text);
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

  /**
   * Build a simple two-column key/value row panel. Both key and value render at the terminal's
   * default foreground — no dimming. The padding visually separates them.
   */
  public static Panel fieldRow(String key, String value) {
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));
    Label keyLabel = new Label(String.format("%-12s", key));
    Label valueLabel = new Label(value);
    row.addComponent(keyLabel);
    row.addComponent(valueLabel);
    return row;
  }

  /**
   * Build a horizontal hint bar: each pair of (key, description) renders as the key in BLUE
   * followed by the description in DIM. Pairs are separated by three spaces.
   *
   * <p>Example: {@code hintBar("↵", "open", "a", "add", "s", "setup", "q", "quit")}.
   */
  public static Panel hintBar(String... keyDescriptionPairs) {
    if ((keyDescriptionPairs.length & 1) != 0) {
      throw new IllegalArgumentException("hintBar requires an even number of arguments");
    }
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));
    for (int i = 0; i < keyDescriptionPairs.length; i += 2) {
      String key = keyDescriptionPairs[i];
      String description = keyDescriptionPairs[i + 1];
      Label keyLabel = new Label(key);
      keyLabel.setForegroundColor(UiColors.BLUE);
      // Descriptions render at the terminal's default foreground — no dimming.
      Label descLabel =
          new Label(" " + description + (i + 2 < keyDescriptionPairs.length ? "   " : ""));
      row.addComponent(keyLabel);
      row.addComponent(descLabel);
    }
    return row;
  }

  private UiComponents() {}
}
