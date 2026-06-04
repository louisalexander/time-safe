package org.louis.ui;

import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.graphics.SimpleTheme;
import com.googlecode.lanterna.gui2.BasicWindow;
import com.googlecode.lanterna.gui2.DefaultWindowManager;
import com.googlecode.lanterna.gui2.EmptySpace;
import com.googlecode.lanterna.gui2.MultiWindowTextGUI;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Panels;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.screen.Screen;
import com.googlecode.lanterna.screen.TerminalScreen;
import com.googlecode.lanterna.terminal.DefaultTerminalFactory;
import com.googlecode.lanterna.terminal.Terminal;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Set;
import java.util.function.Consumer;
import org.louis.Config;
import org.louis.GitHubVault;
import org.louis.Log;
import org.louis.VaultManager;

public class TimeSafeTui implements NavigationController {

  // ── App state ───────────────────────────────────────────────────────────────

  private Config config;
  private VaultManager vaultManager;

  // ── Lanterna ────────────────────────────────────────────────────────────────

  private MultiWindowTextGUI gui;
  private Screen screen;
  private BasicWindow mainWindow;

  // ── Navigation stack ────────────────────────────────────────────────────────

  private record NavEntry(Panel panel, WindowListener listener) {}

  private final Deque<NavEntry> navStack = new ArrayDeque<>();
  private Panel currentPanel;
  private WindowListener currentListener;

  // ── Root panel ──────────────────────────────────────────────────────────────

  private SecretsListPanel secretsListPanel;

  // ── Countdown timer ─────────────────────────────────────────────────────────

  private volatile boolean stopRefresh = false;

  // ── Entry point ─────────────────────────────────────────────────────────────

  public void run() throws IOException {
    Terminal terminal =
        new DefaultTerminalFactory(
                new PrintStream(System.out, true, StandardCharsets.UTF_8),
                System.in,
                StandardCharsets.UTF_8)
            .createTerminal();
    screen = new TerminalScreen(terminal);
    screen.startScreen();

    gui =
        new MultiWindowTextGUI(
            screen, new DefaultWindowManager(), new EmptySpace(TextColor.ANSI.DEFAULT));
    // Use a transparent theme so the terminal's own background shows through
    // everywhere — no blue listbox / window backgrounds painted by the default theme.
    gui.setTheme(
        SimpleTheme.makeTheme(
            false,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT,
            TextColor.ANSI.DEFAULT));

    try {
      config = Config.load();
      vaultManager = new VaultManager(config);
      Log.info("Config loaded: " + config.githubRepo);
    } catch (IOException e) {
      Log.warn("No config found — running unconfigured");
      config = null;
      vaultManager = null;
    }

    mainWindow = new BasicWindow("TimeSafe");
    mainWindow.setHints(
        Set.of(
            Window.Hint.FULL_SCREEN, Window.Hint.NO_DECORATIONS, Window.Hint.FIT_TERMINAL_WINDOW));

    secretsListPanel = new SecretsListPanel(this);
    currentPanel = secretsListPanel.build();
    currentListener = secretsListPanel.buildListener();
    mainWindow.setComponent(currentPanel);
    mainWindow.addWindowListener(currentListener);

    startCountdownTimer();
    gui.addWindowAndWait(mainWindow);
    screen.stopScreen();
  }

  // ── NavigationController ─────────────────────────────────────────────────────

  @Override
  public void push(Panel content, WindowListener keyListener) {
    navStack.push(new NavEntry(currentPanel, currentListener));
    if (currentListener != null) mainWindow.removeWindowListener(currentListener);
    currentPanel = content;
    currentListener = keyListener;
    mainWindow.setComponent(content);
    if (keyListener != null) mainWindow.addWindowListener(keyListener);
  }

  @Override
  public void pop() {
    if (navStack.isEmpty()) return;
    if (currentListener != null) mainWindow.removeWindowListener(currentListener);
    NavEntry prev = navStack.pop();
    currentPanel = prev.panel();
    currentListener = prev.listener();
    mainWindow.setComponent(currentPanel);
    if (currentListener != null) mainWindow.addWindowListener(currentListener);
  }

