# TimeSafe UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current multi-window overlay TUI with a Claude Code-inspired single-pane stack navigation UI: no ASCII art, clean list with colored status, inline navigation (list → detail → action, Esc goes back).

**Architecture:** A single `BasicWindow` with `FULL_SCREEN` hint is used throughout. A `Deque<NavEntry>` in `TimeSafeTui` stores the navigation stack. Each screen is a `Panel` plus a `WindowListener` for key handling; pushing navigates forward, popping (Esc) navigates back. `TimeSafeTui` implements the `NavigationController` interface so all panels can push/pop and access app state without circular imports.

**Tech Stack:** Java 21, Lanterna 3.1.2, JUnit 4, Gradle (`./gradlew`). Formatter: `./gradlew spotlessApply` (Google Java Format). Build: `./gradlew compileJava`. Tests: `./gradlew test`. Fat jar: `./gradlew shadowJar && mkdir -p vault && java -jar build/libs/time-safe-1.0-SNAPSHOT-all.jar`.

---

## Files

### New files
- `src/main/java/org/louis/ui/NavigationController.java` — interface: push/pop/quit/vault/config/saveConfig/runAsync/showRootStatus
- `src/main/java/org/louis/ui/UiColors.java` — TextColor constants (GREEN, ORANGE, RED, DIM, BLUE, BRIGHT)
- `src/main/java/org/louis/ui/UiComponents.java` — shared helpers: breadcrumb, sectionLabel, dimLabel, divider, singleLineInput, passwordInput, multiLineInput, formatDate
- `src/main/java/org/louis/ui/SecretsListPanel.java` — list view with custom ActionListBox renderer + countdown refresh
- `src/main/java/org/louis/ui/SecretDetailPanel.java` — detail view: metadata + d/e/x actions
- `src/main/java/org/louis/ui/DecryptPanel.java` — key entry + decrypted result
- `src/main/java/org/louis/ui/ExtendLockPanel.java` — extend lock form with live date preview
- `src/main/java/org/louis/ui/DeletePanel.java` — delete confirmation (y/Esc)
- `src/main/java/org/louis/ui/AddSecretPanel.java` — 3-step add flow (name → days → text)
- `src/main/java/org/louis/ui/SetupPanel.java` — config form (5 fields, Tab navigation)

### Modified files
- `src/main/java/org/louis/Secret.java` — add `createdAtIso` field + `getCreatedAt()` getter
- `src/main/java/org/louis/ui/TimeSafeTui.java` — full rewrite: implements NavigationController, navigation stack, no ASCII art, no multi-window
- `src/test/java/org/louis/SecretTest.java` — add test for `createdAt` round-trip

---

## Task 1: Add `createdAt` to `Secret`

**Files:**
- Modify: `src/main/java/org/louis/Secret.java`
- Modify: `src/test/java/org/louis/SecretTest.java`

- [ ] **Step 1: Add field and getter to `Secret`**

In `Secret.java`, after line `private String ivBase64;`:
```java
private String createdAtIso;
```

In the `public Secret(String name, Instant decryptionDate, byte[] iv)` constructor, after `this.ivBase64 = ...;`:
```java
this.createdAtIso = Instant.now().toString();
```

After the `getIv()` method:
```java
public Instant getCreatedAt() {
  return createdAtIso != null ? Instant.parse(createdAtIso) : getDecryptionDate();
}
```

The fallback to `getDecryptionDate()` handles old `.meta` files that don't have `createdAtIso` yet — Gson leaves it null when deserialising.

- [ ] **Step 2: Write a failing test in `SecretTest.java`**

