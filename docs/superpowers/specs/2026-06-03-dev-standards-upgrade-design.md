# Dev Standards Upgrade Design

## Goal

Migrate from Maven to Gradle (Kotlin DSL), upgrade Java 8 → 21, add GitHub Actions CI, add Dependabot, and integrate Spotless + SpotBugs so that `./gradlew check` enforces compile, tests, code style, and security analysis locally and in CI.

---

## Section 1: Gradle Build

### Files

| File | Action |
|---|---|
| `pom.xml` | Delete |
| `settings.gradle.kts` | Create |
| `build.gradle.kts` | Create |

### `settings.gradle.kts`

```kotlin
rootProject.name = "time-safe"
```

### `build.gradle.kts` structure

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
}

tasks.named<com.github.spotbugs.snom.SpotBugsTask>("spotbugsMain") {
    reports.create("html") { required = true }
}

tasks.test {
    useJUnit()
}
```

**Gradle wrapper** — generated via `gradle wrapper --gradle-version 8.7` then committed (`gradlew`, `gradlew.bat`, `gradle/wrapper/`). CI uses the wrapper so the Gradle version is pinned in version control.

**Key notes:**
- Dependencies are bumped to current versions (not just Java 21 compat — also picks up security fixes)
- Shadow plugin produces `build/libs/time-safe-all.jar` — same fat-JAR behaviour as `maven-assembly-plugin`
- `./gradlew check` runs: `compileJava` → `test` → `spotlessCheck` → `spotbugsMain`
- `./gradlew spotlessApply` auto-fixes formatting
- `./gradlew shadowJar` produces the runnable fat JAR

---

## Section 2: GitHub Actions CI

### File: `.github/workflows/ci.yml`

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

**Trigger:** push to `master`, all PRs targeting `master`.

**On failure:** SpotBugs HTML report uploaded as a build artifact, downloadable from the Actions run page.

---

## Section 3: Dependabot

### File: `.github/dependabot.yml`

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

**Behaviour:**
- Weekly PRs for all Gradle dependency updates (runtime, test, plugins)
- Weekly PRs for GitHub Actions version updates (`actions/checkout@v3` → `v4` etc.)
- All PRs get a `dependencies` label — no auto-merge, manual review

---

## Section 4: Java 21 Code Improvements

Two targeted source changes alongside the tooling migration:

### 4a. `GitHubVault` — `HttpURLConnection` → `HttpClient`

Replace the `HttpURLConnection`-based `request()` method with `java.net.http.HttpClient`. Cleaner API, proper builder pattern, no manual stream handling.

```java
private final HttpClient http = HttpClient.newHttpClient();

private String request(String method, String endpoint, String body) throws IOException {
    var builder = HttpRequest.newBuilder()
        .uri(URI.create(API + endpoint))
        .header("Authorization", "Bearer " + config.githubToken)
        .header("Accept", "application/vnd.github+json")
        .header("Content-Type", "application/json");

    var bodyPublisher = body != null
        ? HttpRequest.BodyPublishers.ofString(body)
        : HttpRequest.BodyPublishers.noBody();
    builder.method(method, bodyPublisher);

    try {
        var response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 400)
            throw new IOException("GitHub API " + response.statusCode() + ": " + response.body());
        return response.body();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new IOException("Request interrupted", e);
    }
}
```

### 4b. `GitHubVault.buildWorkflowYaml` — text block

Replace the 20-line string concatenation with a text block so the YAML structure is visible and auditable:

```java
public String buildWorkflowYaml(Secret secret) {
    ZonedDateTime unlock = secret.getDecryptionDate().atZone(ZoneOffset.UTC);
    int day   = unlock.getDayOfMonth();
    int month = unlock.getMonthValue();
    int year  = unlock.getYear();

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
        """.formatted(
            secret.getName(), day, month,
            secret.getId(), year, month, day,
            secret.getName(), config.deliveryEmail,
            config.smtpUser, config.smtpPass);
}
```

---

## README Badge

Add to top of `README.md`:

```markdown
[![CI](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml/badge.svg)](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml)
```

---

## What Is Not In Scope

- Migrating from JUnit 4 to JUnit 5 (separate task if desired)
- Fixing SpotBugs findings in existing code (will be addressed when CI flags them)
- Checkstyle or any second linter
