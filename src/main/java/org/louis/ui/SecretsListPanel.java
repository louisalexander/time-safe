package org.louis.ui;

import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

/**
 * Home screen: a list of secrets with a coloured countdown per row.
 *
 * <p>The list is a plain {@link Panel} containing one horizontal {@link Panel} per secret, each
 * holding three {@link Label}s (cursor, name, status). Arrow-key navigation is handled by the
 * window listener — no custom {@code InteractableRenderer} and no {@code ActionListBox}. This keeps
 * the visual model close to the spec's HTML mockup and lets {@link #refreshTimes()} just call
 * {@code setText} on the per-row status Labels instead of rebuilding the list every second.
 */
public class SecretsListPanel {

  private static final int NAME_WIDTH = 24;
  private static final int NAME_TRUNCATE_AT = 22;
  private static final int RIGHT_PAD_AFTER_NAME = 26;

  private final NavigationController nav;

  private Panel panel;
  private List<Secret> secrets = new ArrayList<>();
  private final List<Label> cursorLabels = new ArrayList<>();
  private final List<Label> nameLabels = new ArrayList<>();
  private final List<Label> statusLabels = new ArrayList<>();
  private int selectedIndex = 0;
  private Label statusLine;

  public SecretsListPanel(NavigationController nav) {
    this.nav = nav;
  }

  public Panel build() {
    panel = new Panel(new LinearLayout(Direction.VERTICAL));

    String header = nav.config() != null ? "Secrets — " + nav.config().githubRepo : "Secrets";
    panel.addComponent(UiComponents.sectionLabel(header));
    panel.addComponent(UiComponents.spacer());

    cursorLabels.clear();
    nameLabels.clear();
    statusLabels.clear();
    selectedIndex = 0;

    if (nav.vault() == null) {
      secrets = new ArrayList<>();
      panel.addComponent(UiComponents.dimLabel("No config found — press s to open Setup."));
    } else {
      secrets = new ArrayList<>(nav.vault().getSecrets());
      if (secrets.isEmpty()) {
        panel.addComponent(UiComponents.dimLabel("No secrets yet — press a to add one."));
      } else {
        for (int i = 0; i < secrets.size(); i++) {
          panel.addComponent(buildRow(i, secrets.get(i)));
        }
      }
    }

    statusLine = new Label("");
    panel.addComponent(statusLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.hintBar("↵", "open", "a", "add", "s", "setup", "q", "quit"));

    return panel;
  }

  public WindowListener buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.ArrowUp) {
          consumed.set(true);
          moveSelection(-1);
          return;
        }
        if (k.getKeyType() == KeyType.ArrowDown) {
          consumed.set(true);
          moveSelection(1);
          return;
        }
        if (k.getKeyType() == KeyType.Enter) {
          consumed.set(true);
          openSelected();
          return;
        }
        if (k.getCharacter() == null) return;
        switch (Character.toLowerCase(k.getCharacter())) {
          case 'a':
            if (nav.vault() != null) {
              consumed.set(true);
              new AddSecretPanel(nav).show();
            }
            break;
          case 's':
            consumed.set(true);
            new SetupPanel(nav).show();
            break;
          case 'q':
            consumed.set(true);
            nav.quit();
            break;
          default:
            break;
        }
      }
    };
  }

  /** Called by the countdown timer every second. Updates each row's status Label in place. */
  public void refreshTimes() {
    if (secrets.isEmpty()) return;
    for (int i = 0; i < secrets.size(); i++) {
      Secret s = secrets.get(i);
      statusLabels.get(i).setText(statusText(s));
      statusLabels.get(i).setForegroundColor(statusColor(s));
    }
  }

  /** Show a transient status message at the bottom of the list. */
  public void showStatus(String message, boolean isError) {
    if (statusLine == null) return;
    statusLine.setText(message);
    statusLine.setForegroundColor(isError ? UiColors.RED : UiColors.GREEN);
  }

  // ── Internals ────────────────────────────────────────────────────────────────

  private Panel buildRow(int index, Secret s) {
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));

    Label cursor = new Label(index == selectedIndex ? "›  " : "   ");
    cursor.setForegroundColor(UiColors.BLUE);
    cursorLabels.add(cursor);

    Label name = new Label(formatName(s.getName()));
    name.setForegroundColor(index == selectedIndex ? UiColors.BRIGHT : UiColors.DIM);
    nameLabels.add(name);

    Label status = new Label(statusText(s));
    status.setForegroundColor(statusColor(s));
    statusLabels.add(status);

    row.addComponent(cursor);
    row.addComponent(name);
    row.addComponent(status);
    return row;
  }

  private void moveSelection(int delta) {
    if (secrets.isEmpty()) return;
    int next = Math.max(0, Math.min(secrets.size() - 1, selectedIndex + delta));
    if (next == selectedIndex) return;
    cursorLabels.get(selectedIndex).setText("   ");
    nameLabels.get(selectedIndex).setForegroundColor(UiColors.DIM);
    selectedIndex = next;
    cursorLabels.get(selectedIndex).setText("›  ");
    nameLabels.get(selectedIndex).setForegroundColor(UiColors.BRIGHT);
  }

  private void openSelected() {
    if (secrets.isEmpty()) return;
    new SecretDetailPanel(nav, secrets.get(selectedIndex)).show();
  }

  private static String formatName(String raw) {
    String name = raw;
    if (name.length() > NAME_TRUNCATE_AT) {
      name = name.substring(0, NAME_TRUNCATE_AT - 2) + "..";
    }
    return String.format("%-" + (NAME_WIDTH + RIGHT_PAD_AFTER_NAME) + "s", name);
  }

  private static String statusText(Secret s) {
    return s.availableForDecryption() ? "● ready" : formatTimeRemaining(s.getDecryptionDate());
  }

  private static TextColor statusColor(Secret s) {
    if (s.availableForDecryption()) return UiColors.GREEN;
    long secs = ChronoUnit.SECONDS.between(Instant.now(), s.getDecryptionDate());
    return secs < 86400L ? UiColors.ORANGE : UiColors.DIM;
  }

  /**
   * Format the time remaining until {@code decryptionDate}. Package-private for testing. Returns "●
   * ready" when no time remains; otherwise the largest two units (days+hours, hours+minutes,
   * minutes+seconds, or just seconds).
   */
  static String formatTimeRemaining(Instant decryptionDate) {
    return formatTimeRemaining(Instant.now(), decryptionDate);
  }

  /** Same as {@link #formatTimeRemaining(Instant)} but with an injectable "now" for tests. */
  static String formatTimeRemaining(Instant now, Instant decryptionDate) {
    long total = ChronoUnit.SECONDS.between(now, decryptionDate);
    if (total <= 0) return "● ready";
    long days = total / 86400;
    long hours = (total % 86400) / 3600;
    long minutes = (total % 3600) / 60;
    long seconds = total % 60;
    if (days > 0) return days + "d " + hours + "h " + String.format("%02dm", minutes);
    if (hours > 0) return String.format("%dh %02dm %02ds", hours, minutes, seconds);
    if (minutes > 0) return String.format("%dm %02ds", minutes, seconds);
    return seconds + "s";
  }
}
