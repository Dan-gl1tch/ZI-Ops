package ziops

import java.nio.file.Files
import java.nio.file.Path

fun applicationDataDirectory(): Path {
    val home = Path.of(System.getProperty("user.home"))
    return if (System.getProperty("os.name").startsWith("Windows", ignoreCase = true)) {
        val local = System.getenv("LOCALAPPDATA")?.takeIf { it.isNotBlank() }?.let(Path::of)
            ?: home.resolve("AppData/Local")
        local.resolve("ZI-Ops")
    } else {
        val config = System.getenv("XDG_CONFIG_HOME")?.takeIf { it.isNotBlank() }?.let(Path::of)
            ?: home.resolve(".config")
        config.resolve("zi-ops")
    }
}

fun legacySettingsCandidates(): List<Path> {
    val current = Path.of("config.json").toAbsolutePath().normalize()
    val executable = ProcessHandle.current().info().command().orElse(null)?.let(Path::of)
    val adjacent = executable?.takeIf { it.fileName.toString().equals("ZI-Ops.exe", ignoreCase = true) }
        ?.parent?.resolve("config.json")
    return listOfNotNull(current, adjacent).distinct()
}

fun openApplicationSettings(directory: Path = applicationDataDirectory(), legacy: List<Path> = legacySettingsCandidates()): Settings {
    val target = directory.resolve("config.json")
    val settings = Settings(target)
    if (!Files.exists(target)) {
        val previous = legacy.firstOrNull { Files.isRegularFile(it) && it.toAbsolutePath().normalize() != target.toAbsolutePath().normalize() }
        if (previous != null) {
            settings.load(previous)
            settings.save()
        }
    }
    return settings
}
