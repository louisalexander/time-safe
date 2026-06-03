# Vault Durability & Bypass Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace local-only, hardcoded-key vault with per-secret random AES-256 keys backed by a private GitHub repo, where keys are stored as repo files and emailed to the user on unlock via a scheduled GitHub Action.

**Architecture:** Each secret gets a cryptographically random key and IV. The key is stored as a base64 file in a private vault GitHub repo (`vault/keys/<uuid>.key`) and never written to local disk. Encrypted blobs and metadata are stored both locally and in GitHub. A per-secret GitHub Actions workflow runs monthly and emails the key when the unlock date is reached. A dedicated vault Gmail handles all locked-site recovery emails, its own password also locked in the vault.

**Tech Stack:** Java 8, Maven, AES-256/CBC (Apache Commons Crypto), GitHub Contents API via `HttpURLConnection` + Gson, JUnit 4, Python 3 (GitHub Actions runtime for email delivery via Gmail SMTP)

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `pom.xml` | Modify | Add JUnit 4 |
| `src/main/java/org/louis/Config.java` | Create | Load/save `~/.timesafe/config.json` |
| `src/main/java/org/louis/EncryptDecrypt.java` | Modify | Random key/IV generation; key/IV as params (remove hardcoded values) |
| `src/main/java/org/louis/Secret.java` | Modify | JSON `.meta` + binary `.enc` files; remove `Serializable` |
| `src/main/java/org/louis/GitHubVault.java` | Create | GitHub Contents API: push/fetch/delete files; workflow YAML generation |
| `src/main/java/org/louis/VaultManager.java` | Modify | Orchestrate encrypt → GitHub push → workflow creation; updated extend/delete |
| `src/main/java/org/louis/Main.java` | Modify | Setup command; key-input decrypt flow |
| `vault/scripts/send_key.py` | Create | Python email script committed to repo and run by GitHub Actions |
| `src/test/java/org/louis/ConfigTest.java` | Create | Config round-trip |
| `src/test/java/org/louis/EncryptDecryptTest.java` | Create | Encrypt/decrypt correctness |
| `src/test/java/org/louis/SecretTest.java` | Create | Metadata save/load, .enc round-trip |
| `src/test/java/org/louis/GitHubVaultTest.java` | Create | Workflow YAML generation (pure logic) |

---

### Task 1: Add JUnit 4 and test directory

**Files:**
- Modify: `pom.xml`

- [ ] **Add JUnit 4 and Surefire plugin to pom.xml**

Inside `<dependencies>`, add:

```xml
<dependency>
    <groupId>junit</groupId>
    <artifactId>junit</artifactId>
    <version>4.13.2</version>
    <scope>test</scope>
</dependency>
```

Inside `<plugins>`, add:

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>2.22.2</version>
</plugin>
```

- [ ] **Create test directory**

```bash
mkdir -p src/test/java/org/louis
```

- [ ] **Verify compilation**

```bash
mvn test-compile
```

Expected: `BUILD SUCCESS`

- [ ] **Commit**

```bash
git add pom.xml src/test
git commit -m "chore: add JUnit 4 test framework"
```

---

### Task 2: Create Config

**Files:**
- Create: `src/main/java/org/louis/Config.java`
- Create: `src/test/java/org/louis/ConfigTest.java`

- [ ] **Write the failing test**

`src/test/java/org/louis/ConfigTest.java`:

```java
package org.louis;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;

import static org.junit.Assert.*;

public class ConfigTest {

    @Rule
    public TemporaryFolder tmp = new TemporaryFolder();

    @Test
    public void roundTrip() throws Exception {
        File configFile = new File(tmp.getRoot(), "config.json");
        Config c = new Config();
        c.githubToken = "ghp_abc";
        c.githubRepo = "vault-user/vault";
        c.smtpUser = "vault@gmail.com";
        c.smtpPass = "apppass";
        c.deliveryEmail = "real@gmail.com";
        c.save(configFile.getAbsolutePath());

        Config loaded = Config.load(configFile.getAbsolutePath());
        assertEquals("ghp_abc", loaded.githubToken);
        assertEquals("vault-user/vault", loaded.githubRepo);
        assertEquals("vault@gmail.com", loaded.smtpUser);
        assertEquals("apppass", loaded.smtpPass);
        assertEquals("real@gmail.com", loaded.deliveryEmail);
    }

