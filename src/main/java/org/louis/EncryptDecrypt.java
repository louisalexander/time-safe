package org.louis;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Properties;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.apache.commons.crypto.stream.CryptoInputStream;
import org.apache.commons.crypto.stream.CryptoOutputStream;

public class EncryptDecrypt implements AutoCloseable {

  private static final String TRANSFORM = "AES/CBC/PKCS5Padding";
  private static final Properties PROPERTIES = new Properties();

  public static byte[] generateKey() {
    byte[] key = new byte[32];
    new SecureRandom().nextBytes(key);
    return key;
  }

  public static byte[] generateIV() {
    byte[] iv = new byte[16];
    new SecureRandom().nextBytes(iv);
    return iv;
  }

  public static byte[] encrypt(String input, byte[] key, byte[] iv) throws IOException {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    try (CryptoOutputStream cos =
        new CryptoOutputStream(
            TRANSFORM, PROPERTIES, out, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv))) {
      cos.write(input.getBytes(StandardCharsets.UTF_8));
      cos.flush();
    }
    return out.toByteArray();
  }

  public static String decrypt(byte[] encrypted, byte[] key, byte[] iv) throws IOException {
    try (CryptoInputStream cis =
        new CryptoInputStream(
            TRANSFORM,
            PROPERTIES,
            new ByteArrayInputStream(encrypted),
            new SecretKeySpec(key, "AES"),
            new IvParameterSpec(iv))) {
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      byte[] buf = new byte[4096];
      int n;
      while ((n = cis.read(buf)) > -1) out.write(buf, 0, n);
      return out.toString(StandardCharsets.UTF_8.name());
    }
  }

  @Override
  public void close() {}
}
