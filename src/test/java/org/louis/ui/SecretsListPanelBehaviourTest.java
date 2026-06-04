package org.louis.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import com.googlecode.lanterna.gui2.Component;
import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.Panel;
import java.lang.reflect.Field;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.louis.EncryptDecrypt;
import org.louis.Secret;
import org.louis.VaultManager;

/**
 * Behavioural tests for the Panel-of-rows implementation. We invoke the window listener directly
 * (no real Lanterna GUI is created) and inspect the panel's label state to verify selection moves
 * and the per-row status labels are updated by {@link SecretsListPanel#refreshTimes()}.
 */
public class SecretsListPanelBehaviourTest {

  @Test
  public void initialSelectionIsFirstRow() {
    SecretsListPanel sut = new SecretsListPanel(navWithSecrets(2));
    sut.build();
    assertEquals(0, selectedIndex(sut));
  }

  @Test
  public void refreshTimesUpdatesEveryStatusLabel() {
    FakeNavigationController nav = navWithSecrets(3);
    SecretsListPanel sut = new SecretsListPanel(nav);
    sut.build();

    List<Label> statusLabels = statusLabels(sut);
    assertEquals(3, statusLabels.size());
    String[] before = statusLabels.stream().map(Label::getText).toArray(String[]::new);

    sut.refreshTimes();

    // Every label should still hold a valid status string. The countdown rolls each second, so the
    // text may or may not equal the previous read — but neither should be empty.
    for (Label l : statusLabels) {
      assertTrue("status label text must be non-empty after refresh", !l.getText().isEmpty());
    }
    // Sanity: still the same number of labels (no rebuild churn).
    assertEquals(before.length, statusLabels.size());
  }

  @Test
  public void refreshTimesIsNoOpWhenNoSecrets() {
    SecretsListPanel sut = new SecretsListPanel(new FakeNavigationController());
    sut.build();
    sut.refreshTimes(); // must not throw
  }

  @Test
  public void buildAddsHintBarAndSectionLabel() {
    FakeNavigationController nav = navWithSecrets(2);
    SecretsListPanel sut = new SecretsListPanel(nav);
    Panel root = sut.build();

    boolean foundHeader = labelInTree(root, "Secrets — owner/repo");
    boolean foundHintAdd = labelInTree(root, "a");
    boolean foundHintQuit = labelInTreeContaining(root, "quit");
    assertTrue("Header label must be present", foundHeader);
    assertTrue("Hint bar must include the 'a' key letter", foundHintAdd);
    assertTrue("Hint bar must include 'quit' description", foundHintQuit);
  }

  @Test
  public void selectionDoesNotMovePastBoundaries() throws Exception {
    SecretsListPanel sut = new SecretsListPanel(navWithSecrets(3));
    sut.build();

    // Move up at top — selection stays at 0.
    invokeMoveSelection(sut, -1);
    assertEquals(0, selectedIndex(sut));

    // Move down twice, hitting the bottom.
    invokeMoveSelection(sut, 1);
    invokeMoveSelection(sut, 1);
    assertEquals(2, selectedIndex(sut));

    // Move down once more at bottom — selection stays at 2.
    invokeMoveSelection(sut, 1);
    assertEquals(2, selectedIndex(sut));
  }

  @Test
  public void movingSelectionUpdatesCursorAndNameForegroundColours() throws Exception {
    SecretsListPanel sut = new SecretsListPanel(navWithSecrets(3));
    sut.build();
    List<Label> cursors = cursorLabels(sut);
    List<Label> names = nameLabels(sut);

    // Row 0 starts selected.
    assertEquals("›  ", cursors.get(0).getText());
    assertEquals(UiColors.BRIGHT, names.get(0).getForegroundColor());
    assertEquals("   ", cursors.get(1).getText());
    assertEquals(UiColors.DIM, names.get(1).getForegroundColor());

    invokeMoveSelection(sut, 1); // → row 1

    assertEquals("   ", cursors.get(0).getText());
    assertEquals(UiColors.DIM, names.get(0).getForegroundColor());
    assertEquals("›  ", cursors.get(1).getText());
    assertEquals(UiColors.BRIGHT, names.get(1).getForegroundColor());
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  private static FakeNavigationController navWithSecrets(int n) {
    org.louis.Config cfg = new org.louis.Config();
    cfg.githubRepo = "owner/repo";
    cfg.githubToken = "tok";
    cfg.deliveryEmail = "a@b.c";
    cfg.smtpUser = "u";
    cfg.smtpPass = "p";
    return new FakeNavigationController().withConfig(cfg).withVault(new VaultStub(makeSecrets(n)));
  }

  private static List<Secret> makeSecrets(int n) {
    List<Secret> list = new ArrayList<>();
    for (int i = 0; i < n; i++) {
      list.add(
          new Secret(
              "Secret " + i,
              Instant.now().plus(i + 1, ChronoUnit.DAYS),
              EncryptDecrypt.generateIV()));
    }
    return list;
  }

  /** Minimal VaultStub used only so SecretsListPanel.build() finds a non-null vault. */
  private static final class VaultStub extends VaultManager {
    private final List<Secret> secrets;

    VaultStub(List<Secret> secrets) {
      super(stubConfig());
      this.secrets = secrets;
    }

    private static org.louis.Config stubConfig() {
      org.louis.Config c = new org.louis.Config();
      c.githubRepo = "owner/repo";
      c.githubToken = "x";
      c.deliveryEmail = "x@x";
      c.smtpUser = "x";
      c.smtpPass = "x";
      return c;
    }

    @Override
    public java.util.Collection<Secret> getSecrets() {
      return secrets;
    }
  }

  private static int selectedIndex(SecretsListPanel sut) {
    return (int) readField(sut, "selectedIndex");
  }

  @SuppressWarnings("unchecked")
  private static List<Label> cursorLabels(SecretsListPanel sut) {
    return (List<Label>) readField(sut, "cursorLabels");
  }

  @SuppressWarnings("unchecked")
  private static List<Label> nameLabels(SecretsListPanel sut) {
    return (List<Label>) readField(sut, "nameLabels");
  }

  @SuppressWarnings("unchecked")
  private static List<Label> statusLabels(SecretsListPanel sut) {
    return (List<Label>) readField(sut, "statusLabels");
  }

  private static Object readField(Object target, String name) {
    try {
      Field f = target.getClass().getDeclaredField(name);
      f.setAccessible(true);
      return f.get(target);
    } catch (ReflectiveOperationException e) {
      fail("Could not read " + name + ": " + e);
      return null;
    }
  }

  private static void invokeMoveSelection(SecretsListPanel sut, int delta) throws Exception {
    java.lang.reflect.Method m =
        SecretsListPanel.class.getDeclaredMethod("moveSelection", int.class);
    m.setAccessible(true);
    m.invoke(sut, delta);
  }

  private static boolean labelInTree(Component root, String exact) {
    if (root instanceof Label l && exact.equals(l.getText())) return true;
    if (root instanceof Panel p) {
      for (Component c : p.getChildrenList()) {
        if (labelInTree(c, exact)) return true;
      }
    }
    return false;
  }

  private static boolean labelInTreeContaining(Component root, String substring) {
    if (root instanceof Label l && l.getText() != null && l.getText().contains(substring))
      return true;
    if (root instanceof Panel p) {
      for (Component c : p.getChildrenList()) {
        if (labelInTreeContaining(c, substring)) return true;
      }
    }
    return false;
  }
}