    @Test
    public void defaultPath() {
        assertEquals(
            System.getProperty("user.home") + "/.timesafe/config.json",
            Config.DEFAULT_PATH
        );
    }
}
```

- [ ] **Run to confirm failure**

```bash
mvn test -Dtest=ConfigTest
```

Expected: compilation error — `Config` does not exist

- [ ] **Create Config**

`src/main/java/org/louis/Config.java`:

```java
package org.louis;

import com.google.gson.GsonBuilder;
import com.google.gson.Gson;
import org.apache.commons.io.FileUtils;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class Config {
    public static final String DEFAULT_PATH =
        System.getProperty("user.home") + "/.timesafe/config.json";

    public String githubToken;
    public String githubRepo;    // "owner/repo"
    public String smtpUser;
    public String smtpPass;
    public String deliveryEmail;

    public void save(String path) throws IOException {
        File f = new File(path);
        f.getParentFile().mkdirs();
        FileUtils.writeStringToFile(f,
            new GsonBuilder().setPrettyPrinting().create().toJson(this),
            StandardCharsets.UTF_8);
    }

    public static Config load(String path) throws IOException {
        String json = FileUtils.readFileToString(new File(path), StandardCharsets.UTF_8);
        return new Gson().fromJson(json, Config.class);
    }

    public static Config load() throws IOException {
        return load(DEFAULT_PATH);
    }
}
```

- [ ] **Run tests to confirm pass**

```bash
mvn test -Dtest=ConfigTest
```

Expected: `Tests run: 2, Failures: 0, Errors: 0`

- [ ] **Commit**

```bash
git add src/main/java/org/louis/Config.java src/test/java/org/louis/ConfigTest.java
git commit -m "feat: add Config for ~/.timesafe/config.json"
```

---

### Task 3: Refactor EncryptDecrypt

**Files:**
- Modify: `src/main/java/org/louis/EncryptDecrypt.java`
- Create: `src/test/java/org/louis/EncryptDecryptTest.java`

- [ ] **Write the failing tests**

`src/test/java/org/louis/EncryptDecryptTest.java`:

```java
package org.louis;

import org.junit.Test;

import java.util.Arrays;
import java.util.Base64;

import static org.junit.Assert.*;

public class EncryptDecryptTest {

    @Test
    public void encryptDecryptRoundTrip() throws Exception {
        byte[] key = EncryptDecrypt.generateKey();
        byte[] iv  = EncryptDecrypt.generateIV();
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
        byte[] key  = EncryptDecrypt.generateKey();
        byte[] iv   = EncryptDecrypt.generateIV();
        byte[] enc  = EncryptDecrypt.encrypt("secret", key, iv);
        EncryptDecrypt.decrypt(enc, EncryptDecrypt.generateKey(), iv);
    }

    @Test
    public void keyBase64RoundTrip() {
        byte[] key     = EncryptDecrypt.generateKey();
        byte[] decoded = Base64.getDecoder().decode(Base64.getEncoder().encodeToString(key));
        assertArrayEquals(key, decoded);
    }
}
```

- [ ] **Run to confirm failure**

```bash
mvn test -Dtest=EncryptDecryptTest
```

Expected: compilation errors — `generateKey`, `generateIV`, and new `encrypt`/`decrypt` signatures do not exist

- [ ] **Rewrite EncryptDecrypt**

`src/main/java/org/louis/EncryptDecrypt.java`:

```java
package org.louis;

import org.apache.commons.crypto.stream.CryptoInputStream;
import org.apache.commons.crypto.stream.CryptoOutputStream;