Add this test after the existing `setDecryptionDatePersists` test:
```java
@Test
public void createdAtSurvivesRoundTrip() throws Exception {
  byte[] iv = EncryptDecrypt.generateIV();
  Secret s = new Secret("TestSecret", Instant.now().plus(7, ChronoUnit.DAYS), iv);
  Instant before = Instant.now().minusSeconds(1);

  s.saveMeta(dir());
  Secret loaded = Secret.loadMeta(dir(), s.getId());

  assertNotNull(loaded.getCreatedAt());
  assertTrue(!loaded.getCreatedAt().isBefore(before));
}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/pk/code/time-safe && ./gradlew test --tests "org.louis.SecretTest.createdAtSurvivesRoundTrip" -q
```
Expected: FAIL — `getCreatedAt()` does not exist yet.

- [ ] **Step 4: Run test to verify it passes**

After adding the code from Step 1:
```bash
./gradlew test --tests "org.louis.SecretTest" -q
```
Expected: all `SecretTest` tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/main/java/org/louis/Secret.java src/test/java/org/louis/SecretTest.java
git commit -m "feat: add createdAt field to Secret"
```

---

## Task 2: `NavigationController` interface and `UiColors`

**Files:**
- Create: `src/main/java/org/louis/ui/NavigationController.java`
- Create: `src/main/java/org/louis/ui/UiColors.java`

- [ ] **Step 1: Create `NavigationController.java`**

```java
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
```

- [ ] **Step 2: Create `UiColors.java`**

```java
package org.louis.ui;

import com.googlecode.lanterna.TextColor;

public final class UiColors {

  public static final TextColor GREEN  = new TextColor.RGB(76, 175, 80);
  public static final TextColor ORANGE = new TextColor.RGB(255, 152, 0);
  public static final TextColor RED    = new TextColor.RGB(244, 67, 54);
  public static final TextColor DIM    = TextColor.ANSI.WHITE;
  public static final TextColor BLUE   = new TextColor.RGB(92, 124, 250);
  public static final TextColor BRIGHT = TextColor.ANSI.WHITE_BRIGHT;

  private UiColors() {}
}
```

- [ ] **Step 3: Compile check**

```bash
./gradlew compileJava -q
```
Expected: BUILD SUCCESSFUL (new files compile; TimeSafeTui still unchanged).

- [ ] **Step 4: Commit**

```bash
git add src/main/java/org/louis/ui/NavigationController.java \
        src/main/java/org/louis/ui/UiColors.java
git commit -m "feat: add NavigationController interface and UiColors"
```

---

## Task 3: `UiComponents` helpers

**Files:**
- Create: `src/main/java/org/louis/ui/UiComponents.java`

- [ ] **Step 1: Create `UiComponents.java`**

```java
package org.louis.ui;

import com.googlecode.lanterna.TerminalSize;
import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.EmptySpace;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextBox;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

public final class UiComponents {

  private static final DateTimeFormatter DATE_FMT =
      DateTimeFormatter.ofPattern("yyyy-MM-dd").withZone(ZoneId.systemDefault());

  /** "‹ Parent" breadcrumb label in blue. */
  public static Label breadcrumb(String parentLabel) {
    Label l = new Label("‹ " + parentLabel);
    l.setForegroundColor(UiColors.BLUE);
    return l;
  }

