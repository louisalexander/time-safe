package org.louis.ui;

import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.WindowListener;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.function.Consumer;
import org.louis.Config;
import org.louis.VaultManager;

/**
 * Test double for {@link NavigationController}. Records pushed panels and exposes counters for
 * verification. Does not require a real Lanterna GUI.
 */
class FakeNavigationController implements NavigationController {

  private Config config;
  private VaultManager vault;

  final Deque<Panel> pushed = new ArrayDeque<>();
  final Deque<WindowListener> pushedListeners = new ArrayDeque<>();
  int popCount;
  int popToRootCount;
  int quitCount;
  String lastRootStatusMessage;
  Boolean lastRootStatusIsError;

  FakeNavigationController withConfig(Config c) {
    this.config = c;
    return this;
  }

  FakeNavigationController withVault(VaultManager v) {
    this.vault = v;
    return this;
  }

  @Override
  public void push(Panel content, WindowListener keyListener) {
    pushed.push(content);
    pushedListeners.push(keyListener);
  }

  @Override
  public void pop() {
    popCount++;
    if (!pushed.isEmpty()) pushed.pop();
    if (!pushedListeners.isEmpty()) pushedListeners.pop();
  }

  @Override
  public void popToRoot() {
    popToRootCount++;
    pushed.clear();
    pushedListeners.clear();
  }

  @Override
  public void quit() {
    quitCount++;
  }

  @Override
  public VaultManager vault() {
    return vault;
  }

  @Override
  public Config config() {
    return config;
  }

  @Override
  public void applyConfig(
      Config newConfig, boolean reinitVault, Runnable onSuccess, Consumer<Exception> onError) {
    this.config = newConfig;
    onSuccess.run();
  }

  @Override
  public void runAsync(
      String loadingMessage,
      ThrowingRunnable action,
      Runnable onSuccess,
      Consumer<Exception> onError) {
    try {
      action.run();
      onSuccess.run();
    } catch (Exception e) {
      onError.accept(e);
    }
  }

  @Override
  public <T> void runAsync(
      String loadingMessage,
      ThrowingSupplier<T> action,
      Consumer<T> onSuccess,
      Consumer<Exception> onError) {
    try {
      T result = action.get();
      onSuccess.accept(result);
    } catch (Exception e) {
      onError.accept(e);
    }
  }

  @Override
  public void showRootStatus(String message, boolean isError) {
    lastRootStatusMessage = message;
    lastRootStatusIsError = isError;
  }
}
