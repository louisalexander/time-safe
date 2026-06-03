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