  /** Dim section label (e.g. "Secrets — owner/repo"). */
  public static Label sectionLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.DIM);
    return l;
  }

  /** Plain dim label for hints and subtitles. */
  public static Label dimLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.DIM);
    return l;
  }

  /** Bright white label (headings, names). */
  public static Label brightLabel(String text) {
    Label l = new Label(text);
    l.setForegroundColor(UiColors.BRIGHT);
    return l;
  }

  /** Horizontal rule of em-dashes, given number of chars wide. */
  public static Label divider(int width) {
    return new Label("─".repeat(width));
  }

  /** Single-line text input. */
  public static TextBox singleLineInput(int width) {
    return new TextBox(new TerminalSize(width, 1));
  }

  /** Single-line password input (masked with *). */
  public static TextBox passwordInput(int width) {
    return new TextBox(new TerminalSize(width, 1)).setMask('*');
  }

  /** Multi-line text input. */
  public static TextBox multiLineInput(int width, int height) {
    return new TextBox(new TerminalSize(width, height), TextBox.Style.MULTI_LINE);
  }

  /** Format an Instant as yyyy-MM-dd in local time. */
  public static String formatDate(Instant instant) {
    return DATE_FMT.format(instant);
  }

  /** Compute the unlock date if locked for {@code days} from now. */
  public static String previewUnlockDate(int days) {
    return formatDate(Instant.now().plusSeconds((long) days * 86400));
  }

  /** Blank vertical spacer. */
  public static EmptySpace spacer() {
    return new EmptySpace(new TerminalSize(1, 1));
  }

  /** Build a simple two-column key/value row panel. */
  public static Panel fieldRow(String key, String value) {
    Panel row = new Panel(new LinearLayout(Direction.HORIZONTAL));
    Label keyLabel = new Label(String.format("%-12s", key));
    keyLabel.setForegroundColor(UiColors.DIM);
    Label valueLabel = new Label(value);
    row.addComponent(keyLabel);
    row.addComponent(valueLabel);
    return row;
  }

  private UiComponents() {}
}
```

- [ ] **Step 2: Compile check**

```bash
./gradlew compileJava -q
```
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/UiComponents.java
git commit -m "feat: add UiComponents shared helpers"
```

---

## Task 4: `SecretsListPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/SecretsListPanel.java`

Context: This is the home screen. It shows an `ActionListBox` with a custom `ComponentRenderer` that colors each item (green for ready, orange for <24h, dim for locked). It refreshes every second via `TimeSafeTui`'s countdown timer calling `panel.refreshTimes()`. Window listener handles `a` (add), `s` (setup), `q` (quit).

- [ ] **Step 1: Create `SecretsListPanel.java`**

