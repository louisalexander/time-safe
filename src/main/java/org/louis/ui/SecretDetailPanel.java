package org.louis.ui;

import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class SecretDetailPanel {

  private final NavigationController nav;
  private final Secret secret;
  private Label errorLine;

  public SecretDetailPanel(NavigationController nav, Secret secret) {
    this.nav = nav;
    this.secret = secret;
  }

  public void show() {
    nav.push(buildPanel(), buildListener());
  }

  private Panel buildPanel() {
    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));

    panel.addComponent(UiComponents.breadcrumb("Secrets"));
    panel.addComponent(UiComponents.spacer());

    // Name + status
    panel.addComponent(UiComponents.brightLabel(secret.getName()));
    if (secret.availableForDecryption()) {
      Label statusLabel = new Label("● ready to decrypt");
      statusLabel.setForegroundColor(UiColors.GREEN);
      panel.addComponent(statusLabel);
    } else {
      Label statusLabel = new Label("locked — " + formatCountdown());
      statusLabel.setForegroundColor(UiColors.DIM);
      panel.addComponent(statusLabel);
    }

    panel.addComponent(UiComponents.spacer());

    // Metadata fields
    panel.addComponent(
        UiComponents.fieldRow("created", UiComponents.formatDate(secret.getCreatedAt())));
    panel.addComponent(
        UiComponents.fieldRow("unlocked", UiComponents.formatDate(secret.getDecryptionDate())));
    String shortId =
        secret.getId().length() > 8 ? secret.getId().substring(0, 8) + "…" : secret.getId();
    panel.addComponent(UiComponents.fieldRow("id", shortId));

    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.divider(40));
    panel.addComponent(UiComponents.spacer());

    // Action hints
    panel.addComponent(actionRow("d", "Decrypt", !secret.availableForDecryption()));
    panel.addComponent(actionRow("e", "Extend lock", false));
    panel.addComponent(actionRow("x", "Delete", false));

    // Inline error label (hidden initially)
    errorLine = new Label("");
    panel.addComponent(errorLine);

    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Esc back"));

    return panel;
  }

  private Panel actionRow(String key, String label, boolean disabled) {
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));
    Label keyLabel = new Label(key + "  ");
    keyLabel.setForegroundColor(disabled ? UiColors.DIM : UiColors.BLUE);
    Label actionLabel = new Label(label);
    if (disabled) {
      actionLabel.setForegroundColor(UiColors.DIM);
    } else if ("x".equals(key)) {
      actionLabel.setForegroundColor(UiColors.RED);
    }
    row.addComponent(keyLabel);
    row.addComponent(actionLabel);
    return row;
  }

  private WindowListenerAdapter buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop();
          return;
        }
        if (k.getCharacter() == null) return;
        switch (Character.toLowerCase(k.getCharacter())) {
          case 'd':
            consumed.set(true);
            if (secret.availableForDecryption()) {
              new DecryptPanel(nav, secret).show();
            } else {
              errorLine.setText(
                  "Not unlocked until " + UiComponents.formatDate(secret.getDecryptionDate()));
              errorLine.setForegroundColor(UiColors.RED);
            }
            break;
          case 'e':
            consumed.set(true);
            new ExtendLockPanel(nav, secret).show();
            break;
          case 'x':
            consumed.set(true);
            new DeletePanel(nav, secret).show();
            break;
          default:
            break;
        }
      }
    };
  }

  private String formatCountdown() {
    long total =
        java.time.temporal.ChronoUnit.SECONDS.between(
            java.time.Instant.now(), secret.getDecryptionDate());
    if (total <= 0) return "ready";
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
