# Dev Standards Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate from Maven/Java 8 to Gradle Kotlin DSL/Java 21, add Spotless + SpotBugs quality gates, GitHub Actions CI, and Dependabot.

**Architecture:** Gradle replaces Maven as the build tool. All quality checks (compile, test, style, security) run via `./gradlew check` both locally and in CI. Dependabot watches both `gradle` and `github-actions` ecosystems. Two Java source files are modernised to use Java 21 APIs (HttpClient, text blocks).

**Tech Stack:** Gradle 8.8 (Kotlin DSL), Java 21 (Temurin toolchain), Shadow plugin (fat JAR), Spotless + Google Java Format (style), SpotBugs + FindSecBugs (security), GitHub Actions, Dependabot.

---

## File Map

| File | Change |
|---|---|
| `pom.xml` | Delete |
| `settings.gradle.kts` | Create |
| `build.gradle.kts` | Create |
| `gradle/wrapper/gradle-wrapper.properties` | Create (generated) |
| `gradle/wrapper/gradle-wrapper.jar` | Create (generated) |
| `gradlew` | Create (generated) |
| `gradlew.bat` | Create (generated) |
| `config/spotbugs/exclude.xml` | Create |
| `src/main/java/org/louis/GitHubVault.java` | Modify (HttpClient + text block) |
| `.github/workflows/ci.yml` | Create |
| `.github/dependabot.yml` | Create |
| `README.md` | Modify (add badge) |

---

### Task 1: Bootstrap Gradle wrapper

Gradle is not installed globally. Use SDKMAN or Homebrew to get a temporary Gradle installation, generate the wrapper, then use `./gradlew` for everything afterwards.

**Files:**
- Create: `gradle/wrapper/gradle-wrapper.properties`
- Create: `gradle/wrapper/gradle-wrapper.jar`
- Create: `gradlew`
- Create: `gradlew.bat`
- Create: `settings.gradle.kts`

- [ ] **Install Gradle temporarily (if not present)**

```bash
brew install gradle
```

Or with SDKMAN:
```bash
sdk install gradle 8.8
```

- [ ] **Generate the wrapper**

Run from `/Users/pk/code/time-safe`:
```bash
gradle wrapper --gradle-version 8.8
```

Expected output ends with `BUILD SUCCESSFUL`. This creates `gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.jar`, and `gradle/wrapper/gradle-wrapper.properties`.

- [ ] **Create `settings.gradle.kts`**

```kotlin
rootProject.name = "time-safe"
```

- [ ] **Verify the wrapper works**

```bash
./gradlew --version
```

Expected: output containing `Gradle 8.8`

- [ ] **Commit**

```bash
git add gradlew gradlew.bat gradle/ settings.gradle.kts
git commit -m "chore: add Gradle 8.8 wrapper and settings"
```

---

### Task 2: Create `build.gradle.kts` and delete `pom.xml`

**Files:**
- Create: `build.gradle.kts`
- Delete: `pom.xml`

- [ ] **Create `build.gradle.kts`**

```kotlin
plugins {
    java
    application
    id("com.github.johnrengelman.shadow") version "8.1.1"
    id("com.diffplug.spotless") version "6.25.0"
    id("com.github.spotbugs") version "6.0.18"
}

group = "org.louis"
version = "1.0-SNAPSHOT"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

application {
    mainClass = "org.louis.Main"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.apache.commons:commons-crypto:1.2.0")
    implementation("org.apache.commons:commons-lang3:3.14.0")
    implementation("commons-io:commons-io:2.16.1")
    implementation("com.google.code.gson:gson:2.10.1")
    testImplementation("junit:junit:4.13.2")
    spotbugsPlugins("com.h3xstream.findsecbugs:findsecbugs-plugin:1.13.0")
}

spotless {
    java {
        googleJavaFormat()
    }
}

spotbugs {
    effort = com.github.spotbugs.snom.Effort.MAX
    reportLevel = com.github.spotbugs.snom.Confidence.HIGH
    excludeFilter = file("config/spotbugs/exclude.xml")
}

tasks.named<com.github.spotbugs.snom.SpotBugsTask>("spotbugsMain") {
    reports.create("html") { required = true }
}

tasks.test {
    useJUnit()
}
```