```java
package org.louis.ui;

import com.googlecode.lanterna.TerminalSize;
import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.gui2.ActionListBox;
import com.googlecode.lanterna.gui2.ComponentRenderer;
import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.EmptySpace;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.LinearLayout;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.TextGUIGraphics;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListenerAdapter;
import com.googlecode.lanterna.input.KeyStroke;
import com.googlecode.lanterna.input.KeyType;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.louis.Secret;

public class SecretsListPanel {

  private final NavigationController nav;
  private Panel panel;
  private ActionListBox listBox;
  private List<Secret> cachedSecrets = new ArrayList<>();
  private Label statusLine;

  public SecretsListPanel(NavigationController nav) {
    this.nav = nav;
  }

  // Called by the window to display the panel for the first time.
  public Panel build() {
    panel = new Panel(new LinearLayout(Direction.VERTICAL));

    String repo =
        nav.config() != null ? "Secrets — " + nav.config().githubRepo : "Secrets";
    panel.addComponent(UiComponents.sectionLabel(repo));
    panel.addComponent(UiComponents.spacer());

    rebuildList();

    statusLine = new Label("");
    panel.addComponent(statusLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("↵ open   a add   s setup   q quit"));

    return panel;
  }

  public WindowListener buildListener() {
    return new WindowListenerAdapter() {
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getCharacter() == null) return;
        switch (Character.toLowerCase(k.getCharacter())) {
          case 'a':
            if (nav.vault() != null) {
              consumed.set(true);
              new AddSecretPanel(nav).show();
            }
            break;
          case 's':
            consumed.set(true);
            new SetupPanel(nav).show();
            break;
          case 'q':
            consumed.set(true);
            nav.quit();
            break;
          default:
            break;
        }
      }
    };
  }

  /**
   * Called by the countdown timer every second. Updates the displayed time
   * without rebuilding the whole panel — just clears and re-adds items,
   * preserving selection.
   */
  public void refreshTimes() {
    if (listBox == null || cachedSecrets.isEmpty()) return;
    int selected = listBox.getSelectedIndex();
    listBox.clearItems();
    for (Secret s : cachedSecrets) {
      listBox.addItem("", () -> openDetail(s));
    }
    if (selected >= 0 && selected < listBox.getItemCount()) {
      listBox.setSelectedIndex(selected);
    }
    // Invalidate so the renderer repaints
    listBox.invalidate();
  }

  /** Show a transient status message at the bottom of the list. */
  public void showStatus(String message, boolean isError) {
    if (statusLine == null) return;
    statusLine.setText(message);
    statusLine.setForegroundColor(isError ? UiColors.RED : UiColors.GREEN);
  }

  private void rebuildList() {
    listBox = null;
    cachedSecrets.clear();

    if (nav.vault() == null) {
      panel.addComponent(UiComponents.dimLabel("No config found — press s to open Setup."));
      return;
    }

    cachedSecrets = new ArrayList<>(nav.vault().getSecrets());

    if (cachedSecrets.isEmpty()) {
      panel.addComponent(UiComponents.dimLabel("No secrets yet — press a to add one."));
      return;
    }

    listBox = new ActionListBox();
    for (Secret s : cachedSecrets) {
      listBox.addItem("", () -> openDetail(s));
    }
    listBox.setRenderer(buildListRenderer());
    panel.addComponent(listBox);
  }

  private void openDetail(Secret s) {
    new SecretDetailPanel(nav, s).show();
  }

  private ComponentRenderer<ActionListBox> buildListRenderer() {
    List<Secret> secrets = cachedSecrets; // captured reference — same list mutated by refreshTimes
    return new ComponentRenderer<ActionListBox>() {
      @Override
      public TerminalSize getPreferredSize(ActionListBox component) {
        return new TerminalSize(70, Math.max(1, secrets.size()));
      }

      @Override
      public void drawComponent(TextGUIGraphics graphics, ActionListBox component) {
        TerminalSize size = component.getSize();
        int selectedIdx = component.getSelectedIndex();
        boolean focused = component.isFocused();

        for (int row = 0; row < Math.min(secrets.size(), size.getRows()); row++) {
          Secret s = secrets.get(row);
          boolean selected = row == selectedIdx;

          // Row background
          if (selected) {
            graphics.setBackgroundColor(
                focused ? new TextColor.RGB(25, 35, 65) : new TextColor.RGB(30, 30, 30));
          } else {
            graphics.setBackgroundColor(TextColor.ANSI.DEFAULT);
          }

          // Blank the row
          graphics.drawLine(0, row, size.getColumns() - 1, row, ' ');

          // Name column (28 chars)
          String name = s.getName();
          if (name.length() > 26) name = name.substring(0, 24) + "..";
          String paddedName = String.format("%-28s", name);
          graphics.setForegroundColor(selected ? UiColors.BRIGHT : TextColor.ANSI.WHITE);
          graphics.putString(0, row, paddedName);

          // Status column
          String statusText;
          TextColor statusColor;
          if (s.availableForDecryption()) {
            statusText = "● ready";
            statusColor = UiColors.GREEN;
          } else {
            long secs =
                ChronoUnit.SECONDS.between(Instant.now(), s.getDecryptionDate());
            statusText = formatTimeRemaining(s.getDecryptionDate());
            statusColor = secs < 86400L ? UiColors.ORANGE : UiColors.DIM;
          }
          graphics.setForegroundColor(statusColor);
          int statusCol = Math.min(30, Math.max(0, size.getColumns() - statusText.length() - 2));
          graphics.putString(statusCol, row, statusText);

          // Reset
          graphics.setBackgroundColor(TextColor.ANSI.DEFAULT);
          graphics.setForegroundColor(TextColor.ANSI.DEFAULT);
        }
      }
    };
  }

  private static String formatTimeRemaining(Instant decryptionDate) {
    long total = ChronoUnit.SECONDS.between(Instant.now(), decryptionDate);
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
```

- [ ] **Step 2: Compile check** (will fail because `AddSecretPanel`, `SetupPanel`, `SecretDetailPanel` don't exist yet — that's expected)

