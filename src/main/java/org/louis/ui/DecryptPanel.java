package org.louis.ui;

import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextBox;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.util.Base64;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class DecryptPanel {

  private final NavigationController nav;
  private final Secret secret;

  public DecryptPanel(NavigationController nav, Secret secret) {
    this.nav = nav;
    this.secret = secret;
  }

  public void show() {
    nav.push(buildInputPanel(), buildInputListener());
  }

  // ── Input screen ────────────────────────────────────────────────────────────

  private Panel buildInputPanel() {
    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb(secret.getName()));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Decryption key (base64)"));

    TextBox keyBox = UiComponents.singleLineInput(60);
    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    // Enter in the TextBox triggers decryption
    keyBox.setInputFilter(
        (interactable, keyStroke) -> {
          if (keyStroke.getKeyType() == KeyType.Enter) {
            handleDecrypt(keyBox.getText().trim(), errorLine);
            return false; // consume
          }
          return true;
        });

    panel.addComponent(keyBox);
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Enter decrypt   Esc back"));

    return panel;
  }

  private com.googlecode.lanterna.gui2.WindowListener buildInputListener() {
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

  private void handleDecrypt(String raw, Label errorLine) {
    if (raw.isEmpty()) return;
    byte[] keyBytes;
    try {
      keyBytes = Base64.getDecoder().decode(raw);
    } catch (IllegalArgumentException ex) {
      errorLine.setText("Invalid base64 — paste the full key from the email.");
      return;
    }

    nav.runAsync(
        "Decrypting…",
        () -> {
          String plaintext = nav.vault().decrypt(secret, keyBytes);
          if (plaintext.startsWith("Decryption failed:")) throw new Exception(plaintext);
          return plaintext;
        },
        plaintext -> {
          // Replace current panel with result view (pop input, push result)
          nav.pop();
          nav.push(buildResultPanel(plaintext), buildResultListener());
        },
        ex -> errorLine.setText("✗ " + ex.getMessage()));
  }

  // ── Result screen ────────────────────────────────────────────────────────────

  private Panel buildResultPanel(String plaintext) {
    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb(secret.getName()));
    panel.addComponent(UiComponents.spacer());

    Label successLabel = new Label("✓ decrypted");
    successLabel.setForegroundColor(UiColors.GREEN);
    panel.addComponent(successLabel);
    panel.addComponent(UiComponents.spacer());

    TextBox resultBox = UiComponents.multiLineInput(60, 10);
    resultBox.setText(plaintext);
    resultBox.setReadOnly(true);
    panel.addComponent(resultBox);

    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Esc back"));
    return panel;
  }

  private com.googlecode.lanterna.gui2.WindowListener buildResultListener() {
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
