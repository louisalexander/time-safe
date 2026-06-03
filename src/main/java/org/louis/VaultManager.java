package org.louis;

import org.apache.commons.io.FileUtils;

import java.io.File;
import java.io.IOException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.Collection;
import java.util.Collections;

public class VaultManager {

    private static final String VAULT_DIR = "vault";
    private final Config config;
    private final GitHubVault github;

    public VaultManager(Config config) {
        this.config = config;
        this.github = new GitHubVault(config);
        new File(VAULT_DIR).mkdirs();
    }

    public void putSecret(int daysUntilDecryption, String secretText, String name) {
        try {
            byte[] key = EncryptDecrypt.generateKey();
            byte[] iv  = EncryptDecrypt.generateIV();
            byte[] enc = EncryptDecrypt.encrypt(secretText, key, iv);

            Instant unlockDate = Instant.now().plus(daysUntilDecryption, ChronoUnit.DAYS);
            Secret secret = new Secret(name, unlockDate, iv);

            secret.saveMeta(VAULT_DIR);
            secret.saveEncrypted(VAULT_DIR, enc);

            String keyB64 = Base64.getEncoder().encodeToString(key);
            github.pushFile("vault/secrets/" + secret.getId() + ".enc", enc,
                "lock: add encrypted secret " + name);
            github.pushFile("vault/secrets/" + secret.getId() + ".meta",
                readLocal(VAULT_DIR + "/" + secret.getId() + ".meta"),
                "lock: add metadata for " + name);
            github.pushFile("vault/keys/" + secret.getId() + ".key",
                (keyB64 + "\n").getBytes(),
                "lock: add key for " + name);
            github.pushFile(".github/workflows/unlock-" + secret.getId() + ".yml",
                github.buildWorkflowYaml(secret).getBytes(),
                "lock: add unlock workflow for " + name);

            System.out.println("Done. Secret locked until " + unlockDate);
            System.out.println("\nComplete these steps manually on the site:");
            System.out.println("  [ ] Change recovery email to: " + config.smtpUser);
            System.out.println("  [ ] Change login email to:    " + config.smtpUser + " (if supported)");
            System.out.println("  [ ] Log out of all sessions on the site");

        } catch (Exception e) {
            System.err.println("Failed to lock secret: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public void updateSecret(Secret secret, int additionalDays, String vaultDir) {
        try {
            Instant start = secret.availableForDecryption() ? Instant.now() : secret.getDecryptionDate();
            if (secret.availableForDecryption())
                System.out.println("Secret is currently unlocked. Extension starts from now.");

            Instant newDate = start.plus(additionalDays, ChronoUnit.DAYS);
            secret.setDecryptionDate(newDate);
            secret.saveMeta(vaultDir);

            github.pushFile("vault/secrets/" + secret.getId() + ".meta",
                readLocal(vaultDir + "/" + secret.getId() + ".meta"),
                "extend: update lock date for " + secret.getName());
            github.pushFile(".github/workflows/unlock-" + secret.getId() + ".yml",
                github.buildWorkflowYaml(secret).getBytes(),
                "extend: update workflow for " + secret.getName());

            System.out.println("Lock extended. Unlocks in "
                + Instant.now().until(newDate, ChronoUnit.HOURS) + " hours.");
        } catch (Exception e) {
            System.err.println("Failed to extend secret: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public Collection<Secret> getSecrets() {
        try {
            return Secret.list(VAULT_DIR);
        } catch (IOException e) {
            System.err.println("Could not read vault: " + e.getMessage());
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

    public void delete(Secret secret) {
        try {
            FileUtils.deleteQuietly(new File(VAULT_DIR, secret.getId() + ".meta"));
            FileUtils.deleteQuietly(new File(VAULT_DIR, secret.getId() + ".enc"));
            github.deleteFile("vault/secrets/" + secret.getId() + ".enc",  "delete: " + secret.getName());
            github.deleteFile("vault/secrets/" + secret.getId() + ".meta", "delete: " + secret.getName());
            github.deleteFile("vault/keys/"    + secret.getId() + ".key",  "delete: key for " + secret.getName());
            github.deleteFile(".github/workflows/unlock-" + secret.getId() + ".yml",
                "delete: workflow for " + secret.getName());
            System.out.println("Secret deleted.");
        } catch (Exception e) {
            System.err.println("Failed to delete from GitHub: " + e.getMessage());
        }
    }

    private byte[] readLocal(String path) throws IOException {
        return FileUtils.readFileToByteArray(new File(path));
    }
}
