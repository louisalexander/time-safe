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
