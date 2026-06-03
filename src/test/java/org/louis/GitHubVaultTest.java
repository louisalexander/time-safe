package org.louis;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
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
        String content = new String(script, StandardCharsets.UTF_8);
        assertTrue(content.contains("VAULT_KEY"));
        assertTrue(content.contains("smtp.gmail.com"));
        assertTrue(content.contains("DELIVERY_EMAIL"));
    }
}
