package org.louis;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.Collection;
import java.util.Collections;
import org.apache.commons.io.FileUtils;

public class VaultManager {

  private static final String VAULT_DIR = "vault";
  private final Config config;
  private final GitHubVault github;

  public VaultManager(Config config) {
    this.config = config;
    this.github = new GitHubVault(config);
    new File(VAULT_DIR).mkdirs();
  }

  public void putSecret(int daysUntilDecryption, String secretText, String name) throws Exception {
    byte[] key = EncryptDecrypt.generateKey();
    byte[] iv = EncryptDecrypt.generateIV();
    byte[] enc = EncryptDecrypt.encrypt(secretText, key, iv);

    Instant unlockDate = Instant.now().plus(daysUntilDecryption, ChronoUnit.DAYS);
    Secret secret = new Secret(name, unlockDate, iv);

    secret.saveMeta(VAULT_DIR);
    secret.saveEncrypted(VAULT_DIR, enc);

    String keyB64 = Base64.getEncoder().encodeToString(key);
    github.pushFile(
        "vault/secrets/" + secret.getId() + ".enc", enc, "lock: add encrypted secret " + name);
    github.pushFile(
        "vault/secrets/" + secret.getId() + ".meta",
        readLocal(VAULT_DIR + "/" + secret.getId() + ".meta"),
        "lock: add metadata for " + name);
    github.pushFile(
        "vault/keys/" + secret.getId() + ".key",
        (keyB64 + "\n").getBytes(StandardCharsets.UTF_8),
        "lock: add key for " + name);
    github.pushFile(
        ".github/workflows/unlock-" + secret.getId() + ".yml",
        github.buildWorkflowYaml(secret).getBytes(StandardCharsets.UTF_8),
        "lock: add unlock workflow for " + name);
  }

  public void updateSecret(Secret secret, int additionalDays, String vaultDir) throws Exception {
    Instant start = secret.availableForDecryption() ? Instant.now() : secret.getDecryptionDate();
    Instant newDate = start.plus(additionalDays, ChronoUnit.DAYS);
    secret.setDecryptionDate(newDate);
    secret.saveMeta(vaultDir);

    github.pushFile(
        "vault/secrets/" + secret.getId() + ".meta",
        readLocal(vaultDir + "/" + secret.getId() + ".meta"),
        "extend: update lock date for " + secret.getName());
    github.pushFile(
        ".github/workflows/unlock-" + secret.getId() + ".yml",
        github.buildWorkflowYaml(secret).getBytes(StandardCharsets.UTF_8),
        "extend: update workflow for " + secret.getName());
  }

  public Collection<Secret> getSecrets() {
    try {
      return Secret.list(VAULT_DIR);
    } catch (IOException e) {
      return Collections.emptyList();
    }
  }

  public String decrypt(Secret secret, byte[] key) {
    try {
      byte[] enc = Secret.loadEncrypted(VAULT_DIR, secret.getId());
      return EncryptDecrypt.decrypt(enc, key, secret.getIv());
    } catch (Exception e) {
      return "Decryption failed: " + e.getMessage();
    }
  }

  public void delete(Secret secret) throws Exception {
    FileUtils.deleteQuietly(new File(VAULT_DIR, secret.getId() + ".meta"));
    FileUtils.deleteQuietly(new File(VAULT_DIR, secret.getId() + ".enc"));
    github.deleteFile("vault/secrets/" + secret.getId() + ".enc", "delete: " + secret.getName());
    github.deleteFile("vault/secrets/" + secret.getId() + ".meta", "delete: " + secret.getName());
    github.deleteFile(
        "vault/keys/" + secret.getId() + ".key", "delete: key for " + secret.getName());
    github.deleteFile(
        ".github/workflows/unlock-" + secret.getId() + ".yml",
        "delete: workflow for " + secret.getName());
  }

  private byte[] readLocal(String path) throws IOException {
    return FileUtils.readFileToByteArray(new File(path));
  }
}
