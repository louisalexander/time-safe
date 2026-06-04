package org.louis.ui;

import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.gui2.ActionListBox;
import com.googlecode.lanterna.gui2.BasicWindow;
import com.googlecode.lanterna.gui2.Button;
import com.googlecode.lanterna.gui2.GridLayout;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.MultiWindowTextGUI;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Panels;
import com.googlecode.lanterna.gui2.TextBox;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.gui2.dialogs.MessageDialog;
import com.googlecode.lanterna.gui2.dialogs.MessageDialogButton;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.screen.Screen;
import com.googlecode.lanterna.screen.TerminalScreen;
import com.googlecode.lanterna.terminal.DefaultTerminalFactory;
import com.googlecode.lanterna.terminal.Terminal;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collection;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.louis.Config;
import org.louis.GitHubVault;
import org.louis.Secret;
import org.louis.VaultManager;

/** Full Lanterna TUI for TimeSafe. */
public class TimeSafeTui {

  @FunctionalInterface
  interface ThrowingRunnable {
    void run() throws Exception;
  }

  private Config config;
  private VaultManager vaultManager;
  private MultiWindowTextGUI gui;
  private Screen screen;
  private BasicWindow mainWindow;
  private Panel mainContentPanel;

  /** Entry point: initialize screen and start the event loop. */
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
            screen,
            new com.googlecode.lanterna.gui2.DefaultWindowManager(),
            new com.googlecode.lanterna.gui2.EmptySpace(TextColor.ANSI.BLACK));

    // Try loading config + vault manager
    try {
      config = Config.load();
      vaultManager = new VaultManager(config);
    } catch (IOException e) {
      config = null;
      vaultManager = null;
    }

    mainWindow = new BasicWindow("TimeSafe for Secrets");
    mainWindow.setHints(
        Set.of(
            Window.Hint.FULL_SCREEN, Window.Hint.NO_DECORATIONS, Window.Hint.FIT_TERMINAL_WINDOW));

    buildMainWindow();
    gui.addWindowAndWait(mainWindow);
    screen.stopScreen();
  }

  // ── Main window ────────────────────────────────────────────────────────────

  private void buildMainWindow() {
    mainWindow.setComponent(buildMainWindowPanel());
    mainWindow.addWindowListener(
        new WindowListenerAdapter() {
          @Override
          public void onUnhandledInput(
              Window sourceWindow, KeyStroke keyStroke, AtomicBoolean consumed) {
            if (keyStroke.getCharacter() == null) return;
            switch (Character.toLowerCase(keyStroke.getCharacter())) {
              case 'a':
                if (vaultManager != null) {
                  consumed.set(true);
                  showAddSecretDialog();
                  rebuildSecretsList();
                }
                break;
              case 's':
                consumed.set(true);
                showSetupDialog();
                break;
              case 'q':
                consumed.set(true);
                mainWindow.close();
                break;
              default:
                break;
            }
          }
        });
  }

  private void rebuildSecretsList() {
    mainContentPanel.removeAllComponents();

    if (vaultManager == null) {
      Label msg = new Label("No config found — press S to open Setup.");
      msg.setForegroundColor(TextColor.ANSI.WHITE);
      mainContentPanel.addComponent(msg);
      return;
    }

    Collection<Secret> secrets = vaultManager.getSecrets();
    List<Secret> secretList = new ArrayList<>(secrets);

    if (secretList.isEmpty()) {
      Label msg = new Label("No secrets yet — press A to add one.");
      msg.setForegroundColor(TextColor.ANSI.WHITE);
      mainContentPanel.addComponent(msg);
      return;
    }

    ActionListBox listBox = new ActionListBox();
    for (Secret s : secretList) {
      String label = formatSecretEntry(s);
      listBox.addItem(label, () -> showSecretDetailWindow(s));
    }
    mainContentPanel.addComponent(listBox);
  }

  // ── Secret detail window (Screen 2) ───────────────────────────────────────

  private void showSecretDetailWindow(Secret secret) {
    BasicWindow detailWin = new BasicWindow();
    detailWin.setHints(Set.of(Window.Hint.CENTERED, Window.Hint.NO_DECORATIONS));

    Panel panel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));

    boolean ready = secret.availableForDecryption();

    // top padding row that also enforces a minimum dialog width
    panel.addComponent(
        new com.googlecode.lanterna.gui2.EmptySpace(
            new com.googlecode.lanterna.TerminalSize(44, 1)));

    // Status row
    Panel statusRow =
        new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    statusRow.addComponent(new Label("  Status:   "));
    Label statusLabel;
    if (ready) {
      statusLabel = new Label("✓  READY TO DECRYPT              ");
      statusLabel.setForegroundColor(TextColor.ANSI.GREEN);
    } else {
      statusLabel = new Label("✗  Locked                        ");
      statusLabel.setForegroundColor(TextColor.ANSI.RED);
    }
    statusRow.addComponent(statusLabel);
    panel.addComponent(statusRow);

    // Unlock date row
    Panel unlockRow =
        new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    unlockRow.addComponent(new Label("  Unlocks:  "));
    unlockRow.addComponent(new Label(formatUnlockDate(secret.getDecryptionDate()) + "  "));
    panel.addComponent(unlockRow);

    // ID row
    Panel idRow = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    idRow.addComponent(new Label("  ID:        "));
    String shortId =
        secret.getId().length() > 8 ? secret.getId().substring(0, 8) + "..." : secret.getId();
    idRow.addComponent(new Label(shortId + "  "));
    panel.addComponent(idRow);

    // spacer
    panel.addComponent(
        new com.googlecode.lanterna.gui2.EmptySpace(
            new com.googlecode.lanterna.TerminalSize(1, 1)));

    // Buttons
    Panel btns = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    btns.addComponent(new Label("  "));
    if (ready) {
      btns.addComponent(new Button("Decrypt", () -> showDecryptDialog(secret, detailWin)));
      btns.addComponent(new Label("  "));
    }
    btns.addComponent(new Button("Extend Lock", () -> showExtendLockDialog(secret, detailWin)));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Delete", () -> showDeleteConfirmation(secret, detailWin)));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Close", detailWin::close));
    btns.addComponent(new Label("  "));
    panel.addComponent(btns);

    // bottom padding
    panel.addComponent(
        new com.googlecode.lanterna.gui2.EmptySpace(
            new com.googlecode.lanterna.TerminalSize(1, 1)));

    detailWin.setComponent(
        panel.withBorder(
            com.googlecode.lanterna.gui2.Borders.singleLine(" " + secret.getName() + " ")));
    gui.addWindow(detailWin);
    gui.setActiveWindow(detailWin);
  }

  // ── Decrypt dialog (Screen 3) ──────────────────────────────────────────────

  private void showDecryptDialog(Secret secret, BasicWindow detailWin) {
    BasicWindow dlg = new BasicWindow("Decrypt: " + secret.getName());
    dlg.setHints(Set.of(Window.Hint.CENTERED));

    Panel panel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));
    panel.addComponent(new Label("Paste the base64 key from your unlock email:"));
    TextBox keyBox = new TextBox(new com.googlecode.lanterna.TerminalSize(60, 1));
    panel.addComponent(keyBox);
    panel.addComponent(new Label(""));

    Panel btns = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    btns.addComponent(
        new Button(
            "Decrypt",
            () -> {
              String raw = keyBox.getText().trim();
              byte[] keyBytes;
              try {
                keyBytes = Base64.getDecoder().decode(raw);
              } catch (IllegalArgumentException ex) {
                showError(
                    "Invalid Key", "Invalid key — paste the full base64 string from the email.");
                return;
              }
              dlg.close();
              runWithLoading(
                  "Decrypting...",
                  () -> {
                    String plaintext = vaultManager.decrypt(secret, keyBytes);
                    if (plaintext.startsWith("Decryption failed:")) {
                      throw new Exception(plaintext);
                    }
                    gui.getGUIThread()
                        .invokeLater(
                            () ->
                                MessageDialog.showMessageDialog(
                                    gui, "Decrypted", plaintext, MessageDialogButton.OK));
                  },
                  () -> {},
                  ex -> showError("Decryption Failed", ex.getMessage()));
            }));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Cancel", dlg::close));
    panel.addComponent(btns);

    dlg.setComponent(panel);
    gui.addWindow(dlg);
    gui.setActiveWindow(dlg);
  }

  // ── Add secret dialog (Screen 4) ──────────────────────────────────────────

  private void showAddSecretDialog() {
    BasicWindow dlg = new BasicWindow("Add Secret");
    dlg.setHints(Set.of(Window.Hint.CENTERED));

    Panel panel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));

    Panel fields = new Panel(new GridLayout(2));
    fields.addComponent(new Label("Name:"));
    TextBox nameBox = new TextBox(new com.googlecode.lanterna.TerminalSize(30, 1));
    fields.addComponent(nameBox);

    fields.addComponent(new Label("Secret:"));
    TextBox secretBox = new TextBox(new com.googlecode.lanterna.TerminalSize(30, 1)).setMask('*');
    fields.addComponent(secretBox);

    fields.addComponent(new Label("Lock for (days):"));
    TextBox daysBox = new TextBox(new com.googlecode.lanterna.TerminalSize(10, 1));
    fields.addComponent(daysBox);

    panel.addComponent(fields);
    panel.addComponent(new Label(""));

    Panel btns = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    btns.addComponent(
        new Button(
            "Save",
            () -> {
              String name = nameBox.getText().trim();
              String secretText = secretBox.getText().trim();
              String daysStr = daysBox.getText().trim();

              if (name.isEmpty() || secretText.isEmpty()) {
                showError("Validation Error", "Name and Secret must not be empty.");
                return;
              }
              int days;
              try {
                days = Integer.parseInt(daysStr);
                if (days <= 0) throw new NumberFormatException();
              } catch (NumberFormatException ex) {
                showError("Validation Error", "Days must be a positive integer.");
                return;
              }

              int finalDays = days;
              dlg.close();
              Instant unlockDate = Instant.now().plus(finalDays, ChronoUnit.DAYS);
              String dateStr =
                  DateTimeFormatter.ofPattern("MMM d, yyyy")
                      .format(unlockDate.atZone(ZoneId.systemDefault()));
              runWithLoading(
                  "Encrypting and pushing to GitHub...",
                  () -> vaultManager.putSecret(finalDays, secretText, name),
                  () -> showInfo("Secret Locked", "Secret locked until " + dateStr + "."),
                  ex -> {
                    String msg = ex.getMessage() != null ? ex.getMessage() : ex.toString();
                    if (msg.contains("404")) {
                      showError(
                          "GitHub 404",
                          "GitHub returned 404 — most likely cause:\n\n"
                              + "  Your PAT is missing the 'workflow' scope.\n"
                              + "  Pushing to .github/workflows/ requires it.\n\n"
                              + "Fix: regenerate your PAT at github.com/settings/tokens\n"
                              + "with both 'repo' and 'workflow' scopes, then re-run Setup.\n\n"
                              + "Vault repo: "
                              + (config != null ? config.githubRepo : "unknown"));
                    } else {
                      showError("Failed to Lock Secret", msg);
                    }
                  });
            }));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Cancel", dlg::close));
    panel.addComponent(btns);

    dlg.setComponent(panel);
    gui.addWindow(dlg);
    gui.setActiveWindow(dlg);
    // Wait for this dialog to close before returning so caller can rebuildSecretsList
    gui.waitForWindowToClose(dlg);
  }

  // ── Extend lock dialog (Screen 5) ─────────────────────────────────────────

  private void showExtendLockDialog(Secret secret, BasicWindow detailWin) {
    BasicWindow dlg = new BasicWindow("Extend Lock: " + secret.getName());
    dlg.setHints(Set.of(Window.Hint.CENTERED));

    Panel panel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));
    panel.addComponent(new Label("Additional days to add to the lock:"));
    TextBox daysBox = new TextBox(new com.googlecode.lanterna.TerminalSize(10, 1)).setText("30");
    panel.addComponent(daysBox);
    panel.addComponent(
        new Label("Current unlock: " + formatUnlockDate(secret.getDecryptionDate())));
    panel.addComponent(new Label(""));

    Panel btns = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    btns.addComponent(
        new Button(
            "Extend",
            () -> {
              int days;
              try {
                days = Integer.parseInt(daysBox.getText().trim());
                if (days <= 0) throw new NumberFormatException();
              } catch (NumberFormatException ex) {
                showError("Validation Error", "Days must be a positive integer.");
                return;
              }
              int finalDays = days;
              dlg.close();
              runWithLoading(
                  "Extending lock on GitHub...",
                  () -> vaultManager.updateSecret(secret, finalDays, "vault"),
                  () -> {
                    showInfo("Lock Extended", "Lock extended.");
                    detailWin.close();
                    rebuildSecretsList();
                  },
                  ex -> showError("Error", ex.getMessage()));
            }));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Cancel", dlg::close));
    panel.addComponent(btns);

    dlg.setComponent(panel);
    gui.addWindow(dlg);
    gui.setActiveWindow(dlg);
  }

  // ── Delete confirmation (Screen 6) ────────────────────────────────────────

  private void showDeleteConfirmation(Secret secret, BasicWindow detailWin) {
    MessageDialogButton result =
        MessageDialog.showMessageDialog(
            gui,
            "Delete secret?",
            "This will permanently delete \""
                + secret.getName()
                + "\" and its vault files. This cannot be undone.",
            MessageDialogButton.OK,
            MessageDialogButton.Cancel);
    if (result == MessageDialogButton.OK) {
      runWithLoading(
          "Deleting from GitHub...",
          () -> vaultManager.delete(secret),
          () -> {
            detailWin.close();
            rebuildSecretsList();
          },
          ex -> {
            detailWin.close();
            rebuildSecretsList();
            showError(
                "Partial Delete",
                "Local secret removed, but GitHub cleanup failed:\n\n"
                    + ex.getMessage()
                    + "\n\nThe encrypted blob or workflow may still exist in the vault repo.");
          });
    }
  }

  // ── Setup dialog (Screen 7) ───────────────────────────────────────────────

  private void showSetupDialog() {
    BasicWindow dlg = new BasicWindow("Setup");
    dlg.setHints(Set.of(Window.Hint.CENTERED));

    Panel panel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));

    Panel fields = new Panel(new GridLayout(2));
    fields.addComponent(new Label("GitHub PAT:"));
    TextBox patBox = new TextBox(new com.googlecode.lanterna.TerminalSize(40, 1));
    fields.addComponent(patBox);

    fields.addComponent(new Label("Vault repo (owner/repo):"));
    TextBox repoBox = new TextBox(new com.googlecode.lanterna.TerminalSize(40, 1));
    fields.addComponent(repoBox);

    fields.addComponent(new Label("Vault Gmail:"));
    TextBox gmailBox = new TextBox(new com.googlecode.lanterna.TerminalSize(40, 1));
    fields.addComponent(gmailBox);

    fields.addComponent(new Label("Gmail App Password:"));
    TextBox gmailPassBox =
        new TextBox(new com.googlecode.lanterna.TerminalSize(40, 1)).setMask('*');
    fields.addComponent(gmailPassBox);

    fields.addComponent(new Label("Delivery email:"));
    TextBox deliveryBox = new TextBox(new com.googlecode.lanterna.TerminalSize(40, 1));
    fields.addComponent(deliveryBox);

    panel.addComponent(fields);
    panel.addComponent(new Label(""));

    Panel btns = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    btns.addComponent(
        new Button(
            "Save & Initialize",
            () -> {
              String pat = patBox.getText().trim();
              String repo = repoBox.getText().trim();
              String gmail = gmailBox.getText().trim();
              String gmailPass = gmailPassBox.getText().trim();
              String delivery = deliveryBox.getText().trim();

              if (pat.isEmpty()
                  || repo.isEmpty()
                  || gmail.isEmpty()
                  || gmailPass.isEmpty()
                  || delivery.isEmpty()) {
                showError("Validation Error", "All fields are required.");
                return;
              }

              Config newConfig = new Config();
              newConfig.githubToken = pat;
              newConfig.githubRepo = repo;
              newConfig.smtpUser = gmail;
              newConfig.smtpPass = gmailPass;
              newConfig.deliveryEmail = delivery;

              dlg.close();
              runWithLoading(
                  "Initializing vault on GitHub...",
                  () -> {
                    newConfig.save(Config.DEFAULT_PATH);
                    new GitHubVault(newConfig).initRepo();
                  },
                  () -> {
                    config = newConfig;
                    vaultManager = new VaultManager(newConfig);
                    // Rebuild the main window from scratch so Add Secret button appears
                    mainWindow.setComponent(buildMainWindowPanel());
                    rebuildSecretsList();
                    showInfo("Setup Complete", "Vault initialized successfully.");
                  },
                  ex -> {
                    String msg = ex.getMessage() != null ? ex.getMessage() : ex.toString();
                    if (msg.contains("404")) {
                      showError(
                          "GitHub 404",
                          "GitHub returned 404 — most likely cause:\n\n"
                              + "  Your PAT is missing the 'workflow' scope.\n"
                              + "  Pushing to .github/workflows/ requires it.\n\n"
                              + "Fix: regenerate your PAT at github.com/settings/tokens\n"
                              + "with both 'repo' and 'workflow' scopes, then re-run Setup.\n\n"
                              + "Vault repo: "
                              + newConfig.githubRepo);
                    } else {
                      showError("Setup Failed", msg);
                    }
                  });
            }));
    btns.addComponent(new Label("  "));
    btns.addComponent(new Button("Cancel", dlg::close));
    panel.addComponent(btns);

    dlg.setComponent(panel);
    gui.addWindow(dlg);
    gui.setActiveWindow(dlg);
  }

  // ── Loading window helper ─────────────────────────────────────────────────

  private void runWithLoading(
      String message, ThrowingRunnable action, Runnable onSuccess, Consumer<Exception> onError) {
    BasicWindow loadingWin = new BasicWindow();
    loadingWin.setHints(Set.of(Window.Hint.CENTERED, Window.Hint.MODAL));
    loadingWin.setComponent(Panels.vertical(new Label(message), new Label("Please wait...")));
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
    worker.setUncaughtExceptionHandler(
        (t, ex) -> {
          /* swallow — already handled above */
        });
    worker.start();
  }

  // ── Error / info helpers ──────────────────────────────────────────────────

  private void showError(String title, String message) {
    MessageDialog.showMessageDialog(gui, title, message, MessageDialogButton.OK);
  }

  private void showInfo(String title, String message) {
    MessageDialog.showMessageDialog(gui, title, message, MessageDialogButton.OK);
  }

  // ── Date formatting helper ────────────────────────────────────────────────

  private String formatUnlockDate(Instant decryptionDate) {
    java.time.ZonedDateTime zdt = decryptionDate.atZone(ZoneId.systemDefault());
    long days = ChronoUnit.DAYS.between(Instant.now(), decryptionDate);
    DateTimeFormatter fmt = DateTimeFormatter.ofPattern("MMM d, yyyy");
    if (days <= 0 && Instant.now().isBefore(decryptionDate)) {
      return fmt.format(zdt) + "  (< 1 day remaining)";
    }
    if (days <= 0) return "Unlocked on " + fmt.format(zdt);
    return fmt.format(zdt) + "  (" + days + " day" + (days == 1 ? "" : "s") + " remaining)";
  }

  // ── Secret list entry label helper ───────────────────────────────────────

  private String formatSecretEntry(Secret s) {
    int termWidth = 80;
    if (screen != null) {
      try {
        termWidth = screen.getTerminalSize().getColumns();
      } catch (Exception ignored) {
      }
    }

    String name = s.getName();
    if (name.length() > 22) name = name.substring(0, 20) + "..";
    String padded = String.format("%-24s", name);

    if (s.availableForDecryption()) {
      String left = "  ✓  " + padded;
      String right = "READY TO DECRYPT";
      int gap = Math.max(2, termWidth - left.length() - right.length() - 2);
      return left + " ".repeat(gap) + right;
    } else {
      String date =
          DateTimeFormatter.ofPattern("MMM d yyyy")
              .format(s.getDecryptionDate().atZone(ZoneId.systemDefault()));
      String timeStr = formatTimeRemaining(s.getDecryptionDate());
      String left = "  ✗  " + padded;
      String right = timeStr + "  (" + date + ")";
      int gap = Math.max(2, termWidth - left.length() - right.length() - 2);
      return left + " ".repeat(gap) + right;
    }
  }

  private String formatTimeRemaining(Instant decryptionDate) {
    long totalMinutes = ChronoUnit.MINUTES.between(Instant.now(), decryptionDate);
    if (totalMinutes <= 0) return "READY";
    long days = totalMinutes / (60 * 24);
    long hours = (totalMinutes % (60 * 24)) / 60;
    if (days > 0 && hours > 0) return days + "d " + hours + "h";
    if (days > 0) return days + "d";
    if (hours > 0) return hours + "h";
    return "< 1h";
  }

  // ── Helper: build main window panel (for post-setup rebuild) ─────────────

  private Panel buildMainWindowPanel() {
    Panel root = new Panel(new com.googlecode.lanterna.gui2.BorderLayout());

    // TOP: ASCII art header
    Panel header = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));
    String[] artLines = {
      "████████╗██╗███╗   ███╗███████╗███████╗ █████╗ ███████╗███████╗",
      "╚══██╔══╝██║████╗ ████║██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝",
      "   ██║   ██║██╔████╔██║█████╗  ███████╗███████║█████╗  █████╗  ",
      "   ██║   ██║██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║██╔══╝  ██╔══╝  ",
      "   ██║   ██║██║ ╚═╝ ██║███████╗███████║██║  ██║██║     ███████╗",
      "   ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝",
      "                  your secrets, locked in time."
    };
    for (int i = 0; i < artLines.length; i++) {
      Label line = new Label(artLines[i]);
      line.setForegroundColor(
          i < artLines.length - 1 ? TextColor.ANSI.CYAN : TextColor.ANSI.DEFAULT);
      header.addComponent(line);
    }
    root.addComponent(header, com.googlecode.lanterna.gui2.BorderLayout.Location.TOP);

    // CENTER: content (secrets list or message) — will fill available space
    mainContentPanel = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.VERTICAL));
    root.addComponent(mainContentPanel, com.googlecode.lanterna.gui2.BorderLayout.Location.CENTER);

    // BOTTOM: action buttons
    Panel buttons = new Panel(new LinearLayout(com.googlecode.lanterna.gui2.Direction.HORIZONTAL));
    if (vaultManager != null) {
      buttons.addComponent(
          new Button(
              "(A)dd Secret",
              () -> {
                showAddSecretDialog();
                rebuildSecretsList();
              }));
      buttons.addComponent(new Label("   "));
    }
    buttons.addComponent(new Button("(S)etup", this::showSetupDialog));
    buttons.addComponent(new Label("   "));
    buttons.addComponent(new Button("(Q)uit", mainWindow::close));
    root.addComponent(buttons, com.googlecode.lanterna.gui2.BorderLayout.Location.BOTTOM);

    rebuildSecretsList();
    return root;
  }
}
