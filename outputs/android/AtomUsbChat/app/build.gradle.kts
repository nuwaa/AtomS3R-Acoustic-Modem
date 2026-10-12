plugins { id("com.android.application") }
android {
    namespace = "jp.jn1eep.atomusbchat"
    compileSdk = 37
    defaultConfig { applicationId = "jp.jn1eep.atomusbchat"; minSdk = 26; targetSdk = 37; versionCode = 18; versionName = "0.3.6" }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