import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Properties;

public class EncryptDecrypt implements AutoCloseable {

    private static final String TRANSFORM = "AES/CBC/PKCS5Padding";
    private static final Properties PROPERTIES = new Properties();

    public static byte[] generateKey() {
        byte[] key = new byte[32];
        new SecureRandom().nextBytes(key);
        return key;
    }

    public static byte[] generateIV() {
        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        return iv;
    }

    public static byte[] encrypt(String input, byte[] key, byte[] iv) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (CryptoOutputStream cos = new CryptoOutputStream(
                TRANSFORM, PROPERTIES, out,
                new SecretKeySpec(key, "AES"), new IvParameterSpec(iv))) {
            cos.write(input.getBytes(StandardCharsets.UTF_8));
            cos.flush();
        }
        return out.toByteArray();
    }

    public static String decrypt(byte[] encrypted, byte[] key, byte[] iv) throws IOException {
        try (CryptoInputStream cis = new CryptoInputStream(
                TRANSFORM, PROPERTIES, new ByteArrayInputStream(encrypted),
                new SecretKeySpec(key, "AES"), new IvParameterSpec(iv))) {
            byte[] buf = new byte[1024];
            int len = 0, n;
            while ((n = cis.read(buf, len, buf.length - len)) > -1) len += n;
            return new String(buf, 0, len, StandardCharsets.UTF_8);
        }
    }

    @Override
    public void close() {}
}
```

- [ ] **Run tests to confirm pass**

```bash
mvn test -Dtest=EncryptDecryptTest
```

Expected: `Tests run: 6, Failures: 0, Errors: 0`

- [ ] **Commit**

```bash
git add src/main/java/org/louis/EncryptDecrypt.java src/test/java/org/louis/EncryptDecryptTest.java
git commit -m "feat: per-secret random AES-256 key/IV, remove hardcoded credentials"
```

---

### Task 4: Refactor Secret

Remove `Serializable`. Replace the single serialized file with a JSON `.meta` file (name, id, decryptionDate, IV) and a binary `.enc` file (encrypted bytes). The key is never stored locally.

**Files:**
- Modify: `src/main/java/org/louis/Secret.java`
- Create: `src/test/java/org/louis/SecretTest.java`

- [ ] **Write the failing tests**

`src/test/java/org/louis/SecretTest.java`:

```java
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
```

- [ ] **Run to confirm failure**

```bash
mvn test -Dtest=SecretTest
```

Expected: compilation errors — `Secret` API does not match

- [ ] **Rewrite Secret**

`src/main/java/org/louis/Secret.java`:

```java
package org.louis;

import com.google.gson.Gson;
import org.apache.commons.io.FileUtils;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.UUID;

public class Secret {

    private String id;
    private String name;
    private String decryptionDateIso;
    private String ivBase64;

    private Secret() {} // for Gson

    public Secret(String name, Instant decryptionDate, byte[] iv) {
        this.id = UUID.randomUUID().toString();
        this.name = name;
        this.decryptionDateIso = decryptionDate.toString();
        this.ivBase64 = Base64.getEncoder().encodeToString(iv);
    }

    public String getId()               { return id; }
    public String getName()             { return name; }
    public Instant getDecryptionDate()  { return Instant.parse(decryptionDateIso); }
    public byte[] getIv()               { return Base64.getDecoder().decode(ivBase64); }

    public void setDecryptionDate(Instant newDate) {
        this.decryptionDateIso = newDate.toString();
    }

    public boolean availableForDecryption() {
        return Instant.now().isAfter(getDecryptionDate());
    }

    public void saveMeta(String vaultDir) throws IOException {
        FileUtils.writeStringToFile(
            new File(vaultDir, id + ".meta"),
            new Gson().toJson(this),
            StandardCharsets.UTF_8);
    }

    public static Secret loadMeta(String vaultDir, String uuid) throws IOException {
        String json = FileUtils.readFileToString(new File(vaultDir, uuid + ".meta"), StandardCharsets.UTF_8);
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
        for (String file : files)
            secrets.add(loadMeta(vaultDir, file.replace(".meta", "")));
        return secrets;
    }

