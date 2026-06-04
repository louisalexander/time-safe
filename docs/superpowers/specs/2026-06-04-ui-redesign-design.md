# TimeSafe UI Redesign — Design Spec

## Goal

Replace the current Lanterna TUI with a Claude Code-inspired minimal aesthetic: no ASCII art banner, clean monospace list, color status indicators, and single-pane stack navigation (list → detail → action, Esc to go back one level).

## Decisions Made

| Question | Decision |
|---|---|
| Aesthetic | Full Claude Code minimal (Option A) |
| Action presentation | Inline single-pane stack (no overlays) |
| Status indicators | Color: green ready, orange soon, gray locked |
| Header / branding | None — section label carries repo context |
| Navigation model | Single-pane stack, Esc always goes back one level |

---

## Screens

### 1. Secrets List (home)

```
Secrets — owner/repo-name

›  Journal 2026              ● ready
   Will & Testament          47d 12h 08m
   Bitcoin seed               2h 14m 33s
   Love letter               365d  0h 00m

↵ open   a add   s setup   q quit
```

- Section label shows `Secrets — <githubRepo>` from config; falls back to `Secrets` if config not loaded
- Each row: `›` cursor on selected item, secret name (left-aligned), status (right-aligned)
- Status colors:
  - **Green** `● ready` — `availableForDecryption()` is true
  - **Orange** `Xh Xm Xs` — less than 24 hours remaining
  - **Default/gray** `Xd Xh Xm` — more than 24 hours remaining
- Countdown refreshes every second in-place (no full redraw)
- Empty state: `No secrets yet.` on a single line followed by the hints bar
- `a` → Add Secret flow; `s` → Setup flow; `q` → quit (stops refresh thread, exits)
- `Enter` or `↓`/`↑` to navigate and open

### 2. Secret Detail

```
‹ Secrets

Journal 2026
● ready to decrypt

created     2025-12-01
unlocked    2026-06-01
id          a3f8c2d1-…

────────────────────────

d  Decrypt
e  Extend lock
x  Delete

Esc back
```

- Breadcrumb `‹ Secrets` at top
- Secret name in bright white, status line below it
- Metadata fields: `created` (date secret was first locked — requires adding `createdAtIso` String field to `Secret`, set in constructor to `Instant.now().toString()`, never mutated by extend-lock), `unlocked` (decryption date), `id` (UUID truncated to 8 chars + `…`)
- Horizontal rule separates metadata from actions
- Actions listed as `key  Label`; Delete is red
- If secret is **not yet ready**, `d  Decrypt` is shown in gray/disabled color and pressing `d` shows an inline error: `Not unlocked until <date>` — no navigation occurs
- `Esc` returns to Secrets list

### 3a. Decrypt — Key Entry

```
‹ Journal 2026

Decryption key (base64)
┌─────────────────────────────────────────┐
│ dGhpcyBpcy…█                            │
└─────────────────────────────────────────┘

Enter decrypt   Esc back
```

- Only reachable when secret is ready (`availableForDecryption()` true)
- Single-line text input with Lanterna `TextBox`
- `Enter` submits; empty input does nothing
- `Esc` returns to Secret Detail without decrypting

### 3b. Decrypted Result

```
‹ Journal 2026

✓ decrypted

┌─────────────────────────────────────────┐
│ Dear future self,                       │
│                                         │
│ If you're reading this, a whole year    │
│ has passed…                             │
└─────────────────────────────────────────┘

Esc back
```

- Decrypted text shown in a read-only scrollable box (green tint border)
- If decryption fails (wrong key): show `✗ decryption failed` in red instead of the box; `Esc` goes back to key entry so user can retry
- `Esc` returns to Secret Detail

### 4. Extend Lock

```
‹ Journal 2026

Additional days to lock

┌──────────┐
│ 30█      │
└──────────┘
Unlocks on 2026-07-04

Enter confirm   Esc back
```

- Numeric-only input; non-digit keystrokes ignored
- Preview line below input shows computed unlock date as user types
- If secret is already past unlock date, extension is from today; if still locked, extension is from the current decryption date (matching existing `updateSecret` logic)
- `Enter` with a valid positive integer calls `VaultManager.updateSecret`, shows inline `✓ lock extended to <date>` for 1.5 seconds, then returns to Secret Detail
- `Esc` returns to Secret Detail without changes

### 5. Delete Confirmation

```
‹ Journal 2026

Delete "Journal 2026"?

This will remove the encrypted file, metadata,
key, and GitHub Actions workflow. This cannot
be undone.

y confirm   Esc cancel
```

- No text input required — just `y` to confirm or `Esc` to cancel
- On confirm: calls `VaultManager.delete`, returns to Secrets list
- On error: shows `✗ delete failed: <message>` in red, `Esc` to go back

### 6. Add Secret (3-step flow)

