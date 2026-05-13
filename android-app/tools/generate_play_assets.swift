import AppKit
import Foundation
import WebKit

let fileManager = FileManager.default
let outputRoot = URL(fileURLWithPath: CommandLine.arguments.dropFirst().first ?? "android-app/play-assets", isDirectory: true)
let screenshotsDir = outputRoot.appendingPathComponent("screenshots", isDirectory: true)

let brandAccent = NSColor(calibratedRed: 72.0 / 255.0, green: 151.0 / 255.0, blue: 177.0 / 255.0, alpha: 1.0)
let brandDark = NSColor(calibratedRed: 19.0 / 255.0, green: 31.0 / 255.0, blue: 36.0 / 255.0, alpha: 1.0)
let brandSand = NSColor(calibratedRed: 244.0 / 255.0, green: 235.0 / 255.0, blue: 214.0 / 255.0, alpha: 1.0)
let brandCream = NSColor(calibratedRed: 250.0 / 255.0, green: 246.0 / 255.0, blue: 236.0 / 255.0, alpha: 1.0)
let brandMuted = NSColor(calibratedWhite: 1.0, alpha: 0.68)

final class PageSnapshotter: NSObject, WKNavigationDelegate {
    let webView: WKWebView
    let semaphore = DispatchSemaphore(value: 0)
    private(set) var succeeded = false

    override init() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.preferences.setValue(true, forKey: "developerExtrasEnabled")
        self.webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        webView.customUserAgent = "Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Mobile Safari/537.36"
    }

    func snapshot(url: URL, size: CGSize, to destination: URL) throws {
        webView.frame = NSRect(origin: .zero, size: size)
        let request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData, timeoutInterval: 60)
        _ = webView.load(request)

        while semaphore.wait(timeout: .now() + 0.1) == .timedOut {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.05))
        }

        guard succeeded else {
            throw NSError(domain: "PlayAssetGeneration", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to load \(url.absoluteString)"])
        }

        Thread.sleep(forTimeInterval: 3.0)
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.2))

        let config = WKSnapshotConfiguration()
        config.rect = CGRect(origin: .zero, size: size)

        let imageSemaphore = DispatchSemaphore(value: 0)
        var snapshotImage: NSImage?
        var snapshotError: Error?
        webView.takeSnapshot(with: config) { image, error in
            snapshotImage = image
            snapshotError = error
            imageSemaphore.signal()
        }

        while imageSemaphore.wait(timeout: .now() + 0.1) == .timedOut {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.05))
        }

        if let snapshotError {
            throw snapshotError
        }

        guard let snapshotImage else {
            throw NSError(domain: "PlayAssetGeneration", code: 2, userInfo: [NSLocalizedDescriptionKey: "Snapshot missing for \(url.absoluteString)"])
        }

        try save(image: snapshotImage, to: destination)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        succeeded = true
        semaphore.signal()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        succeeded = false
        semaphore.signal()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        succeeded = false
        semaphore.signal()
    }
}

func ensureDirectory(_ url: URL) throws {
    try fileManager.createDirectory(at: url, withIntermediateDirectories: true)
}

func pngData(from image: NSImage) throws -> Data {
    guard
        let tiffData = image.tiffRepresentation,
        let bitmap = NSBitmapImageRep(data: tiffData),
        let png = bitmap.representation(using: .png, properties: [:])
    else {
        throw NSError(domain: "PlayAssetGeneration", code: 3, userInfo: [NSLocalizedDescriptionKey: "Unable to convert image to PNG"])
    }
    return png
}

func save(image: NSImage, to url: URL) throws {
    let data = try pngData(from: image)
    try data.write(to: url)
}

func attributed(_ text: String, size: CGFloat, weight: NSFont.Weight = .regular, color: NSColor, kern: CGFloat = 0.0) -> NSAttributedString {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .left
    paragraph.lineBreakMode = .byWordWrapping
    return NSAttributedString(
        string: text,
        attributes: [
            .font: NSFont.systemFont(ofSize: size, weight: weight),
            .foregroundColor: color,
            .kern: kern,
            .paragraphStyle: paragraph,
        ]
    )
}

func roundedRect(_ rect: CGRect, radius: CGFloat, fill: NSColor, stroke: NSColor? = nil, lineWidth: CGFloat = 0) {
    let path = NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius)
    fill.setFill()
    path.fill()
    if let stroke {
        stroke.setStroke()
        path.lineWidth = lineWidth
        path.stroke()
    }
}

