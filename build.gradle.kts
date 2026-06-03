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
    implementation("com.google.code.gson:gson:2.14.0")
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