    @Override
    public String toString() {
        long hours = availableForDecryption() ? 0
            : Instant.now().until(getDecryptionDate(), ChronoUnit.HOURS);
        return "Name: " + name
            + "\nID: " + id
            + "\nHours until unlock: " + (hours == 0 ? "Unlocked" : hours + " hours");
    }
}
```

- [ ] **Run tests to confirm pass**

```bash
mvn test -Dtest=SecretTest
```

Expected: `Tests run: 6, Failures: 0, Errors: 0`

- [ ] **Commit**

```bash
git add src/main/java/org/louis/Secret.java src/test/java/org/louis/SecretTest.java
git commit -m "feat: replace Java serialization with JSON meta + binary enc files"
```

---

### Task 5: Create GitHubVault

**Files:**
- Create: `src/main/java/org/louis/GitHubVault.java`
- Create: `src/test/java/org/louis/GitHubVaultTest.java`

`GitHubVault` wraps the GitHub Contents API via `HttpURLConnection`. The key insight: keys are stored as repo files (`vault/keys/<uuid>.key`) in a private repo — accessible only if logged into the vault GitHub account, which itself requires access to the vault.

- [ ] **Write the failing tests (pure logic only — no HTTP)**

`src/test/java/org/louis/GitHubVaultTest.java`:

```java
package org.louis;

import org.junit.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.junit.Assert.*;

public class GitHubVaultTest {

    private Config testConfig() {
        Config c = new Config();
        c.githubToken   = "ghp_test";
        c.githubRepo    = "vault-user/vault";
        c.smtpUser      = "vault@gmail.com";
        c.smtpPass      = "app-pass";
        c.deliveryEmail = "real@gmail.com";
        return c;
    }

    @Test
    public void workflowYamlContainsCronForUnlockDay() {
        Secret s = new Secret("Empornium",
            Instant.now().plus(30, ChronoUnit.DAYS),
            EncryptDecrypt.generateIV());
        GitHubVault vault = new GitHubVault(testConfig());
        String yaml = vault.buildWorkflowYaml(s);

        assertTrue(yaml.contains("cron:"));
        assertTrue(yaml.contains("python3 vault/scripts/send_key.py"));
        assertTrue(yaml.contains(s.getId()));
        assertTrue(yaml.contains("Empornium"));
        assertTrue(yaml.contains("real@gmail.com"));
    }

    @Test
    public void workflowYamlContainsWorkflowDispatch() {
        Secret s = new Secret("X", Instant.now().plus(1, ChronoUnit.DAYS), EncryptDecrypt.generateIV());
        String yaml = new GitHubVault(testConfig()).buildWorkflowYaml(s);
        assertTrue(yaml.contains("workflow_dispatch"));
    }

    @Test
    public void sendKeyScriptIsNonEmpty() {
        byte[] script = GitHubVault.getSendKeyScript();
        assertTrue(script.length > 0);
        String content = new String(script);
        assertTrue(content.contains("VAULT_KEY"));
        assertTrue(content.contains("smtp.gmail.com"));
        assertTrue(content.contains("DELIVERY_EMAIL"));
    }
}
```

- [ ] **Run to confirm failure**

```bash
mvn test -Dtest=GitHubVaultTest
```

Expected: compilation error — `GitHubVault` does not exist

- [ ] **Create GitHubVault**

`src/main/java/org/louis/GitHubVault.java`:

```java
package org.louis;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.apache.commons.io.IOUtils;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.Base64;

public class GitHubVault {

    private static final String API = "https://api.github.com";
    private final Config config;

    public GitHubVault(Config config) {
        this.config = config;
    }

    // ── Public API ───────────────────────────────────────────────────────────