func drawMark(in rect: CGRect, strokeColor: NSColor, fillColor: NSColor) {
    let inset = rect.insetBy(dx: rect.width * 0.16, dy: rect.height * 0.16)
    let border = NSBezierPath(rect: inset)
    border.lineWidth = rect.width * 0.045
    strokeColor.setStroke()
    border.stroke()

    let barWidth = rect.width * 0.11
    let barHeight = rect.height * 0.42
    let gap = rect.width * 0.12
    let leftBar = NSBezierPath(rect: CGRect(x: inset.minX + rect.width * 0.08, y: inset.minY + rect.height * 0.05, width: barWidth, height: barHeight))
    let rightBar = NSBezierPath(rect: CGRect(x: inset.minX + rect.width * 0.08 + barWidth + gap, y: inset.minY + rect.height * 0.05, width: barWidth, height: barHeight))
    let crossBar = NSBezierPath(rect: CGRect(x: inset.minX + rect.width * 0.08 + barWidth, y: inset.minY + rect.height * 0.21, width: gap, height: rect.height * 0.10))
    fillColor.setFill()
    leftBar.fill()
    rightBar.fill()
    crossBar.fill()
}

func generateIcon() throws {
    let size = NSSize(width: 512, height: 512)
    let image = NSImage(size: size)
    image.lockFocus()

    let background = NSBezierPath(roundedRect: CGRect(origin: .zero, size: size), xRadius: 110, yRadius: 110)
    let gradient = NSGradient(colors: [brandDark, NSColor(calibratedRed: 10.0 / 255.0, green: 21.0 / 255.0, blue: 24.0 / 255.0, alpha: 1.0)])!
    gradient.draw(in: background, angle: 225)

    let orbRect = CGRect(x: 60, y: 300, width: 180, height: 180)
    let orb = NSBezierPath(ovalIn: orbRect)
    let orbGradient = NSGradient(colors: [brandAccent.withAlphaComponent(0.92), brandAccent.withAlphaComponent(0.30)])!
    orbGradient.draw(in: orb, angle: -90)

    let glow = NSBezierPath(ovalIn: CGRect(x: 286, y: 74, width: 162, height: 162))
    NSColor.white.withAlphaComponent(0.06).setFill()
    glow.fill()

    drawMark(in: CGRect(x: 112, y: 92, width: 288, height: 288), strokeColor: brandAccent, fillColor: brandAccent)

    image.unlockFocus()
    try save(image: image, to: outputRoot.appendingPathComponent("icon-512.png"))
}

func generateFeatureGraphic() throws {
    let size = NSSize(width: 1024, height: 500)
    let image = NSImage(size: size)
    image.lockFocus()

    let bg = NSBezierPath(rect: CGRect(origin: .zero, size: size))
    let gradient = NSGradient(colors: [
        brandDark,
        NSColor(calibratedRed: 28.0 / 255.0, green: 44.0 / 255.0, blue: 51.0 / 255.0, alpha: 1.0),
        NSColor(calibratedRed: 20.0 / 255.0, green: 31.0 / 255.0, blue: 35.0 / 255.0, alpha: 1.0),
    ])!
    gradient.draw(in: bg, angle: 0)

    roundedRect(CGRect(x: 574, y: 82, width: 372, height: 336), radius: 34, fill: NSColor.white.withAlphaComponent(0.08))
    roundedRect(CGRect(x: 600, y: 112, width: 320, height: 52), radius: 20, fill: NSColor.white.withAlphaComponent(0.12))
    roundedRect(CGRect(x: 600, y: 182, width: 320, height: 92), radius: 28, fill: brandSand.withAlphaComponent(0.92))
    roundedRect(CGRect(x: 600, y: 292, width: 148, height: 82), radius: 24, fill: NSColor.white.withAlphaComponent(0.10))
    roundedRect(CGRect(x: 772, y: 292, width: 148, height: 82), radius: 24, fill: NSColor.white.withAlphaComponent(0.10))

    NSColor.white.withAlphaComponent(0.14).setFill()
    NSBezierPath(ovalIn: CGRect(x: 488, y: 32, width: 220, height: 220)).fill()
    NSBezierPath(ovalIn: CGRect(x: 90, y: 244, width: 290, height: 290)).fill()

    drawMark(in: CGRect(x: 88, y: 120, width: 186, height: 186), strokeColor: brandAccent, fillColor: brandAccent)

    attributed("HajiHaz AI", size: 52, weight: .bold, color: NSColor.white, kern: 0.3)
        .draw(in: CGRect(x: 304, y: 308, width: 240, height: 70))
    attributed("Your grounded business AI workspace", size: 20, weight: .semibold, color: brandSand)
        .draw(in: CGRect(x: 304, y: 268, width: 320, height: 40))
    attributed("Live chat, retrieval, admin controls, and web-assisted answers in one clean mobile app shell.", size: 18, weight: .regular, color: brandMuted)
        .draw(in: CGRect(x: 304, y: 170, width: 250, height: 84))
    attributed("Powered by AllBee Solutions", size: 16, weight: .medium, color: brandAccent)
        .draw(in: CGRect(x: 304, y: 118, width: 260, height: 28))

    image.unlockFocus()
    try save(image: image, to: outputRoot.appendingPathComponent("feature-graphic-1024x500.png"))
}

