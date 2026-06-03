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
        pushFile("vault/keys/.gitkeep", new byte[0], "chore: initialize vault structure");
        pushFile("vault/scripts/send_key.py", getSendKeyScript(), "chore: add key delivery script");
    }

    public String buildWorkflowYaml(Secret secret) {
        ZonedDateTime unlock = secret.getDecryptionDate().atZone(ZoneOffset.UTC);
        int day   = unlock.getDayOfMonth();
        int month = unlock.getMonthValue();
        int year  = unlock.getYear();
        String cron = String.format("0 9 %d %d *", day, month);

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