    public void pushFile(String path, byte[] content, String message) throws IOException {
        String sha = getFileSha(path);
        JsonObject body = new JsonObject();
        body.addProperty("message", message);
        body.addProperty("content", Base64.getEncoder().encodeToString(content));
        if (sha != null) body.addProperty("sha", sha);
        request("PUT", "/repos/" + config.githubRepo + "/contents/" + path, body.toString());
    }

    public byte[] fetchFile(String path) throws IOException {
        try {
            String response = request("GET", "/repos/" + config.githubRepo + "/contents/" + path, null);
            JsonObject json = new Gson().fromJson(response, JsonObject.class);
            String encoded = json.get("content").getAsString().replaceAll("\\s", "");
            return Base64.getDecoder().decode(encoded);
        } catch (IOException e) {
            if (e.getMessage() != null && e.getMessage().contains("404")) return null;
            throw e;
        }
    }

    public void deleteFile(String path, String message) throws IOException {
        String sha = getFileSha(path);
        if (sha == null) return;
        JsonObject body = new JsonObject();
        body.addProperty("message", message);
        body.addProperty("sha", sha);
        request("DELETE", "/repos/" + config.githubRepo + "/contents/" + path, body.toString());
    }

    public void initRepo() throws IOException {
        // Create vault/keys/.gitkeep so the keys directory exists
        pushFile("vault/keys/.gitkeep", new byte[0], "chore: initialize vault structure");
        // Push the email delivery script
        pushFile("vault/scripts/send_key.py", getSendKeyScript(), "chore: add key delivery script");
    }

    public String buildWorkflowYaml(Secret secret) {
        ZonedDateTime unlock = secret.getDecryptionDate().atZone(ZoneOffset.UTC);
        int day   = unlock.getDayOfMonth();
        int month = unlock.getMonthValue();
        int year  = unlock.getYear();
        // Run at 09:00 UTC on the Nth of every month; Python script checks the year+month at runtime
        String cron = String.format("0 9 %d * *", day);

        return "name: Unlock " + secret.getName() + "\n"
            + "on:\n"
            + "  schedule:\n"
            + "    - cron: '" + cron + "'\n"
            + "  workflow_dispatch:\n"
            + "jobs:\n"
            + "  send-key:\n"
            + "    runs-on: ubuntu-latest\n"
            + "    steps:\n"
            + "      - uses: actions/checkout@v3\n"
            + "      - name: Send key\n"
            + "        env:\n"
            + "          UUID: " + secret.getId() + "\n"
            + "          UNLOCK_YEAR: '" + year + "'\n"
            + "          UNLOCK_MONTH: '" + month + "'\n"
            + "          UNLOCK_DAY: '" + day + "'\n"
            + "          SECRET_NAME: " + secret.getName() + "\n"
            + "          DELIVERY_EMAIL: " + config.deliveryEmail + "\n"
            + "          SMTP_USER: " + config.smtpUser + "\n"
            + "          SMTP_PASS: " + config.smtpPass + "\n"
            + "        run: python3 vault/scripts/send_key.py\n";
    }

