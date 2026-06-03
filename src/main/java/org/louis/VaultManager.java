package org.louis;

import org.apache.commons.io.FileUtils;

import java.io.File;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collection;


public class VaultManager {

    // NOTE: This class is a stub — it will be fully rewritten in Task 7.
    // Methods that depended on the old Secret API (persist(), getKey(), getIV(),
    // getEncryptedData(), Secret(String filename), Secret(Instant,byte[],String,byte[],byte[]))
    // have been removed because Secret.java was replaced with the new JSON meta + binary enc design.

    public void putSecret(int daysUntilDecryption, String secret, String name) {
        throw new UnsupportedOperationException("VaultManager not yet updated — see Task 7");
    }

    public void updateSecret(Secret secret, int additionalDays) {
        throw new UnsupportedOperationException("VaultManager not yet updated — see Task 7");
    }

    public Collection<Secret> getSecrets() {
        throw new UnsupportedOperationException("VaultManager not yet updated — see Task 7");
    }

    public String decrypt(Secret secret) {
        throw new UnsupportedOperationException("VaultManager not yet updated — see Task 7");
    }

    public void delete(Secret secret) {
        throw new UnsupportedOperationException("VaultManager not yet updated — see Task 7");
    }
}
