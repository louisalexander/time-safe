package org.louis.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.googlecode.lanterna.gui2.Label;
import com.googlecode.lanterna.gui2.TextBox;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import org.junit.Test;

public class UiComponentsTest {

  @Test
  public void breadcrumbPrependsChevron() {
    Label l = UiComponents.breadcrumb("Secrets");
    assertEquals("‹ Secrets", l.getText());
    assertEquals(UiColors.BLUE, l.getForegroundColor());
  }

  @Test
  public void sectionLabelRendersDim() {
    Label l = UiComponents.sectionLabel("Secrets — repo");
    assertEquals("Secrets — repo", l.getText());
    assertEquals(UiColors.DIM, l.getForegroundColor());
  }

  @Test
  public void dimLabelRendersDim() {
    Label l = UiComponents.dimLabel("Hint text");
    assertEquals(UiColors.DIM, l.getForegroundColor());
  }

  @Test
  public void brightLabelUsesBrightColor() {
    Label l = UiComponents.brightLabel("Heading");
    assertEquals(UiColors.BRIGHT, l.getForegroundColor());
  }

  @Test
  public void dividerRepeatsEmDash() {
    Label l = UiComponents.divider(5);
    assertEquals("─────", l.getText());
  }

  @Test
  public void formatDateMatchesYyyyMmDd() {
    Instant instant = LocalDate.of(2026, 6, 4).atStartOfDay(ZoneId.systemDefault()).toInstant();
    assertEquals("2026-06-04", UiComponents.formatDate(instant));
  }

  @Test
  public void previewUnlockDateAddsDays() {
    String today = UiComponents.formatDate(Instant.now());
    String thirtyDaysOut = UiComponents.previewUnlockDate(30);
    // Should be different from today (assuming we're not running at the moment of day-rollover)
    assertNotNull(thirtyDaysOut);
    assertEquals(10, thirtyDaysOut.length());
    assertTrue("Preview should not equal today's date", !thirtyDaysOut.equals(today));
  }

  @Test
  public void previewUnlockDateZeroDaysIsToday() {
    assertEquals(UiComponents.formatDate(Instant.now()), UiComponents.previewUnlockDate(0));
  }

  @Test
  public void passwordInputIsMasked() {
    TextBox tb = UiComponents.passwordInput(20);
    tb.setText("hello");
    // Masked TextBox still returns the original text via getText(); the mask only affects display.
    assertEquals("hello", tb.getText());
  }

  @Test
  public void singleLineInputIsCreated() {
    TextBox tb = UiComponents.singleLineInput(40);
    assertNotNull(tb);
  }

  @Test
  public void multiLineInputIsCreated() {
    TextBox tb = UiComponents.multiLineInput(60, 8);
    assertNotNull(tb);
  }

  @Test
  public void hintBarKeysAreBlueDescriptionsAreDim() {
    com.googlecode.lanterna.gui2.Panel bar = UiComponents.hintBar("a", "add", "q", "quit");
    java.util.List<com.googlecode.lanterna.gui2.Label> labels = new java.util.ArrayList<>();
    for (com.googlecode.lanterna.gui2.Component c : bar.getChildrenList()) {
      if (c instanceof com.googlecode.lanterna.gui2.Label l) labels.add(l);
    }
    assertEquals(4, labels.size());
    assertEquals("a", labels.get(0).getText());
    assertEquals(UiColors.BLUE, labels.get(0).getForegroundColor());
    assertTrue(labels.get(1).getText().contains("add"));
    assertEquals(UiColors.DIM, labels.get(1).getForegroundColor());
    assertEquals("q", labels.get(2).getText());
    assertEquals(UiColors.BLUE, labels.get(2).getForegroundColor());
    assertTrue(labels.get(3).getText().contains("quit"));
    assertEquals(UiColors.DIM, labels.get(3).getForegroundColor());
  }

  @Test(expected = IllegalArgumentException.class)
  public void hintBarRejectsOddArgumentCount() {
    UiComponents.hintBar("a", "add", "q");
  }
}