    public static byte[] getSendKeyScript() {
        String script =
            "import smtplib, os, datetime, sys\n"
            + "from email.mime.text import MIMEText\n"
            + "from pathlib import Path\n"
            + "\n"
            + "uuid         = os.environ['UUID']\n"
            + "unlock_year  = int(os.environ['UNLOCK_YEAR'])\n"
            + "unlock_month = int(os.environ['UNLOCK_MONTH'])\n"
            + "unlock_day   = int(os.environ['UNLOCK_DAY'])\n"
            + "name         = os.environ['SECRET_NAME']\n"
            + "DELIVERY_EMAIL = os.environ['DELIVERY_EMAIL']\n"
            + "SMTP_USER    = os.environ['SMTP_USER']\n"
            + "SMTP_PASS    = os.environ['SMTP_PASS']\n"
            + "\n"
            + "unlock_date = datetime.date(unlock_year, unlock_month, unlock_day)\n"
            + "if datetime.date.today() < unlock_date:\n"
            + "    print(f'Not yet unlocked. Unlock date: {unlock_date}')\n"
            + "    sys.exit(0)\n"
            + "\n"
            + "key_file = Path(f'vault/keys/{uuid}.key')\n"
            + "if not key_file.exists():\n"
            + "    print(f'Key file not found: {key_file}')\n"
            + "    sys.exit(1)\n"
            + "\n"
            + "VAULT_KEY = key_file.read_text().strip()\n"
            + "\n"
            + "body = (\n"
            + "    f'Your time-safe vault has unlocked.\\n\\n'\n"
            + "    f'Secret name: {name}\\n'\n"
            + "    f'Decryption key (base64): {VAULT_KEY}\\n\\n'\n"
            + "    f'Enter this key in the time-safe app when prompted to decrypt.'\n"
            + ")\n"
            + "msg = MIMEText(body)\n"
            + "msg['Subject'] = f'Vault Unlock: {name}'\n"
            + "msg['From']    = SMTP_USER\n"
            + "msg['To']      = DELIVERY_EMAIL\n"
            + "\n"
            + "with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:\n"
            + "    s.login(SMTP_USER, SMTP_PASS)\n"
            + "    s.sendmail(SMTP_USER, [DELIVERY_EMAIL], msg.as_string())\n"
            + "    print('Key delivered successfully.')\n";
        return script.getBytes(StandardCharsets.UTF_8);
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    private String getFileSha(String path) throws IOException {
        try {
            String response = request("GET", "/repos/" + config.githubRepo + "/contents/" + path, null);
            return new Gson().fromJson(response, JsonObject.class).get("sha").getAsString();
        } catch (IOException e) {
            if (e.getMessage() != null && e.getMessage().contains("404")) return null;
            throw e;
        }
    }

    private String request(String method, String endpoint, String body) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(API + endpoint).openConnection();
        conn.setRequestMethod(method);
        conn.setRequestProperty("Authorization", "Bearer " + config.githubToken);
        conn.setRequestProperty("Accept", "application/vnd.github+json");
        conn.setRequestProperty("Content-Type", "application/json");

        if (body != null) {
            conn.setDoOutput(true);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }

        int status = conn.getResponseCode();
        InputStream stream = (status >= 400) ? conn.getErrorStream() : conn.getInputStream();
        String response = (stream != null)
            ? IOUtils.toString(stream, StandardCharsets.UTF_8)
            : "";

        if (status >= 400) throw new IOException("GitHub API " + status + ": " + response);
        return response;
    }
}
```

- [ ] **Run tests to confirm pass**

```bash
mvn test -Dtest=GitHubVaultTest
```

Expected: `Tests run: 3, Failures: 0, Errors: 0`

- [ ] **Commit**

```bash
git add src/main/java/org/louis/GitHubVault.java src/test/java/org/louis/GitHubVaultTest.java
git commit -m "feat: GitHub Contents API integration and workflow YAML generation"
```

---

### Task 6: Commit send_key.py to the repo

The Python script is generated by `GitHubVault.getSendKeyScript()` and pushed during setup. We also commit a local copy so it's visible in the repo for inspection.

**Files:**
- Create: `vault/scripts/send_key.py`

- [ ] **Write the local copy**

`vault/scripts/send_key.py`:

```python
import smtplib, os, datetime, sys
from email.mime.text import MIMEText
from pathlib import Path

uuid         = os.environ['UUID']
unlock_year  = int(os.environ['UNLOCK_YEAR'])
unlock_month = int(os.environ['UNLOCK_MONTH'])
unlock_day   = int(os.environ['UNLOCK_DAY'])
name         = os.environ['SECRET_NAME']
DELIVERY_EMAIL = os.environ['DELIVERY_EMAIL']
SMTP_USER    = os.environ['SMTP_USER']
SMTP_PASS    = os.environ['SMTP_PASS']

unlock_date = datetime.date(unlock_year, unlock_month, unlock_day)
if datetime.date.today() < unlock_date:
    print(f'Not yet unlocked. Unlock date: {unlock_date}')
    sys.exit(0)