```bash
./gradlew compileJava -q 2>&1 | grep -v "^$"
```
Expected: errors referencing `AddSecretPanel`, `SetupPanel`, `SecretDetailPanel`. No other errors.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/SecretsListPanel.java
git commit -m "feat: add SecretsListPanel with colored ActionListBox renderer"
```

---

## Task 5: `SecretDetailPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/SecretDetailPanel.java`

Context: Detail view for a single secret. Shows metadata and action shortcuts. The spec shows `d` decrypt, `e` extend lock, `x` delete; Esc goes back. If the secret is not yet ready, `d` shows an inline error label instead of navigating.

- [ ] **Step 1: Create `SecretDetailPanel.java`**

```java
package org.louis.ui;

import com.googlecode.lanterna.gui2.Direction;
import com.googlecode.lanterna.gui2.EmptySpace;
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
    panel.addComponent(UiComponents.fieldRow("created", UiComponents.formatDate(secret.getCreatedAt())));
    panel.addComponent(UiComponents.fieldRow("unlocked", UiComponents.formatDate(secret.getDecryptionDate())));
    String shortId = secret.getId().length() > 8
        ? secret.getId().substring(0, 8) + "…"
        : secret.getId();
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

  private WindowListener buildListener() {
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
              errorLine.setText("Not unlocked until " + UiComponents.formatDate(secret.getDecryptionDate()));
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
    long total = java.time.temporal.ChronoUnit.SECONDS.between(
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
```

- [ ] **Step 2: Compile check** (will still fail on `DecryptPanel`, `ExtendLockPanel`, `DeletePanel`)

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: errors for `DecryptPanel`, `ExtendLockPanel`, `DeletePanel` only.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/SecretDetailPanel.java
git commit -m "feat: add SecretDetailPanel"
```

---

## Task 6: `DecryptPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/DecryptPanel.java`

Context: Two sub-screens handled in one class. Step 1: text input for the base64 key. Enter submits (via InputFilter). Step 2: if decryption succeeds, replaces the input view with a read-only result view. If it fails, shows an error inline and lets the user correct the key. Esc always goes back to detail.

- [ ] **Step 1: Create `DecryptPanel.java`**

```java
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

  private WindowListener buildInputListener() {
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

  private WindowListener buildResultListener() {
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
```

Note: `runAsync` above needs to return a value (the decrypted plaintext). Update `NavigationController` in Task 2 to add an overload:

```java
// Add this overload to NavigationController.java (after the existing runAsync):
<T> void runAsync(
    String loadingMessage,
    ThrowingSupplier<T> action,
    java.util.function.Consumer<T> onSuccess,
    java.util.function.Consumer<Exception> onError);

@FunctionalInterface
interface ThrowingSupplier<T> {
  T get() throws Exception;
}
```

- [ ] **Step 2: Update `NavigationController.java` to add `ThrowingSupplier` overload**

Add to `NavigationController.java` after the existing `runAsync` method:

```java
<T> void runAsync(
    String loadingMessage,
    ThrowingSupplier<T> action,
    java.util.function.Consumer<T> onSuccess,
    java.util.function.Consumer<Exception> onError);

@FunctionalInterface
interface ThrowingSupplier<T> {
  T get() throws Exception;
}
```

- [ ] **Step 3: Compile check**

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: errors for `ExtendLockPanel`, `DeletePanel` only (and `AddSecretPanel`, `SetupPanel` from SecretsListPanel).

- [ ] **Step 4: Commit**

```bash
git add src/main/java/org/louis/ui/DecryptPanel.java \
        src/main/java/org/louis/ui/NavigationController.java
git commit -m "feat: add DecryptPanel with key entry and result screens"
```

---

## Task 7: `ExtendLockPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/ExtendLockPanel.java`

Context: Single-line numeric input for additional days. A live preview label shows the computed unlock date as the user types. Enter submits. Esc goes back to detail without changes.

- [ ] **Step 1: Create `ExtendLockPanel.java`**

```java
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
```

- [ ] **Step 2: Compile check**

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: errors for `DeletePanel`, `AddSecretPanel`, `SetupPanel` only.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/ExtendLockPanel.java
git commit -m "feat: add ExtendLockPanel with live date preview"
```

---

## Task 8: `DeletePanel`

**Files:**
- Create: `src/main/java/org/louis/ui/DeletePanel.java`

Context: No text input. Just a confirmation message. `y` confirms and triggers delete. Esc cancels. On success, pops to root and refreshes. On error (partial GitHub failure), pops to root with an error status message.

- [ ] **Step 1: Create `DeletePanel.java`**

```java
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
```

- [ ] **Step 2: Compile check**

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: errors for `AddSecretPanel`, `SetupPanel` only.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/DeletePanel.java
git commit -m "feat: add DeletePanel"
```

---

## Task 9: `AddSecretPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/AddSecretPanel.java`

Context: Three-step flow. Each step is a separate `push`. Going back (Esc) pops to the previous step, preserving entered data in instance fields. Step 3 uses a multi-line TextBox; Ctrl+Enter submits (window listener checks `isCtrlDown() && KeyType.Enter`). On success, `nav.popToRoot()` and the list refreshes showing the new item.

- [ ] **Step 1: Create `AddSecretPanel.java`**

```java
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
            nav.push(buildStep2Panel(errorLine), buildStep2Listener());
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

  private WindowListener buildStep1Listener() {
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

  private Panel buildStep2Panel(Label ignoredError) {
    TextBox daysBox = UiComponents.singleLineInput(10);
    if (savedDays > 0) daysBox.setText(String.valueOf(savedDays));

    Label previewLabel = new Label(
        savedDays > 0 ? "Unlocks on " + UiComponents.previewUnlockDate(savedDays) : "Unlocks on —");
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
            nav.push(buildStep3Panel(), buildStep3Listener());
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

  private WindowListener buildStep2Listener() {
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

  // ── Step 3: Secret text ──────────────────────────────────────────────────────

  private Panel buildStep3Panel() {
    TextBox secretBox = UiComponents.multiLineInput(60, 8);
    Label errorLine = new Label("");
    errorLine.setForegroundColor(UiColors.RED);

    Panel panel = new Panel(new LinearLayout(Direction.VERTICAL));
    panel.addComponent(UiComponents.breadcrumb("Secrets"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Add secret — step 3 of 3"));
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Secret text"));
    panel.addComponent(secretBox);
    panel.addComponent(UiComponents.dimLabel("This will be encrypted."));
    panel.addComponent(errorLine);
    panel.addComponent(UiComponents.spacer());
    panel.addComponent(UiComponents.dimLabel("Ctrl+Enter save   Esc back"));
    return panel;
  }

  private WindowListener buildStep3Listener() {
    return new WindowListenerAdapter() {
      // Need access to secretBox — use a field
      // This is awkward because the TextBox is built in buildStep3Panel.
      // Solution: pass secretBox as a captured variable via a local class.
      // This listener accesses the window's components via the panel reference.
      // Instead, capture secretBox by making it a field:
      // See NOTE below — secretBox must be captured. Refactor: store it as a field
      // or use a local helper class.
      @Override
      public void onUnhandledInput(Window w, KeyStroke k, AtomicBoolean consumed) {
        if (k.getKeyType() == KeyType.Escape) {
          consumed.set(true);
          nav.pop(); // back to step 2
        }
      }
    };
  }
}
```

**NOTE:** The Ctrl+Enter handler for step 3 needs access to the `secretBox` TextBox. The cleanest solution is to refactor `buildStep3Panel()` to return both the `Panel` and the `TextBox` together, then build the window listener capturing the TextBox reference. Replace the `buildStep3Panel()` + `buildStep3Listener()` calls with:

```java
// Inside showStep2() (the Enter handler that goes to step 3):
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

WindowListener step3Listener = new WindowListenerAdapter() {
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
            nav.showRootStatus("✓ " + savedName + " locked until "
                + UiComponents.previewUnlockDate(savedDays), false);
          },
          ex -> errorLine3.setText("✗ " + ex.getMessage()));
    }
  }
};

nav.push(step3Panel, step3Listener);
```

Rewrite `AddSecretPanel.java` incorporating this inlined approach: instead of separate `buildStep3Panel()` / `buildStep3Listener()` methods, inline step 3 construction inside the step 2 Enter handler (the same pattern used for step 1 → step 2 transition). Delete the separate `buildStep3Panel()` and `buildStep3Listener()` methods and the incomplete listener stub.

- [ ] **Step 2: Compile check**

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: error for `SetupPanel` only.

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/AddSecretPanel.java
git commit -m "feat: add AddSecretPanel 3-step flow"
```

---

## Task 10: `SetupPanel`

**Files:**
- Create: `src/main/java/org/louis/ui/SetupPanel.java`

Context: Five fields pre-populated from existing config. Tab moves between fields (Lanterna default). Enter on any field triggers save (via InputFilter). Esc cancels. On success, calls `nav.applyConfig(...)` which updates the vault reference, then `nav.popToRoot()`.

- [ ] **Step 1: Create `SetupPanel.java`**

```java
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
import org.louis.Config;
import org.louis.GitHubVault;

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

    if (pat.isEmpty() || repo.isEmpty() || delivery.isEmpty()
        || smtpUser.isEmpty() || smtpPass.isEmpty()) {
      errorLine.setText("All fields are required.");
      return;
    }

    Config newConfig = new Config();
    newConfig.githubToken = pat;
    newConfig.githubRepo = repo;
    newConfig.deliveryEmail = delivery;
    newConfig.smtpUser = smtpUser;
    newConfig.smtpPass = smtpPass;

    boolean isNewRepo = nav.config() == null
        || !repo.equals(nav.config().githubRepo);

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
```

- [ ] **Step 2: Compile check**

```bash
./gradlew compileJava -q 2>&1 | grep "error:"
```
Expected: all compilation errors should now be only in `TimeSafeTui.java` (which still has the old code and doesn't implement `NavigationController`).

- [ ] **Step 3: Commit**

```bash
git add src/main/java/org/louis/ui/SetupPanel.java
git commit -m "feat: add SetupPanel"
```

---

## Task 11: Rewrite `TimeSafeTui`

**Files:**
- Modify: `src/main/java/org/louis/ui/TimeSafeTui.java` — full rewrite

Context: `TimeSafeTui` implements `NavigationController`. It owns the `BasicWindow`, the nav stack (`Deque<NavEntry>`), the countdown timer, and the `SecretsListPanel` instance. All multi-window / overlay code is removed. The class is now ~180 lines.

- [ ] **Step 1: Write the new `TimeSafeTui.java`** (completely replaces existing content)

```java
package org.louis.ui;

import com.googlecode.lanterna.TextColor;
import com.googlecode.lanterna.gui2.BasicWindow;
import com.googlecode.lanterna.gui2.DefaultWindowManager;
import com.googlecode.lanterna.gui2.EmptySpace;
import com.googlecode.lanterna.gui2.MultiWindowTextGUI;
import com.googlecode.lanterna.gui2.Panel;
import com.googlecode.lanterna.gui2.Panels;
import com.googlecode.lanterna.gui2.Window;
import com.googlecode.lanterna.gui2.WindowListener;
import com.googlecode.lanterna.gui2.dialogs.MessageDialog;
import com.googlecode.lanterna.gui2.dialogs.MessageDialogButton;
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

    gui = new MultiWindowTextGUI(
        screen,
        new DefaultWindowManager(),
        new EmptySpace(TextColor.ANSI.BLACK));

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
        Set.of(Window.Hint.FULL_SCREEN, Window.Hint.NO_DECORATIONS, Window.Hint.FIT_TERMINAL_WINDOW));

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
    loadingWin.setComponent(Panels.vertical(
        new com.googlecode.lanterna.gui2.Label(loadingMessage),
        new com.googlecode.lanterna.gui2.Label("Please wait…")));
    gui.addWindow(loadingWin);

    Thread worker = new Thread(() -> {
      try {
        action.run();
        gui.getGUIThread().invokeLater(() -> {
          loadingWin.close();
          onSuccess.run();
        });
      } catch (Exception e) {
        gui.getGUIThread().invokeLater(() -> {
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
    loadingWin.setComponent(Panels.vertical(
        new com.googlecode.lanterna.gui2.Label(loadingMessage),
        new com.googlecode.lanterna.gui2.Label("Please wait…")));
    gui.addWindow(loadingWin);

    Thread worker = new Thread(() -> {
      try {
        T result = action.get();
        gui.getGUIThread().invokeLater(() -> {
          loadingWin.close();
          onSuccess.accept(result);
        });
      } catch (Exception e) {
        gui.getGUIThread().invokeLater(() -> {
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
    Thread t = new Thread(() -> {
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
```

- [ ] **Step 2: Compile check — should now be clean**

```bash
./gradlew compileJava -q
```
Expected: BUILD SUCCESSFUL with no errors.

- [ ] **Step 3: Run all tests**

```bash
./gradlew test -q
```
Expected: BUILD SUCCESSFUL (all tests still pass — Secret tests are unaffected).

- [ ] **Step 4: Commit**

```bash
git add src/main/java/org/louis/ui/TimeSafeTui.java
git commit -m "feat: rewrite TimeSafeTui with NavigationController stack navigation"
```

---

## Task 12: Format, final integration check, and cleanup

- [ ] **Step 1: Apply formatter**

```bash
./gradlew spotlessApply -q
```
Expected: completes without errors (Google Java Format applied to all modified files).

- [ ] **Step 2: Compile after formatting**

```bash
./gradlew compileJava -q
```
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Run all tests**

```bash
./gradlew test -q
```
Expected: BUILD SUCCESSFUL — all tests pass.

- [ ] **Step 4: Build fat jar and smoke-test manually**

```bash
./gradlew shadowJar -q && mkdir -p vault && java -jar build/libs/time-safe-1.0-SNAPSHOT-all.jar
```

Verify:
- Home screen shows `Secrets — <repo>` label (or `Secrets` if unconfigured) with no ASCII art
- Arrow keys navigate the list; Enter opens detail view
- Detail view shows metadata and action keys; Esc returns to list
- `a` opens Add Secret step 1 of 3; Esc goes back through steps
- `s` opens Setup; Esc cancels without saving
- `q` exits cleanly

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "style: apply Google Java Format to UI redesign"
```

---

## Notes for implementer

**Lanterna API details to verify at implementation time:**
- `ActionListBox.setRenderer(ComponentRenderer<ActionListBox>)` — confirm the exact method name (may be `setRenderer` or `withRenderer`). In Lanterna 3.1.2, `AbstractComponent<T>` has `public T setRenderer(ComponentRenderer<T>)`.
- `TextBox.setReadOnly(boolean)` — confirm this method exists. If not, use `textBox.setEnabled(false)` or set the InputFilter to reject all keys.
- `graphics.drawLine(col1, row, col2, row, char)` — for filling a row background. Alternatively use `graphics.fillRectangle(new TerminalPosition(0, row), new TerminalSize(cols, 1), ' ')`.
- `WindowListener.removeWindowListener` — `BasicWindow` inherits from `AbstractBasePane`. Confirm it has `removeWindowListener(WindowListener)`.

**Key security constraint (do not violate):**
The AES decryption key is NEVER fetched from GitHub — only delivered via the scheduled GitHub Actions email. The `DecryptPanel` only takes user-pasted input; it never calls any GitHub API to retrieve keys.

**`popToRoot` rebuild note:**
`SecretsListPanel.refresh()` calls `panel.removeAllComponents()` and rebuilds from scratch. This means the `Panel` object returned by the first `build()` call is mutated in-place. The `mainWindow.setComponent(currentPanel)` call in `popToRoot()` re-sets the same panel object (which has been rebuilt). This is intentional — no new Panel object is needed.