  @Override
  public void popToRoot() {
    if (currentListener != null) mainWindow.removeWindowListener(currentListener);
    navStack.clear();
    // build() re-reads vault state and creates a fresh panel
    currentPanel = secretsListPanel.build();
    currentListener = secretsListPanel.buildListener();
    mainWindow.setComponent(currentPanel);
    mainWindow.addWindowListener(currentListener);
  }

  @Override
  public void showRootStatus(String message, boolean isError) {
    secretsListPanel.showStatus(message, isError);
  }

  @Override
  public void quit() {
    stopRefresh = true;
    mainWindow.close();
  }

  @Override
  public VaultManager vault() {
    return vaultManager;
  }

  @Override
  public Config config() {
    return config;
  }

  @Override
  public void applyConfig(
      Config newConfig, boolean reinitVault, Runnable onSuccess, Consumer<Exception> onError) {
    runAsync(
        reinitVault ? "Initialising vault on GitHub…" : "Saving config…",
        () -> {
          newConfig.save(Config.DEFAULT_PATH);
          if (reinitVault) new GitHubVault(newConfig).initRepo();
        },
        () -> {
          config = newConfig;
          vaultManager = new VaultManager(newConfig);
          Log.info("Config applied: " + newConfig.githubRepo);
          onSuccess.run();
        },
        onError);
  }

  @Override
  public void runAsync(
      String loadingMessage,
      ThrowingRunnable action,
      Runnable onSuccess,
      Consumer<Exception> onError) {
    BasicWindow loadingWin = new BasicWindow();
    loadingWin.setHints(Set.of(Window.Hint.CENTERED, Window.Hint.MODAL));
    loadingWin.setComponent(
        Panels.vertical(
            new com.googlecode.lanterna.gui2.Label(loadingMessage),
            new com.googlecode.lanterna.gui2.Label("Please wait…")));
    gui.addWindow(loadingWin);

    Thread worker =
        new Thread(
            () -> {
              try {
                action.run();
                gui.getGUIThread()
                    .invokeLater(
                        () -> {
                          loadingWin.close();
                          onSuccess.run();
                        });
              } catch (Exception e) {
                gui.getGUIThread()
                    .invokeLater(
                        () -> {
                          loadingWin.close();
                          onError.accept(e);
                        });
              }
            });
    worker.setDaemon(true);
    worker.start();
  }

  @Override
  public <T> void runAsync(
      String loadingMessage,
      ThrowingSupplier<T> action,
      Consumer<T> onSuccess,
      Consumer<Exception> onError) {
    BasicWindow loadingWin = new BasicWindow();
    loadingWin.setHints(Set.of(Window.Hint.CENTERED, Window.Hint.MODAL));
    loadingWin.setComponent(
        Panels.vertical(
            new com.googlecode.lanterna.gui2.Label(loadingMessage),
            new com.googlecode.lanterna.gui2.Label("Please wait…")));
    gui.addWindow(loadingWin);

    Thread worker =
        new Thread(
            () -> {
              try {
                T result = action.get();
                gui.getGUIThread()
                    .invokeLater(
                        () -> {
                          loadingWin.close();
                          onSuccess.accept(result);
                        });
              } catch (Exception e) {
                gui.getGUIThread()
                    .invokeLater(
                        () -> {
                          loadingWin.close();
                          onError.accept(e);
                        });
              }
            });
    worker.setDaemon(true);
    worker.start();
  }

  // ── Countdown timer ──────────────────────────────────────────────────────────

  private void startCountdownTimer() {
    Thread t =
        new Thread(
            () -> {
              while (!stopRefresh) {
                try {
                  Thread.sleep(1000);
                } catch (InterruptedException e) {
                  break;
                }
                if (stopRefresh) break;
                try {
                  gui.getGUIThread().invokeLater(secretsListPanel::refreshTimes);
                } catch (Exception e) {
                  break;
                }
              }
            });
    t.setDaemon(true);
    t.start();
  }
}
