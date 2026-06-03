package org.louis;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

import static org.junit.Assert.*;

public class SecretTest {

    @Rule
    public TemporaryFolder tmp = new TemporaryFolder();

    private String dir() { return tmp.getRoot().getAbsolutePath(); }

    @Test
    public void metadataRoundTrip() throws Exception {
        byte[] iv = EncryptDecrypt.generateIV();
        Instant unlock = Instant.now().plus(7, ChronoUnit.DAYS);
        Secret s = new Secret("MySecret", unlock, iv);

        s.saveMeta(dir());
        Secret loaded = Secret.loadMeta(dir(), s.getId());

        assertEquals(s.getId(), loaded.getId());
        assertEquals("MySecret", loaded.getName());
        assertArrayEquals(iv, loaded.getIv());
        assertEquals(unlock.getEpochSecond(), loaded.getDecryptionDate().getEpochSecond());
    }

    @Test
    public void encryptedDataRoundTrip() throws Exception {
        byte[] data = new byte[]{1, 2, 3, 4, 5};
        Secret s = new Secret("X", Instant.now().plus(1, ChronoUnit.DAYS), EncryptDecrypt.generateIV());
        s.saveEncrypted(dir(), data);

        assertArrayEquals(data, Secret.loadEncrypted(dir(), s.getId()));
    }

    @Test
    public void listFindsAllMeta() throws Exception {
        byte[] iv = EncryptDecrypt.generateIV();
        new Secret("Alpha", Instant.now().plus(1, ChronoUnit.DAYS), iv).saveMeta(dir());
        new Secret("Beta",  Instant.now().plus(2, ChronoUnit.DAYS), iv).saveMeta(dir());

        List<Secret> list = Secret.list(dir());
        assertEquals(2, list.size());
    }

    @Test
    public void availableWhenPast() {
        Secret s = new Secret("X", Instant.now().minus(1, ChronoUnit.SECONDS), EncryptDecrypt.generateIV());
        assertTrue(s.availableForDecryption());
    }

    @Test
    public void lockedWhenFuture() {
        Secret s = new Secret("X", Instant.now().plus(7, ChronoUnit.DAYS), EncryptDecrypt.generateIV());
        assertFalse(s.availableForDecryption());
    }

    @Test
    public void setDecryptionDatePersists() throws Exception {
        byte[] iv = EncryptDecrypt.generateIV();
        Secret s = new Secret("X", Instant.now().plus(1, ChronoUnit.DAYS), iv);
        s.saveMeta(dir());

        Instant newDate = Instant.now().plus(30, ChronoUnit.DAYS);
        s.setDecryptionDate(newDate);
        s.saveMeta(dir());

        Secret loaded = Secret.loadMeta(dir(), s.getId());
        assertEquals(newDate.getEpochSecond(), loaded.getDecryptionDate().getEpochSecond());
    }
}