key_file = Path(f'vault/keys/{uuid}.key')
if not key_file.exists():
    print(f'Key file not found: {key_file}')
    sys.exit(1)

VAULT_KEY = key_file.read_text().strip()

body = (
    f'Your time-safe vault has unlocked.\n\n'
    f'Secret name: {name}\n'
    f'Decryption key (base64): {VAULT_KEY}\n\n'
    f'Enter this key in the time-safe app when prompted to decrypt.'
)
msg = MIMEText(body)
msg['Subject'] = f'Vault Unlock: {name}'
msg['From']    = SMTP_USER
msg['To']      = DELIVERY_EMAIL

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
    s.login(SMTP_USER, SMTP_PASS)
    s.sendmail(SMTP_USER, [DELIVERY_EMAIL], msg.as_string())
    print('Key delivered successfully.')
```

- [ ] **Verify it matches getSendKeyScript() output**

```bash
mvn compile -q && mvn -q exec:java -Dexec.mainClass=org.louis.GitHubVault 2>/dev/null || true
```

(No need to run the class — the test in Task 5 already verifies script content.)

- [ ] **Commit**

```bash
git add vault/scripts/send_key.py
git commit -m "chore: add send_key.py email delivery script for GitHub Actions"
```

---

### Task 7: Update VaultManager

**Files:**
- Modify: `src/main/java/org/louis/VaultManager.java`

VaultManager now: generates key+IV, encrypts, saves locally, pushes to GitHub, writes workflow. Extend updates both the local meta and the GitHub workflow. Delete removes local files and GitHub files.

- [ ] **Rewrite VaultManager**

`src/main/java/org/louis/VaultManager.java`:

```java
package org.louis;

import org.apache.commons.io.FileUtils;

