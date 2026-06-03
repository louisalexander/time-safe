package org.louis;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.goterl.lazysodium.LazySodiumJava;
import com.goterl.lazysodium.SodiumJava;
import com.goterl.lazysodium.interfaces.Box;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.Base64;

public class GitHubVault {

  private static final String API = "https://api.github.com";
  private final Config config;
  private final HttpClient http = HttpClient.newHttpClient();
  private final LazySodiumJava sodium = new LazySodiumJava(new SodiumJava());

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
    pushFile("vault/keys/.gitkeep", new byte[0], "chore: initialize vault structure");
    pushFile("vault/scripts/send_key.py", getSendKeyScript(), "chore: add key delivery script");
    setRepoSecret("SMTP_USER", config.smtpUser);
    setRepoSecret("SMTP_PASS", config.smtpPass);
  }

  public String buildWorkflowYaml(Secret secret) {
    ZonedDateTime unlock = secret.getDecryptionDate().atZone(ZoneOffset.UTC);
    int day = unlock.getDayOfMonth();
    int month = unlock.getMonthValue();
    int year = unlock.getYear();

    return """
          name: Unlock %s
          on:
            schedule:
              - cron: '0 9 %d %d *'
            workflow_dispatch:
          jobs:
            send-key:
              runs-on: ubuntu-latest
              steps:
                - uses: actions/checkout@v4
                - name: Send key
                  env:
                    UUID: %s
                    UNLOCK_YEAR: '%d'
                    UNLOCK_MONTH: '%d'
                    UNLOCK_DAY: '%d'
                    SECRET_NAME: %s
                    DELIVERY_EMAIL: %s
                    SMTP_USER: ${{ secrets.SMTP_USER }}
                    SMTP_PASS: ${{ secrets.SMTP_PASS }}
                  run: python3 vault/scripts/send_key.py
          """
        .formatted(
            secret.getName(),
            day,
            month,
            secret.getId(),
            year,
            month,
            day,
            secret.getName(),
            config.deliveryEmail);
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

  public void setRepoSecret(String name, String value) throws IOException {
    String keyResponse =
        request("GET", "/repos/" + config.githubRepo + "/actions/secrets/public-key", null);
    JsonObject keyJson = new Gson().fromJson(keyResponse, JsonObject.class);
    String keyId = keyJson.get("key_id").getAsString();
    byte[] recipientPublicKey = Base64.getDecoder().decode(keyJson.get("key").getAsString());

    byte[] plaintext = value.getBytes(StandardCharsets.UTF_8);
    byte[] ciphertext = new byte[plaintext.length + Box.SEALBYTES];
    sodium.getSodium().crypto_box_seal(ciphertext, plaintext, plaintext.length, recipientPublicKey);

    JsonObject body = new JsonObject();
    body.addProperty("encrypted_value", Base64.getEncoder().encodeToString(ciphertext));
    body.addProperty("key_id", keyId);
    request("PUT", "/repos/" + config.githubRepo + "/actions/secrets/" + name, body.toString());
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
    var bodyPublisher =
        body != null
            ? HttpRequest.BodyPublishers.ofString(body)
            : HttpRequest.BodyPublishers.noBody();

    var req =
        HttpRequest.newBuilder()
            .uri(URI.create(API + endpoint))
            .header("Authorization", "Bearer " + config.githubToken)
            .header("Accept", "application/vnd.github+json")
            .header("Content-Type", "application/json")
            .method(method, bodyPublisher)
            .build();

    try {
      HttpResponse<String> response = http.send(req, HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() >= 400)
        throw new IOException("GitHub API " + response.statusCode() + ": " + response.body());
      return response.body();
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IOException("Request interrupted", e);
    }
  }
}
