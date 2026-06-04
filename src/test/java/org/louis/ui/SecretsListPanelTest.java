package org.louis.ui;

import static org.junit.Assert.assertEquals;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import org.junit.Test;

public class SecretsListPanelTest {

  private static final Instant NOW = Instant.parse("2026-06-04T10:00:00Z");

  @Test
  public void readyWhenPast() {
    assertEquals(
        "● ready", SecretsListPanel.formatTimeRemaining(NOW, NOW.minus(1, ChronoUnit.SECONDS)));
  }

  @Test
  public void readyWhenExactlyNow() {
    assertEquals("● ready", SecretsListPanel.formatTimeRemaining(NOW, NOW));
  }

  @Test
  public void secondsOnly() {
    assertEquals("45s", SecretsListPanel.formatTimeRemaining(NOW, NOW.plusSeconds(45)));
  }

  @Test
  public void minutesAndSeconds() {
    assertEquals("5m 30s", SecretsListPanel.formatTimeRemaining(NOW, NOW.plusSeconds(5 * 60 + 30)));
  }

  @Test
  public void hoursMinutesSeconds() {
    Instant target = NOW.plusSeconds(2L * 3600 + 14 * 60 + 33);
    assertEquals("2h 14m 33s", SecretsListPanel.formatTimeRemaining(NOW, target));
  }

  @Test
  public void daysHoursMinutes() {
    Instant target = NOW.plus(47, ChronoUnit.DAYS).plusSeconds(12L * 3600 + 8 * 60);
    assertEquals("47d 12h 08m", SecretsListPanel.formatTimeRemaining(NOW, target));
  }

  @Test
  public void singleDay() {
    Instant target = NOW.plus(1, ChronoUnit.DAYS);
    assertEquals("1d 0h 00m", SecretsListPanel.formatTimeRemaining(NOW, target));
  }

  @Test
  public void hoursPadMinutesAndSeconds() {
    Instant target = NOW.plusSeconds(3L * 3600 + 2 * 60 + 7);
    assertEquals("3h 02m 07s", SecretsListPanel.formatTimeRemaining(NOW, target));
  }

  @Test
  public void minutesPadSeconds() {
    Instant target = NOW.plusSeconds(2L * 60 + 5);
    assertEquals("2m 05s", SecretsListPanel.formatTimeRemaining(NOW, target));
  }
}