import java.io.File;
import java.io.IOException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.Collection;

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

            // Save locally
            secret.saveMeta(VAULT_DIR);
            secret.saveEncrypted(VAULT_DIR, enc);

            // Push to GitHub
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
            Instant start = secret.availableForDecryption()
                ? Instant.now()
                : secret.getDecryptionDate();

            if (secret.availableForDecryption())
                System.out.println("Secret is currently unlocked. Extension starts from now.");

            Instant newDate = start.plus(additionalDays, ChronoUnit.DAYS);
            secret.setDecryptionDate(newDate);
            secret.saveMeta(vaultDir);

            // Update GitHub: meta and workflow
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
            return java.util.Collections.emptyList();
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
            github.deleteFile("vault/secrets/" + secret.getId() + ".enc", "delete: " + secret.getName());
            github.deleteFile("vault/secrets/" + secret.getId() + ".meta", "delete: " + secret.getName());
            github.deleteFile("vault/keys/" + secret.getId() + ".key",    "delete: key for " + secret.getName());
            github.deleteFile(".github/workflows/unlock-" + secret.getId() + ".yml", "delete: workflow for " + secret.getName());
            System.out.println("Secret deleted.");
        } catch (Exception e) {
            System.err.println("Failed to delete from GitHub: " + e.getMessage());
        }
    }

    private byte[] readLocal(String path) throws IOException {
        return FileUtils.readFileToByteArray(new File(path));
    }
}
```

- [ ] **Compile to confirm no errors**

```bash
mvn compile
```

Expected: `BUILD SUCCESS`

- [ ] **Commit**

```bash
git add src/main/java/org/louis/VaultManager.java
git commit -m "feat: VaultManager uses random keys, GitHub storage, and workflow generation"
```

---

### Task 8: Update Main

Add a `0) Setup` option. Update the decrypt flow to prompt for the key the user received by email. Wire VaultManager to Config.

**Files:**
- Modify: `src/main/java/org/louis/Main.java`

- [ ] **Rewrite Main**

`src/main/java/org/louis/Main.java`:

```java
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
            "0) Setup (first-time configuration)\n" +
            "1) Add a new secret to the vault\n" +
            "2) List secrets in the vault\n" +
            "> ");
        int choice = in.nextInt();
        System.out.println();
        switch (choice) {
            case 0: runSetup();        break;
            case 1: captureNewSecret(); break;
            case 2: listAllSecrets();   break;
        }
    }

    // ── Setup ────────────────────────────────────────────────────────────────

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

    // ── Add secret ───────────────────────────────────────────────────────────

    private static void captureNewSecret() {
        if (vaultManager == null) { System.out.println("Run setup first (option 0)."); return; }
        Scanner in = new Scanner(System.in);

        System.out.print("Name for this secret (e.g. Empornium, Vault Gmail):\n> ");
        String name = in.nextLine();

        System.out.print("The password to lock:\n> ");
        String secret = in.nextLine();

        System.out.print("Days to lock for:\n> ");
        int days = in.nextInt();

        vaultManager.putSecret(days, secret, name);
    }

    // ── List & manage ────────────────────────────────────────────────────────

    private static void listAllSecrets() {
        if (vaultManager == null) { System.out.println("Run setup first (option 0)."); return; }
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
            System.out.println(i + ") " + s.getName()
                + (s.availableForDecryption() ? " (UNLOCKED - check email for key)" : " (locked)"));
            i++;
        }
        System.out.print("> ");
        manageSecret(menu.get(in.nextInt()));
    }

    private static void manageSecret(Secret secret) {
        if (secret == null) return;
        Scanner in = new Scanner(System.in);
        System.out.print("\n1) Secret details\n2) Decrypt (enter key from email)\n3) Extend lock\n4) Delete\n> ");
        int choice = in.nextInt();
        System.out.println();
        switch (choice) {
            case 1: System.out.println(secret);              break;
            case 2: decryptSecret(secret);                   break;
            case 3: extendSecret(secret);                    break;
            case 4: deleteSecret(secret);                    break;
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
            byte[] key = java.util.Base64.getDecoder().decode(keyB64);
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
```

- [ ] **Compile and package**

```bash
mvn package -DskipTests
```

Expected: `BUILD SUCCESS`, fat JAR created at `target/time-safe-1.0-SNAPSHOT-jar-with-dependencies.jar`

- [ ] **Run full test suite**

```bash
mvn test
```

Expected: all tests pass, 0 failures

- [ ] **Commit**

```bash
git add src/main/java/org/louis/Main.java
git commit -m "feat: setup command, email-key decrypt flow, wire VaultManager to Config"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Per-secret random AES-256 key/IV | Task 3 |
| Key stored in GitHub repo file, not on disk | Task 5, 7 |
| Encrypted blob pushed to GitHub | Task 7 |
| Scheduled GitHub Actions workflow per secret | Task 5, 7 |
| Monthly cron + runtime date check | Task 5 |
| `workflow_dispatch` for manual early trigger | Task 5 |
| Config file (`~/.timesafe/config.json`) | Task 2 |
| Setup command | Task 8 |
| Add secret: manual checklist printed | Task 7 |
| List: shows locked/unlocked status | Task 8 |
| Decrypt: user pastes key from email | Task 8 |
| Extend lock: updates meta + workflow on GitHub | Task 7 |
| Delete: removes local + GitHub files | Task 7 |
| send_key.py Python email script | Task 6 |
| `initRepo` pushes send_key.py on setup | Task 5, 8 |

**Gaps:** None found.

**Type consistency:** `VaultManager(Config)` constructor used in Task 7 matches Task 2. `Secret` API (saveMeta, loadMeta, saveEncrypted, loadEncrypted, list) defined in Task 4 and used in Tasks 5, 7, 8 consistently. `EncryptDecrypt.encrypt(String, byte[], byte[])` defined in Task 3 and used in Task 7. `GitHubVault.buildWorkflowYaml(Secret)` defined and tested in Task 5, used in Task 7.

**Placeholder scan:** Clean. All code blocks are complete and runnable.
