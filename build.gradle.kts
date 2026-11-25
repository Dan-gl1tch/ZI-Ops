import java.util.Properties

plugins {
    kotlin("jvm") version "2.1.20"
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"
    id("org.jetbrains.compose") version "1.8.2"
}
val appVersion = Properties().apply {
    file("src/main/resources/app-version.properties").inputStream().use { load(it) }
}.getProperty("app.version")
require(appVersion.matches(Regex("\\d+(\\.\\d+){3}"))) { "Use language.feature.code.visual version format" }
version = appVersion

kotlin { jvmToolchain(21) }
dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("commons-net:commons-net:3.11.1")
}
compose.desktop {
    application {
        mainClass = "ziops.MainKt"
        nativeDistributions {
            modules("java.net.http", "java.naming", "jdk.crypto.ec", "jdk.unsupported", "java.management")
            targetFormats(org.jetbrains.compose.desktop.application.dsl.TargetFormat.Exe)
            packageName = "ZI-Ops"
            // jpackage accepts three numbers; the application and portable EXE use the full version.
            packageVersion = appVersion.split(".").take(3).joinToString(".")
            windows { menuGroup = "ZI-Ops"; shortcut = true; iconFile.set(project.file("src/main/resources/ZI-Ops.ico")) }
        }
    }
}
