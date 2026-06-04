package org.louis;

import com.google.gson.Gson;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.UUID;
import org.apache.commons.io.FileUtils;

public class Secret {

  private String id;
  private String name;
  private String decryptionDateIso;
  private String ivBase64;
  private String createdAtIso;

  private Secret() {} // for Gson

  public Secret(String name, Instant decryptionDate, byte[] iv) {
    this.id = UUID.randomUUID().toString();
    this.name = name;
    this.decryptionDateIso = decryptionDate.toString();
    this.ivBase64 = Base64.getEncoder().encodeToString(iv);
    this.createdAtIso = Instant.now().toString();
  }

  public String getId() {
    return id;
  }

  public String getName() {
    return name;
  }

  public Instant getDecryptionDate() {
    return Instant.parse(decryptionDateIso);
  }

  public byte[] getIv() {
    return Base64.getDecoder().decode(ivBase64);
  }

  public Instant getCreatedAt() {
    return createdAtIso != null ? Instant.parse(createdAtIso) : getDecryptionDate();
  }

  public void setDecryptionDate(Instant newDate) {
    this.decryptionDateIso = newDate.toString();
  }

  public boolean availableForDecryption() {
    return Instant.now().isAfter(getDecryptionDate());
  }

  public void saveMeta(String vaultDir) throws IOException {
    FileUtils.writeStringToFile(
        new File(vaultDir, id + ".meta"), new Gson().toJson(this), StandardCharsets.UTF_8);
  }

  public static Secret loadMeta(String vaultDir, String uuid) throws IOException {
    String json =
        FileUtils.readFileToString(new File(vaultDir, uuid + ".meta"), StandardCharsets.UTF_8);
    return new Gson().fromJson(json, Secret.class);
  }

  public void saveEncrypted(String vaultDir, byte[] data) throws IOException {
    FileUtils.writeByteArrayToFile(new File(vaultDir, id + ".enc"), data);
  }

  public static byte[] loadEncrypted(String vaultDir, String uuid) throws IOException {
    return FileUtils.readFileToByteArray(new File(vaultDir, uuid + ".enc"));
  }

  public static List<Secret> list(String vaultDir) throws IOException {
    File dir = new File(vaultDir);
    List<Secret> secrets = new ArrayList<>();
    String[] files = dir.list((d, n) -> n.endsWith(".meta"));
    if (files == null) return secrets;
    for (String file : files) secrets.add(loadMeta(vaultDir, file.replace(".meta", "")));
    return secrets;
  }

  @Override
  public String toString() {
    long hours =
        availableForDecryption() ? 0 : Instant.now().until(getDecryptionDate(), ChronoUnit.HOURS);
    return "Name: "
        + name
        + "\nID: "
        + id
        + "\nHours until unlock: "
        + (hours == 0 ? "Unlocked" : hours + " hours");
  }
}
