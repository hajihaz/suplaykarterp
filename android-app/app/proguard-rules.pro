# Keep the JavaScript bridge and WebView internals readable in release builds.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
