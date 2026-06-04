package org.louis.ui;

import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.WindowListener;
import java.util.function.Consumer;
import org.louis.Config;
import org.louis.VaultManager;

public interface NavigationController {

  /** Push a new full-screen panel onto the nav stack. */
  void push(Panel content, WindowListener keyListener);

  /** Pop back to the previous panel. */
  void pop();

  /** Pop all the way back to the secrets list and refresh it. */
  void popToRoot();

  /** Close the application. */
  void quit();

  /** Access the vault (may be null if not configured). */
  VaultManager vault();

  /** Access current config (may be null if not configured). */
  Config config();

  /**
   * Persist a new config and optionally reinitialise the GitHub vault.
   * Calls initRepo() on GitHub only when reinitVault is true.
   * Calls onSuccess on the GUI thread after completion, or onError on failure.
   */
  void applyConfig(
      Config newConfig,
      boolean reinitVault,
      Runnable onSuccess,
      Consumer<Exception> onError);

  /**
   * Run a blocking action on a background thread, show a loading message,
   * then call onSuccess or onError on the GUI thread.
   */
  void runAsync(
      String loadingMessage,
      ThrowingRunnable action,
      Runnable onSuccess,
      Consumer<Exception> onError);

  /**
   * Show a transient status message on the secrets list (green or red).
   * Call after popToRoot() so the message appears on the refreshed list.
   */
  void showRootStatus(String message, boolean isError);

  @FunctionalInterface
  interface ThrowingRunnable {
    void run() throws Exception;
  }
}
