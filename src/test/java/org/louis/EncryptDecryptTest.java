package org.louis;

import static org.junit.Assert.*;

import java.util.Arrays;
import java.util.Base64;
import org.junit.Test;

public class EncryptDecryptTest {

  @Test
  public void encryptDecryptRoundTrip() throws Exception {
    byte[] key = EncryptDecrypt.generateKey();
    byte[] iv = EncryptDecrypt.generateIV();
    String plaintext = "hunter2$ecretP@ss";

    byte[] encrypted = EncryptDecrypt.encrypt(plaintext, key, iv);
    String decrypted = EncryptDecrypt.decrypt(encrypted, key, iv);

    assertEquals(plaintext, decrypted);
  }

  @Test
  public void generateKeyIsUnique() {
    assertFalse(Arrays.equals(EncryptDecrypt.generateKey(), EncryptDecrypt.generateKey()));
  }

  @Test
  public void keyIs32Bytes() {
    assertEquals(32, EncryptDecrypt.generateKey().length);
  }

  @Test
  public void ivIs16Bytes() {
    assertEquals(16, EncryptDecrypt.generateIV().length);
  }

  @Test(expected = Exception.class)
  public void wrongKeyFailsDecrypt() throws Exception {
    byte[] key = EncryptDecrypt.generateKey();
    byte[] iv = EncryptDecrypt.generateIV();
    byte[] enc = EncryptDecrypt.encrypt("secret", key, iv);
    EncryptDecrypt.decrypt(enc, EncryptDecrypt.generateKey(), iv);
  }

  @Test
  public void keyBase64RoundTrip() {
    byte[] key = EncryptDecrypt.generateKey();
    byte[] decoded = Base64.getDecoder().decode(Base64.getEncoder().encodeToString(key));
    assertArrayEquals(key, decoded);
  }
}
