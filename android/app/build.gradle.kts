import java.util.Properties

plugins {
    id("com.android.application")
}

val localProperties = Properties().apply {
    val file = project.rootProject.file("local.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}
val releaseKeystore = (project.findProperty("inputbridge.keystore") as String?)
    ?: localProperties.getProperty("inputbridge.keystore")
val releaseStorePassword = (project.findProperty("inputbridge.storePassword") as String?)
    ?: localProperties.getProperty("inputbridge.storePassword")
val releaseKeyAlias = (project.findProperty("inputbridge.keyAlias") as String?)
    ?: localProperties.getProperty("inputbridge.keyAlias")
val releaseKeyPassword = (project.findProperty("inputbridge.keyPassword") as String?)
    ?: localProperties.getProperty("inputbridge.keyPassword")

android {
    namespace = "com.inputbridge.android"
    compileSdk = 37

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = project.file(releaseKeystore)
                storePassword = releaseStorePassword ?: ""
                keyAlias = releaseKeyAlias ?: ""
                keyPassword = releaseKeyPassword ?: ""
            }
        }
    }

    defaultConfig {
        applicationId = "com.inputbridge.android"
        minSdk = 26
        targetSdk = 37
        versionCode = 4
        versionName = "0.3.1-fix"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseKeystore != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.13.0")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
