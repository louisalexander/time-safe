package org.louis;

import java.io.IOException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

public class Main {

  private static VaultManager vaultManager;

  @SuppressWarnings("InfiniteLoopStatement")
  public static void main(String[] args) throws IOException {
    vaultManager = loadVaultManager();
    while (true) {
      doMenu();
      System.out.println();
    }
  }

  private static VaultManager loadVaultManager() {
    try {
      Config config = Config.load();
      return new VaultManager(config);
    } catch (IOException e) {
      System.out.println("No config found. Run setup first (option 0).");
      return null;
    }
  }

  private static void doMenu() throws IOException {
    Scanner in = new Scanner(System.in);
    System.out.print(
        "0) Setup (first-time configuration)\n"
            + "1) Add a new secret to the vault\n"
            + "2) List secrets in the vault\n"
            + "> ");
    int choice = in.nextInt();
    System.out.println();
    switch (choice) {
      case 0:
        runSetup();
        break;
      case 1:
        captureNewSecret();
        break;
      case 2:
        listAllSecrets();
        break;
    }
  }

  private static void runSetup() throws IOException {
    Scanner in = new Scanner(System.in);
    Config config = new Config();

    System.out.print("Vault GitHub personal access token (repo scope): ");
    config.githubToken = in.nextLine().trim();

    System.out.print("Vault GitHub repo (owner/repo, e.g. myname-vault/vault): ");
    config.githubRepo = in.nextLine().trim();

    System.out.print("Vault Gmail address: ");
    config.smtpUser = in.nextLine().trim();

    System.out.print("Vault Gmail App Password: ");
    config.smtpPass = in.nextLine().trim();

    System.out.print("Your real email (where keys will be delivered): ");
    config.deliveryEmail = in.nextLine().trim();

    config.save(Config.DEFAULT_PATH);
    System.out.println("Config saved to " + Config.DEFAULT_PATH);

    System.out.println("Initialising vault repo on GitHub...");
    new GitHubVault(config).initRepo();
    System.out.println("Done. Vault repo is ready.");

    vaultManager = new VaultManager(config);
  }

  private static void captureNewSecret() {
    if (vaultManager == null) {
      System.out.println("Run setup first (option 0).");
      return;
    }
    Scanner in = new Scanner(System.in);

    System.out.print("Name for this secret (e.g. Empornium, Vault Gmail):\n> ");
    String name = in.nextLine();

    System.out.print("The password to lock:\n> ");
    String secret = in.nextLine();

    System.out.print("Days to lock for:\n> ");
    int days = in.nextInt();

    vaultManager.putSecret(days, secret, name);
  }

  private static void listAllSecrets() {
    if (vaultManager == null) {
      System.out.println("Run setup first (option 0).");
      return;
    }
    Scanner in = new Scanner(System.in);
    Collection<Secret> secrets = vaultManager.getSecrets();

    if (secrets.isEmpty()) {
      System.out.println("No secrets in the vault.");
      return;
    }

    Map<Integer, Secret> menu = new HashMap<>();
    int i = 1;
    for (Secret s : secrets) {
      menu.put(i, s);
      System.out.println(
          i
              + ") "
              + s.getName()
              + (s.availableForDecryption() ? " (UNLOCKED - check email for key)" : " (locked)"));
      i++;
    }
    System.out.print("> ");
    Secret selected = menu.get(in.nextInt());
    System.out.println();
    if (selected != null) manageSecret(selected);
  }

  private static void manageSecret(Secret secret) {
    Scanner in = new Scanner(System.in);
    System.out.print(
        "1) Secret details\n2) Decrypt (enter key from email)\n3) Extend lock\n4) Delete\n> ");
    int choice = in.nextInt();
    System.out.println();
    switch (choice) {
      case 1:
        System.out.println(secret);
        break;
      case 2:
        decryptSecret(secret);
        break;
      case 3:
        extendSecret(secret);
        break;
      case 4:
        deleteSecret(secret);
        break;
    }
  }

  private static void decryptSecret(Secret secret) {
    if (!secret.availableForDecryption()) {
      long hours = Instant.now().until(secret.getDecryptionDate(), ChronoUnit.HOURS);
      System.out.println("Still locked. " + hours + " hours remaining.");
      return;
    }
    Scanner in = new Scanner(System.in);
    System.out.print("Paste the base64 key from your unlock email:\n> ");
    String keyB64 = in.nextLine().trim();
    try {
      byte[] key = Base64.getDecoder().decode(keyB64);
      System.out.println("\nDecrypted: " + vaultManager.decrypt(secret, key));
    } catch (IllegalArgumentException e) {
      System.out.println("Invalid key format. Paste the full base64 string from the email.");
    }
  }

  private static void extendSecret(Secret secret) {
    Scanner in = new Scanner(System.in);
    System.out.print("Additional days to add to the lock:\n> ");
    int days = in.nextInt();
    vaultManager.updateSecret(secret, days, "vault");
  }

  private static void deleteSecret(Secret secret) {
    Scanner in = new Scanner(System.in);
    System.out.print("Are you sure? (y/n)\n> ");
    if ("y".equals(in.nextLine().trim())) {
      vaultManager.delete(secret);
    } else {
      System.out.println("Not deleted.");
    }
  }
}
