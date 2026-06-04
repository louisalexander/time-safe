package org.louis.ui;

import com.googlecode.lanterna.TerminalSize;
import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.gui2.ActionListBox;
import com.googlecode.lanterna.gui2.ComponentRenderer;
import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextGUIGraphics;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class SecretsListPanel {

  private final NavigationController nav;
  private Panel panel;
  private ActionListBox listBox;
  private List<Secret> cachedSecrets = new ArrayList<>();
  private Label statusLine;

  public SecretsListPanel(NavigationController nav) {
    this.nav = nav;
  }

  // Called by the window to display the panel for the first time.
  public Panel build() {
    panel = new Panel(new LinearLayout(Direction.VERTICAL));

    String repo = nav.config() != null ? "Secrets — " + nav.config().githubRepo : "Secrets";
    panel.addComponent(UiComponents.sectionLabel(repo));
    panel.addComponent(UiComponents.spacer());

    rebuildList();

    statusLine = new Label("");
    panel.addComponent(statusLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("↵ open   a add   s setup   q quit"));

    return panel;
  }

  public WindowListener buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
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

  /**
   * Called by the countdown timer every second. Updates the displayed time without rebuilding the
   * whole panel — just clears and re-adds items, preserving selection.
   */
  public void refreshTimes() {
    if (listBox == null || cachedSecrets.isEmpty()) return;
    int selected = listBox.getSelectedIndex();
    listBox.clearItems();
    for (Secret s : cachedSecrets) {
      listBox.addItem("", () -> openDetail(s));
    }
    if (selected >= 0 && selected < listBox.getItemCount()) {
      listBox.setSelectedIndex(selected);
    }
    // Invalidate so the renderer repaints
    listBox.invalidate();
  }

  /** Show a transient status message at the bottom of the list. */
  public void showStatus(String message, boolean isError) {
    if (statusLine == null) return;
    statusLine.setText(message);
    statusLine.setForegroundColor(isError ? UiColors.RED : UiColors.GREEN);
  }

  private void rebuildList() {
    listBox = null;
    cachedSecrets.clear();

    if (nav.vault() == null) {
      panel.addComponent(UiComponents.dimLabel("No config found — press s to open Setup."));
      return;
    }

    cachedSecrets = new ArrayList<>(nav.vault().getSecrets());

    if (cachedSecrets.isEmpty()) {
      panel.addComponent(UiComponents.dimLabel("No secrets yet — press a to add one."));
      return;
    }

    listBox = new ActionListBox();
    for (Secret s : cachedSecrets) {
      listBox.addItem("", () -> openDetail(s));
    }
    listBox.setRenderer(buildListRenderer());
    panel.addComponent(listBox);
  }

  private void openDetail(Secret s) {
    new SecretDetailPanel(nav, s).show();
  }

  private ComponentRenderer<ActionListBox> buildListRenderer() {
    List<Secret> secrets = cachedSecrets; // captured reference — same list mutated by refreshTimes
    return new ComponentRenderer<ActionListBox>() {
      @Override
      public TerminalSize getPreferredSize(ActionListBox component) {
        return new TerminalSize(70, Math.max(1, secrets.size()));
      }

      @Override
      public void drawComponent(TextGUIGraphics graphics, ActionListBox component) {
        TerminalSize size = component.getSize();
        int selectedIdx = component.getSelectedIndex();
        boolean focused = component.isFocused();

        for (int row = 0; row < Math.min(secrets.size(), size.getRows()); row++) {
          Secret s = secrets.get(row);
          boolean selected = row == selectedIdx;

          // Row background
          if (selected) {
            graphics.setBackgroundColor(
                focused ? new TextColor.RGB(25, 35, 65) : new TextColor.RGB(30, 30, 30));
          } else {
            graphics.setBackgroundColor(TextColor.ANSI.DEFAULT);
          }

          // Blank the row
          graphics.drawLine(0, row, size.getColumns() - 1, row, ' ');

          // Name column (28 chars)
          String name = s.getName();
          if (name.length() > 26) name = name.substring(0, 24) + "..";
          String paddedName = String.format("%-28s", name);
          graphics.setForegroundColor(selected ? UiColors.BRIGHT : TextColor.ANSI.WHITE);
          graphics.putString(0, row, paddedName);

          // Status column
          String statusText;
          TextColor statusColor;
          if (s.availableForDecryption()) {
            statusText = "● ready";
            statusColor = UiColors.GREEN;
          } else {
            long secs = ChronoUnit.SECONDS.between(Instant.now(), s.getDecryptionDate());
            statusText = formatTimeRemaining(s.getDecryptionDate());
            statusColor = secs < 86400L ? UiColors.ORANGE : UiColors.DIM;
          }
          graphics.setForegroundColor(statusColor);
          int statusCol = Math.min(30, Math.max(0, size.getColumns() - statusText.length() - 2));
          graphics.putString(statusCol, row, statusText);

          // Reset
          graphics.setBackgroundColor(TextColor.ANSI.DEFAULT);
          graphics.setForegroundColor(TextColor.ANSI.DEFAULT);
        }
      }
    };
  }

  private static String formatTimeRemaining(Instant decryptionDate) {
    long total = ChronoUnit.SECONDS.between(Instant.now(), decryptionDate);
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
