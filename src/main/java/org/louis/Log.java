package org.louis;

import java.io.IOException;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.logging.FileHandler;
import java.util.logging.Formatter;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/** Static logging facade writing to timesafe.log in the working directory. */
public final class Log {

  private static final Logger LOGGER = Logger.getLogger("timesafe");
  private static final DateTimeFormatter TS =
      DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault());

  static {
    // Silence the root logger (removes console output)
    Logger root = Logger.getLogger("");
    for (Handler h : root.getHandlers()) root.removeHandler(h);

    try {
      FileHandler fh = new FileHandler("timesafe.log", /* append= */ true);
      fh.setLevel(Level.ALL);
      fh.setFormatter(
          new Formatter() {
            @Override
            public String format(LogRecord r) {
              String ts = TS.format(ZonedDateTime.now());
              String level = String.format("%-5s", r.getLevel().getName());
              StringBuilder sb = new StringBuilder();
              sb.append(ts).append(" [").append(level).append("] ").append(r.getMessage());
              if (r.getThrown() != null) {
                sb.append(" — ").append(r.getThrown().toString());
                for (StackTraceElement e : r.getThrown().getStackTrace()) {
                  sb.append("\n    at ").append(e);
                }
              }
              sb.append('\n');
              return sb.toString();
            }
          });
      LOGGER.addHandler(fh);
      LOGGER.setLevel(Level.ALL);
      LOGGER.setUseParentHandlers(false);
    } catch (IOException e) {
      // File logging unavailable — silently continue without it
    }
  }

  public static void info(String msg) {
    LOGGER.info(msg);
  }

  public static void warn(String msg) {
    LOGGER.warning(msg);
  }

  public static void error(String msg) {
    LOGGER.severe(msg);
  }

  public static void error(String msg, Throwable t) {
    LOGGER.log(Level.SEVERE, msg, t);
  }

  private Log() {}
}
