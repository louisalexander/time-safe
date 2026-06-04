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
import java.util.concurrent.atomic.AtomicBoolean;

public class AddSecretPanel {

  private final NavigationController nav;

  // State preserved across steps
  private String savedName = "";
  private int savedDays = 0;

  public AddSecretPanel(NavigationController nav) {
    this.nav = nav;
  }

  public void show() {
    showStep1();
  }

  // ── Step 1: Name ─────────────────────────────────────────────────────────────

  private void showStep1() {
    TextBox nameBox = UiComponents.singleLineInput(40);
    nameBox.setText(savedName);
    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    nameBox.setInputFilter(
        (interactable, keyStroke) -> {
          if (keyStroke.getKeyType() == KeyType.Enter) {
            String name = nameBox.getText().trim();
            if (name.isEmpty()) {
              errorLine.setText("Name must not be empty.");
              return false;
            }
            savedName = name;
            nav.push(buildStep2Panel(), buildStep2Listener());
            return false;
          }
          return true;
        });

    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb("Secrets"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Add secret — step 1 of 3"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Secret name"));
    panel.addComponent(nameBox);
    panel.addComponent(UiComponents.dimLabel("A label for this secret."));
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Enter next   Esc cancel"));

    nav.push(panel, buildStep1Listener());
  }

  private WindowListenerAdapter buildStep1Listener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop(); // back to list
        }
      }
    };
  }

  // ── Step 2: Lock duration ────────────────────────────────────────────────────

  private Panel buildStep2Panel() {
    TextBox daysBox = UiComponents.singleLineInput(10);
    if (savedDays > 0) daysBox.setText(String.valueOf(savedDays));

    Label previewLabel =
        new Label(
            savedDays > 0
                ? "Unlocks on " + UiComponents.previewUnlockDate(savedDays)
                : "Unlocks on —");
    previewLabel.setForegroundColor(UiColors.DIM);
    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    daysBox.setInputFilter(
        (interactable, keyStroke) -> {
          if (keyStroke.getKeyType() == KeyType.Enter) {
            int days;
            try {
              days = Integer.parseInt(daysBox.getText().trim());
              if (days <= 0) throw new NumberFormatException();
            } catch (NumberFormatException ex) {
              errorLine.setText("Enter a positive number of days.");
              return false;
            }
            savedDays = days;

            // ── Inline Step 3 construction ──────────────────────────────────────
            TextBox secretBox = UiComponents.multiLineInput(60, 8);
            Label errorLine3 = new Label("");
            errorLine3.setForegroundColor(UiColors.RED);

            Panel step3Panel = new Panel(new LinearLayout(Direction.VERTICAL));
            step3Panel.addComponent(UiComponents.breadcrumb("Secrets"));
            step3Panel.addComponent(UiComponents.spacer());
            step3Panel.addComponent(UiComponents.dimLabel("Add secret — step 3 of 3"));
            step3Panel.addComponent(UiComponents.spacer());
            step3Panel.addComponent(UiComponents.dimLabel("Secret text"));
            step3Panel.addComponent(secretBox);
            step3Panel.addComponent(UiComponents.dimLabel("This will be encrypted."));
            step3Panel.addComponent(errorLine3);
            step3Panel.addComponent(UiComponents.spacer());
            step3Panel.addComponent(UiComponents.dimLabel("Ctrl+Enter save   Esc back"));

            WindowListenerAdapter step3Listener =
                new WindowListenerAdapter() {
                  @Override
                  public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
                    if (k.getKeyType() == KeyType.Escape) {
                      consumed.set(true);
                      nav.pop();
                      return;
                    }
                    // Ctrl+Enter
                    if (k.isCtrlDown() && k.getKeyType() == KeyType.Enter) {
                      consumed.set(true);
                      String text = secretBox.getText().trim();
                      if (text.isEmpty()) {
                        errorLine3.setText("Secret text must not be empty.");
                        return;
                      }
                      nav.runAsync(
                          "Encrypting and pushing to GitHub…",
                          () -> nav.vault().putSecret(savedDays, text, savedName),
                          () -> {
                            nav.popToRoot();
                            nav.showRootStatus(
                                "✓ "
                                    + savedName
                                    + " locked until "
                                    + UiComponents.previewUnlockDate(savedDays),
                                false);
                          },
                          ex -> errorLine3.setText("✗ " + ex.getMessage()));
                    }
                  }
                };

            nav.push(step3Panel, step3Listener);
            return false;
          }
          if (keyStroke.getKeyType() == KeyType.Backspace
              || keyStroke.getKeyType() == KeyType.Delete) return true;
          if (keyStroke.getCharacter() != null && Character.isDigit(keyStroke.getCharacter())) {
            try {
              String current = daysBox.getText() + keyStroke.getCharacter();
              int preview = Integer.parseInt(current.trim());
              previewLabel.setText("Unlocks on " + UiComponents.previewUnlockDate(preview));
            } catch (NumberFormatException e) {
              previewLabel.setText("Unlocks on —");
            }
            return true;
          }
          return false;
        });

    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb("Secrets"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Add secret — step 2 of 3"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Lock for how many days?"));
    panel.addComponent(daysBox);
    panel.addComponent(previewLabel);
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Enter next   Esc back"));
    return panel;
  }

  private WindowListenerAdapter buildStep2Listener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop(); // back to step 1
        }
      }
    };
  }
}
