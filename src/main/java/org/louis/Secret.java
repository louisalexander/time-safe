package org.louis;

import com.google.gson.Gson;
import org.apache.commons.io.output.StringBuilderWriter;
import org.apache.commons.lang3.builder.ReflectionToStringBuilder;

import java.io.*;
import java.time.Duration;
import java.time.Instant;
import java.time.Period;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

public class Secret implements Serializable{
    private Instant decryptionDate;
    private byte[] encryptedData;
    private String name;
    private UUID id;
    private byte[] key;
    private byte[] iv;

    public Secret(String filename) {

        Secret secret = null;

        try (ObjectInputStream ois
                     = new ObjectInputStream(new FileInputStream(filename))) {

            secret = (Secret) ois.readObject();

        } catch (Exception ex) {
            ex.printStackTrace();
        }

        this.decryptionDate = secret.decryptionDate;
        this.encryptedData = secret.encryptedData;
        this.name = secret.name;
        this.id = secret.id;
        this.key = secret.key;
        this.iv = secret.iv;
    }

    public Secret(Instant decryptionDate, byte[] encryptedData, String name) {
        this.decryptionDate = decryptionDate;
        this.encryptedData = encryptedData;
        this.name = name;
        this.id = UUID.randomUUID();
        this.key = null;
        this.iv = null;
    }

    public Secret(Instant decryptionDate, byte[] encryptedData, String name, byte[] key, byte[] iv) {
        this.decryptionDate = decryptionDate;
        this.encryptedData = encryptedData;
        this.name = name;
        this.id = UUID.randomUUID();
        this.key = key;
        this.iv = iv;
    }

    public Instant getDecryptionDate() {
        return decryptionDate;
    }

    public byte[] getEncryptedData() {
        return encryptedData;
    }

    public String getName() {
        return name;
    }

    public String getId() {
        return id.toString();
    }

    public byte[] getKey() {
        return key;
    }

    public byte[] getIV() {
        return iv;
    }

    public void persist() {

        try (ObjectOutputStream oos =
                     new ObjectOutputStream(new FileOutputStream("vault/" + id.toString()))) {

            oos.writeObject(this);
            System.out.println("Done");

        } catch (Exception ex) {
            ex.printStackTrace();
        }
    }

    public boolean availableForDecryption() {
        return Instant.now().isAfter(this.decryptionDate);
    }

    public void setDecryptionDate(Instant decryptionDate) {
        this.decryptionDate = decryptionDate;

    }
    public String toString() {
        try( StringBuilderWriter stringBuilderWriter = new StringBuilderWriter()) {

            stringBuilderWriter.append("Name: ");
            stringBuilderWriter.append(this.name);
            stringBuilderWriter.append("\n");
            stringBuilderWriter.append("ID: ");
            stringBuilderWriter.append(this.id.toString());
            stringBuilderWriter.append("\n");
            stringBuilderWriter.append("Hours until unlock: ");
            stringBuilderWriter.append(availableForDecryption() ? "0" : Instant.now().until(this.getDecryptionDate(), ChronoUnit.HOURS) + " hours");

            return stringBuilderWriter.toString();
        }
    }
}