- [ ] **Delete `pom.xml`**

```bash
rm pom.xml
```

- [ ] **Compile Java sources**

```bash
./gradlew compileJava
```

Expected: `BUILD SUCCESSFUL`. Gradle downloads JDK 21 (Temurin) automatically if not present — this may take a minute on first run.

- [ ] **Run tests**

```bash
./gradlew test
```

Expected: `BUILD SUCCESSFUL`, 17 tests passing. Test report at `build/reports/tests/test/index.html`.

- [ ] **Commit**

```bash
git add build.gradle.kts
git rm pom.xml
git commit -m "chore: migrate from Maven to Gradle Kotlin DSL with Java 21 toolchain"
```

---

### Task 3: Create SpotBugs exclusion filter and run `./gradlew check`

SpotBugs with FindSecBugs will flag the AES/CBC mode used in `EncryptDecrypt` (cipher lacks authentication — CIPHER_INTEGRITY rule). This is an accepted trade-off for this project (documented in the spec). Suppress it with an exclusion filter.

**Files:**
- Create: `config/spotbugs/exclude.xml`

- [ ] **Create the exclusion filter**

```bash
mkdir -p config/spotbugs
```

`config/spotbugs/exclude.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<FindBugsFilter>
    <!-- AES/CBC without authentication is a known trade-off in this project.
         The time-lock mechanism provides the integrity guarantee, not the cipher. -->
    <Match>
        <Class name="org.louis.EncryptDecrypt"/>
        <Bug pattern="CIPHER_INTEGRITY"/>
    </Match>
</FindBugsFilter>
```

- [ ] **Run SpotBugs alone to see what it finds**

```bash
./gradlew spotbugsMain
```

If the build fails with findings other than CIPHER_INTEGRITY, add additional `<Match>` blocks to `exclude.xml` for each finding. The pattern name appears in the HTML report at `build/reports/spotbugs/main.html`. Add exclusions only for findings that are clearly false positives or accepted design decisions — fix real bugs instead.

- [ ] **Run full check**

```bash
./gradlew check
```

Expected: `BUILD SUCCESSFUL` — compile, test, spotlessCheck, and spotbugsMain all green.

If `spotlessCheck` fails (existing code not yet formatted), that is expected — Task 4 fixes it.

- [ ] **Commit**

```bash
git add config/spotbugs/exclude.xml
git commit -m "chore: add SpotBugs exclusion filter for accepted CBC cipher trade-off"
```

---

### Task 4: Apply Spotless formatting

Spotless enforces Google Java Format. Existing source files have not been formatted to this style yet. `spotlessApply` auto-fixes them all.

**Files:**
- Modify: all `.java` files under `src/`

- [ ] **Apply formatting**

```bash
./gradlew spotlessApply
```

Expected: Spotless reformats whichever files need it (import ordering, spacing, brace placement). No logic changes.

- [ ] **Run the full check to confirm everything is green**

```bash
./gradlew check
```

Expected: `BUILD SUCCESSFUL` — all 17 tests pass, `spotlessCheck` passes, `spotbugsMain` passes.

- [ ] **Commit all reformatted files**

```bash
git add src/
git commit -m "style: apply Google Java Format via Spotless"
```

---

### Task 5: Upgrade `GitHubVault` to `HttpClient` and text block

Replace `HttpURLConnection` with `java.net.http.HttpClient` (Java 11+, now available under Java 21). Replace the 20-line string concatenation in `buildWorkflowYaml` with a text block. Also update `actions/checkout@v3` → `v4` in the generated workflow YAML.

**Files:**
- Modify: `src/main/java/org/louis/GitHubVault.java`

- [ ] **Read the current GitHubVault.java**

Read `/Users/pk/code/time-safe/src/main/java/org/louis/GitHubVault.java` in full before editing.

- [ ] **Replace imports**

Remove:
```java
import org.apache.commons.io.IOUtils;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
```

Add:
```java
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
```

The existing imports `com.google.gson.*`, `java.nio.charset.StandardCharsets`, `java.time.*`, `java.util.Base64` remain unchanged.

- [ ] **Replace the `request` field and method**

Remove the existing `request(String, String, String)` method entirely. Add:

