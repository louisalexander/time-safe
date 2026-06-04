package org.louis.ui;

import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class DeletePanel {

  private final NavigationController nav;
  private final Secret secret;

  public DeletePanel(NavigationController nav, Secret secret) {
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

    Label heading = new Label("Delete \"" + secret.getName() + "\"?");
    heading.setForegroundColor(UiColors.RED);
    panel.addComponent(heading);
    panel.addComponent(UiComponents.spacer());

    panel.addComponent(
        UiComponents.dimLabel("This will remove the encrypted file, metadata,"));
    panel.addComponent(
        UiComponents.dimLabel("key, and GitHub Actions workflow. Cannot be undone."));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("y confirm   Esc cancel"));
    return panel;
  }

  private WindowListener buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop();
          return;
        }
        if (k.getCharacter() != null && Character.toLowerCase(k.getCharacter()) == 'y') {
          consumed.set(true);
          nav.runAsync(
              "Deleting…",
              () -> nav.vault().delete(secret),
              () -> nav.popToRoot(),
              ex -> {
                nav.popToRoot();
                nav.showRootStatus("✗ delete failed: " + ex.getMessage(), true);
              });
        }
      }
    };
  }
}
