package ziops

private object VersionResource

val APP_VERSION: String = java.util.Properties().run {
    checkNotNull(VersionResource::class.java.getResourceAsStream("/app-version.properties")) { "Missing application version" }.use { load(it) }
    getProperty("app.version").also { version ->
        require(version.matches(Regex("\\d+(\\.\\d+){3}"))) { "Application version must contain four numbers" }
    }
}