func annotateScreenshot(_ source: URL, destination: URL, title: String, subtitle: String, accentLabel: String) throws {
    let sourceImage = NSImage(contentsOf: source)
    guard let sourceImage else {
        throw NSError(domain: "PlayAssetGeneration", code: 4, userInfo: [NSLocalizedDescriptionKey: "Missing source screenshot \(source.lastPathComponent)"])
    }

    let canvasSize = NSSize(width: 1242, height: 2208)
    let image = NSImage(size: canvasSize)
    image.lockFocus()

    let background = NSGradient(colors: [brandCream, NSColor(calibratedRed: 244.0 / 255.0, green: 240.0 / 255.0, blue: 230.0 / 255.0, alpha: 1.0)])!
    background.draw(in: NSBezierPath(rect: CGRect(origin: .zero, size: canvasSize)), angle: 90)

    roundedRect(CGRect(x: 72, y: 1828, width: 1098, height: 228), radius: 48, fill: NSColor.white.withAlphaComponent(0.92))
    attributed(title, size: 58, weight: .bold, color: brandDark)
        .draw(in: CGRect(x: 124, y: 1948, width: 860, height: 74))
    attributed(subtitle, size: 26, weight: .regular, color: brandDark.withAlphaComponent(0.72))
        .draw(in: CGRect(x: 124, y: 1876, width: 920, height: 70))
    attributed(accentLabel, size: 24, weight: .semibold, color: brandAccent)
        .draw(in: CGRect(x: 124, y: 1840, width: 420, height: 36))

    let frameRect = CGRect(x: 150, y: 170, width: 942, height: 1618)
    let shadow = NSShadow()
    shadow.shadowBlurRadius = 36
    shadow.shadowOffset = NSSize(width: 0, height: -10)
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.16)
    shadow.set()
    roundedRect(frameRect, radius: 94, fill: brandDark)
    NSGraphicsContext.current?.saveGraphicsState()
    let clip = NSBezierPath(roundedRect: frameRect.insetBy(dx: 28, dy: 28), xRadius: 70, yRadius: 70)
    clip.addClip()
    sourceImage.draw(in: frameRect.insetBy(dx: 28, dy: 28))
    NSGraphicsContext.current?.restoreGraphicsState()

    roundedRect(CGRect(x: 498, y: 1680, width: 246, height: 34), radius: 17, fill: NSColor.white.withAlphaComponent(0.18))
    roundedRect(CGRect(x: 418, y: 153, width: 406, height: 20), radius: 10, fill: brandDark.withAlphaComponent(0.45))

    image.unlockFocus()
    try save(image: image, to: destination)
}

func generateWebSnapshots() throws {
    try ensureDirectory(screenshotsDir)
    let snapshotter = PageSnapshotter()
    try snapshotter.snapshot(
        url: URL(string: "https://hajihazai.allbeesolutions.com/")!,
        size: CGSize(width: 430, height: 932),
        to: screenshotsDir.appendingPathComponent("raw-home.png")
    )
    try snapshotter.snapshot(
        url: URL(string: "https://hajihazai.allbeesolutions.com/admin")!,
        size: CGSize(width: 430, height: 932),
        to: screenshotsDir.appendingPathComponent("raw-admin.png")
    )
}

func generateShowcaseScreens() throws {
    try annotateScreenshot(
        outputRoot.appendingPathComponent("screenshots/raw-home.png"),
        destination: outputRoot.appendingPathComponent("screenshots/phone-1-home.png"),
        title: "Grounded business answers",
        subtitle: "Ask naturally and get responses shaped by your live knowledge base plus online context when needed.",
        accentLabel: "HajiHaz AI"
    )
    try annotateScreenshot(
        outputRoot.appendingPathComponent("screenshots/raw-admin.png"),
        destination: outputRoot.appendingPathComponent("screenshots/phone-2-admin.png"),
        title: "Control the knowledge layer",
        subtitle: "Manage documents, sources, runtime health, and monitoring from one focused admin workspace.",
        accentLabel: "Admin workspace"
    )
}

try ensureDirectory(outputRoot)
try ensureDirectory(screenshotsDir)
try generateIcon()
try generateFeatureGraphic()
try generateWebSnapshots()
try generateShowcaseScreens()
print("Play assets generated at \(outputRoot.path)")