**Step 1 — Name**
```
‹ Secrets

Add secret — step 1 of 3

Secret name
┌─────────────────────────────────────────┐
│ █                                       │
└─────────────────────────────────────────┘
A label for this secret.

Enter next   Esc cancel
```

**Step 2 — Lock duration**
```
‹ Secrets

Add secret — step 2 of 3

Lock for how many days?
┌──────────┐
│ 365█     │
└──────────┘
Unlocks on 2027-06-04

Enter next   Esc back
```

- Preview updates live as user types
- `Esc` goes back to step 1 (preserving the entered name)

**Step 3 — Secret text**
```
‹ Secrets

Add secret — step 3 of 3

Secret text
┌─────────────────────────────────────────┐
│ Dear future self…                       │
│ █                                       │
└─────────────────────────────────────────┘
This will be encrypted.

Ctrl+Enter save   Esc back
```

- Multi-line `TextBox`
- `Ctrl+Enter` submits — implemented via a `WindowListenerAdapter.onUnhandledInput` that checks `keyStroke.isCtrlDown() && keyStroke.getKeyType() == KeyType.Enter`; `Esc` goes back to step 2 (preserving name and days)
- On save: calls `VaultManager.putSecret`, returns to Secrets list with cursor on the new item; shows `✓ <name> locked until <date>` status line for 1.5 seconds
- On error: shows `✗ failed: <message>` in red, stays on step 3

### 7. Setup

```
‹ Secrets

Setup

GitHub token
┌─────────────────────────────────────────┐
│ ghp_████████████████████                │
└─────────────────────────────────────────┘

GitHub repo  (owner/repo)
┌─────────────────────────────────────────┐
│ louisalexander/time-safe-vault          │
└─────────────────────────────────────────┘

Delivery email
┌─────────────────────────────────────────┐
│ louis.alexander@gmail.com               │
└─────────────────────────────────────────┘

SMTP user
┌─────────────────────────────────────────┐
│ vault@gmail.com                         │
└─────────────────────────────────────────┘

SMTP password
┌─────────────────────────────────────────┐
│ ████████████                            │
└─────────────────────────────────────────┘

Tab next field   Enter save   Esc cancel
```

- Fields pre-populated from existing `Config` if present
- GitHub token and SMTP password fields mask characters with `*`
- `Tab` / `Shift+Tab` move between fields
- `Enter` saves config and optionally calls `github.initRepo()` if repo is new, returns to Secrets list
- `Esc` discards changes

---

## Architecture

### Navigation Model

Replace the current multi-window approach with a single `Panel` swapped in and out inside one `BasicWindow`. A navigation stack (`Deque<Panel>`) tracks history:

- `push(panel)` — replace current content, push previous onto stack
- `pop()` — pop stack, replace content with previous panel (triggered by Esc)

This avoids Lanterna's multi-window z-order issues and gives natural Esc-to-back behavior.

### Color Palette

```java
TextColor GREEN  = new TextColor.RGB(76, 175, 80);   // ● ready
TextColor ORANGE = new TextColor.RGB(255, 152, 0);   // soon
TextColor RED    = new TextColor.RGB(244, 67, 54);   // error / delete
TextColor DIM    = TextColor.ANSI.WHITE;             // countdown, dim labels (renders as gray)
TextColor BLUE   = new TextColor.RGB(92, 124, 250);  // cursor ›, key hints, breadcrumb
TextColor BRIGHT = TextColor.ANSI.WHITE_BRIGHT;      // selected item name, headings
```

Note: `TextColor.ANSI` values are enum constants, not constructed with `new`. `RGB` values are constructed with `new TextColor.RGB(r, g, b)`.

### Countdown Timer

Unchanged from current: daemon thread, 1-second sleep, `gui.getGUIThread().invokeLater()`. Only runs when the secrets list panel is active; paused/no-op when other panels are shown (check active panel before updating).

### File Structure

The single `TimeSafeTui.java` file will be split into focused classes:

- `TimeSafeTui.java` — entry point, GUI init, navigation stack, countdown timer
- `ui/SecretsListPanel.java` — secrets list view
- `ui/SecretDetailPanel.java` — detail view
- `ui/DecryptPanel.java` — key entry + result view
- `ui/ExtendLockPanel.java` — extend lock form
- `ui/DeletePanel.java` — delete confirmation
- `ui/AddSecretPanel.java` — 3-step add flow
- `ui/SetupPanel.java` — setup/config form
- `ui/UiColors.java` — color constants
- `ui/UiComponents.java` — shared helpers (styledInput, hintBar, breadcrumb, divider)

Each panel receives a `NavigationController` interface:

```java
interface NavigationController {
    void push(Panel panel);
    void pop();
    VaultManager vault();
    Config config();
    void saveConfig(Config c);
}
```

---

## Out of Scope

- Mouse support
- Resizable terminal handling (fixed-width layout is acceptable)
- Multi-line secret display pagination (scrollable TextBox is sufficient)
- Dark/light theme switching
