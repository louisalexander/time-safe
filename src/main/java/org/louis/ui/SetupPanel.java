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
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Config;

public class SetupPanel {

  private final NavigationController nav;

  public SetupPanel(NavigationController nav) {
    this.nav = nav;
  }

  public void show() {
    nav.push(buildPanel(), buildListener());
  }

  private Panel buildPanel() {
    Config existing = nav.config();

    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb("Secrets"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.brightLabel("Setup"));
    panel.addComponent(UiComponents.spacer());

    TextBox patBox = UiComponents.passwordInput(40);
    TextBox repoBox = UiComponents.singleLineInput(40);
    TextBox deliveryBox = UiComponents.singleLineInput(40);
    TextBox smtpUserBox = UiComponents.singleLineInput(40);
    TextBox smtpPassBox = UiComponents.passwordInput(40);

    if (existing != null) {
      if (existing.githubToken != null) patBox.setText(existing.githubToken);
      if (existing.githubRepo != null) repoBox.setText(existing.githubRepo);
      if (existing.deliveryEmail != null) deliveryBox.setText(existing.deliveryEmail);
      if (existing.smtpUser != null) smtpUserBox.setText(existing.smtpUser);
      if (existing.smtpPass != null) smtpPassBox.setText(existing.smtpPass);
    }

    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    // Enter on any field triggers save
    TextBox[] fields = {patBox, repoBox, deliveryBox, smtpUserBox, smtpPassBox};
    for (TextBox field : fields) {
      field.setInputFilter(
          (interactable, keyStroke) -> {
            if (keyStroke.getKeyType() == KeyType.Enter) {
              handleSave(patBox, repoBox, deliveryBox, smtpUserBox, smtpPassBox, errorLine);
              return false;
            }
            return true;
          });
    }

    panel.addComponent(UiComponents.dimLabel("GitHub token"));
    panel.addComponent(patBox);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("GitHub repo  (owner/repo)"));
    panel.addComponent(repoBox);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Delivery email"));
    panel.addComponent(deliveryBox);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("SMTP user"));
    panel.addComponent(smtpUserBox);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("SMTP password"));
    panel.addComponent(smtpPassBox);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Tab next field   Enter save   Esc cancel"));
    return panel;
  }

  private void handleSave(
      TextBox patBox,
      TextBox repoBox,
      TextBox deliveryBox,
      TextBox smtpUserBox,
      TextBox smtpPassBox,
      Label errorLine) {

    String pat = patBox.getText().trim();
    String repo = repoBox.getText().trim();
    String delivery = deliveryBox.getText().trim();
    String smtpUser = smtpUserBox.getText().trim();
    String smtpPass = smtpPassBox.getText().trim();

    if (pat.isEmpty()
        || repo.isEmpty()
        || delivery.isEmpty()
        || smtpUser.isEmpty()
        || smtpPass.isEmpty()) {
      errorLine.setText("All fields are required.");
      return;
    }

    Config newConfig = new Config();
    newConfig.githubToken = pat;
    newConfig.githubRepo = repo;
    newConfig.deliveryEmail = delivery;
    newConfig.smtpUser = smtpUser;
    newConfig.smtpPass = smtpPass;

    boolean isNewRepo = nav.config() == null || !repo.equals(nav.config().githubRepo);

    nav.applyConfig(
        newConfig,
        isNewRepo,
        () -> {
          nav.popToRoot();
          nav.showRootStatus("✓ Setup complete", false);
        },
        ex -> {
          String msg = ex.getMessage() != null ? ex.getMessage() : ex.toString();
          if (msg.contains("404")) {
            errorLine.setText("GitHub 404 — PAT may be missing 'workflow' scope.");
          } else {
            errorLine.setText("✗ " + msg);
          }
        });
  }

  private WindowListener buildListener() {
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
