package org.louis.ui;

import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextBox;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class ExtendLockPanel {

  private final NavigationController nav;
  private final Secret secret;

  public ExtendLockPanel(NavigationController nav, Secret secret) {
    this.nav = nav;
    this.secret = secret;
  }

  public void show() {
    nav.push(buildPanel(), buildListener());
  }

  private Panel buildPanel() {
    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb(secret.getName()));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Additional days to lock"));

    TextBox daysBox = UiComponents.singleLineInput(10);
    daysBox.setText("30");

    // Live preview label
    Label previewLabel = new Label("Unlocks on " + computePreview(30));
    previewLabel.setForegroundColor(UiColors.DIM);

    // Error label
    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    // Filter: only allow digits; update preview on each keystroke
    daysBox.setInputFilter(
        (interactable, keyStroke) -> {
          if (keyStroke.getKeyType() == KeyType.Enter) {
            handleExtend(daysBox.getText().trim(), errorLine);
            return false;
          }
          // Allow only digits, backspace, delete
          if (keyStroke.getKeyType() == KeyType.Backspace
              || keyStroke.getKeyType() == KeyType.Delete) {
            updatePreview(daysBox, previewLabel, keyStroke);
            return true; // let TextBox handle backspace
          }
          if (keyStroke.getCharacter() != null && Character.isDigit(keyStroke.getCharacter())) {
            updatePreview(daysBox, previewLabel, keyStroke);
            return true;
          }
          return false; // reject non-digit characters
        });

    panel.addComponent(daysBox);
    panel.addComponent(previewLabel);
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Enter confirm   Esc back"));
    return panel;
  }

  private void updatePreview(TextBox daysBox, Label previewLabel, KeyStroke keyStroke) {
    // Schedule update after TextBox processes the key
    try {
      int days = Integer.parseInt(daysBox.getText().trim());
      previewLabel.setText("Unlocks on " + computePreview(days));
    } catch (NumberFormatException e) {
      previewLabel.setText("Unlocks on —");
    }
  }

  private String computePreview(int days) {
    Instant base = secret.availableForDecryption()
        ? Instant.now()
        : secret.getDecryptionDate();
    return UiComponents.formatDate(base.plus(days, ChronoUnit.DAYS));
  }

  private void handleExtend(String text, Label errorLine) {
    int days;
    try {
      days = Integer.parseInt(text);
      if (days <= 0) throw new NumberFormatException();
    } catch (NumberFormatException ex) {
      errorLine.setText("Enter a positive number of days.");
      return;
    }
    int finalDays = days;
    nav.runAsync(
        "Extending lock…",
        () -> nav.vault().updateSecret(secret, finalDays, "vault"),
        () -> {
          nav.pop(); // back to detail
          // The detail panel will re-use the in-memory secret which was mutated by updateSecret
        },
        ex -> errorLine.setText("✗ " + ex.getMessage()));
  }

  private WindowListenerAdapter buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop();
        }
      }
    };
  }
}
