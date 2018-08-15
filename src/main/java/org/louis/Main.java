package org.louis;

import java.io.IOException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.Scanner;

/**
 * Example showing how to use stream encryption and decryption.
 */
public class Main {

    private static VaultManager vaultManager = new VaultManager();

    @SuppressWarnings("InfiniteLoopStatement")
    public static void main(String[] args) throws IOException {

        while (true) {
            doMenu();
            System.out.println();
        }
    }

    private static void doMenu() {
        Scanner in = new Scanner(System.in);

        System.out.print("1) Add a new secret to the vault\n" +
                "2) List secrets in the vault\n" +
                "> "
        );

        int choice = in.nextInt();
        System.out.println();

        switch (choice) {
            case (1):
                captureNewSecret();
                break;

            case (2):
                listAllSecrets();
                break;

        }
    }

    private static void listAllSecrets() {
        Scanner in = new Scanner(System.in);

        Collection<Secret> secrets = vaultManager.getSecrets();

        Map<Integer, Secret> menu = new HashMap<Integer, Secret>();

        if (secrets.isEmpty()) {
            System.out.println("There are no secrets in the vault :(");
            return;
        }

        System.out.print("Which secret do you wish to manage?\n");

        Integer i = Integer.valueOf(1);
        for (Secret secret : secrets) {

            menu.put(i, secret);
            System.out.print(i + ") " + secret.getName() + (secret.availableForDecryption() ? " (unlocked)" : " (locked)") + "\n");

            i++;
        }

        System.out.print("> ");
        int choice = in.nextInt();
        System.out.println();

        Secret secret = menu.get(choice);

        manageSecret(secret);
    }

    private static void manageSecret(Secret secret) {
        Scanner in = new Scanner(System.in);


        System.out.print("1) Secret details\n" +
                "2) Decrypt secret\n" +
                "3) Extend lock\n" +
                "4) Delete secret\n" +
                "> "
        );

        int choice = in.nextInt();
        System.out.println();
        System.out.flush();

        switch (choice) {
            case (1):
                System.out.println(secret);
                break;

            case (2):
                decryptSecret(secret);
                break;

            case (3):
                extendSecret(secret);
                break;

            case (4):
                deleteSecret(secret);
                break;
        }
    }

    private static void decryptSecret(Secret secret) {
        if (secret.availableForDecryption()) {
            System.out.println(vaultManager.decrypt(secret));
        } else {
            System.out.println("Decryption date not met!");
            System.out.println("Secret will unlock in " + Instant.now().until(secret.getDecryptionDate(), ChronoUnit.HOURS) + " hours ¯\\_(ツ)_/¯");
        }
    }

    private static void deleteSecret(Secret secret) {
        Scanner in = new Scanner(System.in);

        System.out.print("Are you sure? (y/n)\n> ");
        String choice = in.nextLine();

        switch (choice) {
            case ("y"):
                vaultManager.delete(secret);
                break;

            default:
                System.out.println("Secret not deleted ;)");
        }

    }

    private static void extendSecret(Secret secret) {
        Scanner in = new Scanner(System.in);


        System.out.print("How many days do you want to extend the secret lock for?\n> ");
        int days = in.nextInt();

        vaultManager.updateSecret(secret, days);
    }

    public static void captureNewSecret() {
        Scanner in = new Scanner(System.in);
        System.out.print("What should we call this secret?\n> ");
        String name = in.nextLine();

        System.out.print("Enter the secret:\n> ");
        String input = in.nextLine();

        System.out.print("How many days should we lock this secret for?\n> ");
        int days = in.nextInt();

        vaultManager.putSecret(days, input, name);
    }

}