```java
private final HttpClient http = HttpClient.newHttpClient();

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
            throw new IOException(
                "GitHub API " + response.statusCode() + ": " + response.body());
        return response.body();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new IOException("Request interrupted", e);
    }
}
```

- [ ] **Replace `buildWorkflowYaml` with a text block**

Replace the entire `buildWorkflowYaml` method with:

```java
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
                      SMTP_USER: %s
                      SMTP_PASS: %s
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
            config.deliveryEmail,
            config.smtpUser,
            config.smtpPass);
}
```

Note: the closing `"""` is at 12 spaces indent. The content lines start at 12 spaces. Java strips 12 spaces from every line, producing clean YAML with no leading whitespace on `name:`, `on:`, `jobs:`, etc.

- [ ] **Run check**

```bash
./gradlew check
```

Expected: `BUILD SUCCESSFUL`, 17 tests pass. If `spotlessCheck` fails, run `./gradlew spotlessApply` then re-run `./gradlew check`.

- [ ] **Commit**

```bash
git add src/main/java/org/louis/GitHubVault.java
git commit -m "feat: replace HttpURLConnection with HttpClient; use text block for workflow YAML"
```

---

### Task 6: Add GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Create the workflow directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle.kts', 'gradle/wrapper/gradle-wrapper.properties') }}
          restore-keys: ${{ runner.os }}-gradle-

      - name: Make gradlew executable
        run: chmod +x gradlew

      - name: Check
        run: ./gradlew check

      - name: Upload SpotBugs report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: spotbugs-report
          path: build/reports/spotbugs/
```

- [ ] **Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (compile, test, Spotless, SpotBugs)"
```

---

### Task 7: Add Dependabot

**Files:**
- Create: `.github/dependabot.yml`

- [ ] **Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: "gradle"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
```

- [ ] **Commit**

```bash
git add .github/dependabot.yml
git commit -m "chore: add Dependabot for Gradle and GitHub Actions dependencies"
```

---

### Task 8: Add CI badge to README

**Files:**
- Modify: `README.md`

- [ ] **Read the current README.md first**

Read `/Users/pk/code/time-safe/README.md` to find the first line.

- [ ] **Insert badge after the first heading**

Add this line immediately after `# TimeSafe for Secrets` (the first line of README.md):

```markdown
[![CI](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml/badge.svg)](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml)
```

- [ ] **Commit**

```bash
git add README.md
git commit -m "docs: add CI status badge"
```

---

### Task 9: Push and verify CI

- [ ] **Push all commits to GitHub**

```bash
git push origin master
```

- [ ] **Verify CI runs**

Open `https://github.com/louisalexander/time-safe/actions` in a browser. The `CI` workflow should appear and run. Confirm it completes green.

If CI fails, download the SpotBugs artifact from the failed run, read `main.html`, and add the appropriate exclusion to `config/spotbugs/exclude.xml`, then commit and push.

- [ ] **Verify Dependabot is active**

Open `https://github.com/louisalexander/time-safe/network/updates`. Dependabot should show two configured update targets (gradle, github-actions). First PRs may appear within a day.

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Gradle Kotlin DSL + Gradle 8.8 wrapper | Task 1, 2 |
| Java 21 toolchain | Task 2 |
| Shadow plugin (fat JAR) | Task 2 |
| Spotless + Google Java Format | Task 2, 4 |
| SpotBugs + FindSecBugs + exclusion filter | Task 2, 3 |
| `./gradlew check` runs all gates | Task 3 |
| Delete pom.xml | Task 2 |
| HttpClient (Java 21) | Task 5 |
| Text block for workflow YAML (Java 21) | Task 5 |
| actions/checkout v4 in generated YAML | Task 5 |
| GitHub Actions CI workflow | Task 6 |
| Dependabot (gradle + github-actions) | Task 7 |
| README CI badge | Task 8 |
| Push + verify CI green | Task 9 |

**Placeholder scan:** Clean. All code blocks are complete.

**Type consistency:** `GitHubVault.buildWorkflowYaml(Secret)` signature unchanged. `request(String, String, String)` signature unchanged. `GitHubVaultTest` assertions (`yaml.contains("cron:")`, `yaml.contains(s.getId())`, etc.) still pass with text block output.
