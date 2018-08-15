package org.louis;

import org.apache.commons.io.FileUtils;

import java.io.File;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collection;


public class VaultManager {

    public void putSecret(int daysUntilDecryption, String secret, String name) {

        Instant decryptionDate = Instant.now().plus(daysUntilDecryption, ChronoUnit.DAYS);

        try (EncryptDecrypt encryptDecrypt = new EncryptDecrypt()) {
            byte[] encryptedSecret = encryptDecrypt.encrypt(secret);
            Secret encryptedDatum = new Secret(decryptionDate, encryptedSecret, name);
            encryptedDatum.persist();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void updateSecret(Secret secret, int additionalDays) {

        Instant start = null;

        if ( !secret.availableForDecryption() ) {
            start = secret.getDecryptionDate();
        } else {
            System.out.println("Secret is currently unlocked.  Extension will start from current time.");
            start = Instant.now();
        }

        secret.setDecryptionDate(start.plus(additionalDays, ChronoUnit.DAYS));
        secret.persist();

        System.out.println("Secret lock has been extended.  Secret will unlock in "
                + Instant.now().until(secret.getDecryptionDate(), ChronoUnit.HOURS));



    }


    public Collection<Secret> getSecrets() {

        Collection<Secret> secrets = new ArrayList<Secret>();
        File folder = new File("vault");

        String[] files = folder.list();

        for (String file : files) {

            Secret secret = new Secret("vault/" + file);
            secrets.add(secret);
        }

        return secrets;
    }

    public String decrypt(Secret secret) {
        try (EncryptDecrypt encryptDecrypt = new EncryptDecrypt()) {
            return encryptDecrypt.decrypt(secret.getEncryptedData());
        } catch (Exception e) {
            e.printStackTrace();
        }

        return "An error occurred during decryption";
    }

    public void delete(Secret secret) {
        FileUtils.deleteQuietly(new File("vault/" + secret.getId()));
    }

}
