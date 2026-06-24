import SwiftUI
import AppKit

/// Design tokens for the Text Replacement Studio redesign.
///
/// Ported from the `Text Replacement Studio.dc.html` Claude Design comp: a calm,
/// content-first surface. Hierarchy comes from weight + secondary/tertiary text
/// colors, not extra type sizes. Color roles carry light/dark variants via
/// dynamic `NSColor` providers so the app tracks the system appearance without an
/// asset catalog.
enum Theme {

    // MARK: Color roles (light / dark)

    /// Window / content background — `#FFFFFF` light, `#1E1E20` dark.
    static let window      = dynamic(light: 0xFFFFFF, dark: 0x1E1E20)
    /// Sidebar & toolbar fill — `#ECEBE7` light, `#252528` dark.
    static let sidebar     = dynamic(light: 0xECEBE7, dark: 0x252528)
    /// Elevated controls / search field / phrase well — `#F4F3EF` light, `#2B2B2E` dark.
    static let elevated    = dynamic(light: 0xF4F3EF, dark: 0x2B2B2E)
    /// Primary text — `#1D1D1F` light, `#F5F5F7` dark.
    static let text        = dynamic(light: 0x1D1D1F, dark: 0xF5F5F7)
    /// Secondary text — `#86868B` light, `#98989E` dark.
    static let text2       = dynamic(light: 0x86868B, dark: 0x98989E)
    /// Tertiary text — `#B2B2B7` light, `#69696E` dark.
    static let text3       = dynamic(light: 0xB2B2B7, dark: 0x69696E)
    /// Accent — `#2F6BED` light, `#4D86FF` dark.
    static let accent      = dynamic(light: 0x2F6BED, dark: 0x4D86FF)
    /// 10% / 16% accent tint used for the selected row & active filter fill.
    static let accentSoft  = dynamicA(light: (0x2F6BED, 0.10), dark: (0x4D86FF, 0.16))
    /// Hairline separator — 7% black / 9% white.
    static let separator   = dynamicA(light: (0x000000, 0.07), dark: (0xFFFFFF, 0.09))
    /// Lighter hairline — 5% black / 6% white.
    static let separator2  = dynamicA(light: (0x000000, 0.05), dark: (0xFFFFFF, 0.06))
    /// Row hover / chip fill — 4.5% black / 6% white.
    static let hover       = dynamicA(light: (0x000000, 0.045), dark: (0xFFFFFF, 0.06))
    /// Window border.
    static let windowBorder = dynamicA(light: (0x000000, 0.08), dark: (0xFFFFFF, 0.10))

    /// Key-cap fill / border / bottom-highlight.
    static let keycapBG     = dynamic(light: 0xF1F0EB, dark: 0x333337)
    static let keycapBorder = dynamicA(light: (0x000000, 0.10), dark: (0xFFFFFF, 0.12))
    static let keycapShadow = dynamicA(light: (0x000000, 0.06), dark: (0x000000, 0.20))

    /// Toggle "off" track.
    static let switchOff = Color(red: 120/255, green: 120/255, blue: 128/255, opacity: 0.28)

    // MARK: Semantic (diff)

    static let diffAdd    = Color(hex: 0x1F9D55)
    static let diffUpdate = Color(hex: 0x2F6BED)
    static let diffRemove = Color(hex: 0xD14343)

    // MARK: Spacing (8pt rhythm) & radii

    enum Space {
        static let xs: CGFloat = 4, s: CGFloat = 8, m: CGFloat = 12
        static let l: CGFloat = 16, xl: CGFloat = 24, xxl: CGFloat = 32
    }
    enum Radius {
        static let control: CGFloat = 6, row: CGFloat = 8, window: CGFloat = 11, sheet: CGFloat = 14
    }

    // MARK: Type ramp — SF Pro / SF Mono, three sizes only

    /// 17 · Semibold — titles, shortcut, stats.
    static let display = Font.system(size: 17, weight: .semibold)
    /// 13 · Regular — list, controls, editor body.
    static let body    = Font.system(size: 13)
    /// 13 · Medium — emphasized body (selected row, control labels).
    static let bodyMed = Font.system(size: 13, weight: .medium)
    /// 11 · Semibold, tracked, uppercased — section labels, counts, status.
    static let caption = Font.system(size: 11, weight: .semibold)
    /// SF Mono 13 — key-caps.
    static let mono    = Font.system(size: 13, design: .monospaced).weight(.medium)
    /// SF Mono 11 — small mono (⌘F hint, counts).
    static let monoSmall = Font.system(size: 11, design: .monospaced)

    // MARK: Motion

    static let spring = Animation.spring(response: 0.35, dampingFraction: 0.82)

    // MARK: Helpers

    private static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { $0.isDark ? NSColor(hex: dark) : NSColor(hex: light) })
    }
    private static func dynamicA(light: (UInt32, Double), dark: (UInt32, Double)) -> Color {
        Color(nsColor: NSColor(name: nil) {
            $0.isDark ? NSColor(hex: dark.0, alpha: dark.1) : NSColor(hex: light.0, alpha: light.1)
        })
    }
}

// MARK: - Group colors (oklch 0.62 0.11 H)

extension Theme {
    /// Hue ramp for group tags, matching the comp's named groups; unknown groups
    /// get a deterministic hue from the name so colors stay stable across launches.
    static func groupColor(_ name: String?) -> Color {
        guard let name, !name.isEmpty else { return text3 }
        let known: [String: (Double, Double, Double)] = [
            "personal": (0.62, 0.11, 255),
            "work":     (0.62, 0.11, 305),
            "dev":      (0.64, 0.12, 70),
            "urls":     (0.62, 0.10, 200),
            "snippets": (0.62, 0.12, 350),
        ]
        if let p = known[name.lowercased()] {
            return oklch(p.0, p.1, p.2)
        }
        // Stable hue from a simple string hash (FNV-1a, 32-bit).
        var hash: UInt32 = 2166136261
        for b in name.utf8 { hash = (hash ^ UInt32(b)) &* 16777619 }
        return oklch(0.62, 0.11, Double(hash % 360))
    }

    /// Convert an OKLCH color to a SwiftUI `Color` in sRGB.
    static func oklch(_ l: Double, _ c: Double, _ hDeg: Double) -> Color {
        let h = hDeg * .pi / 180
        let a = c * cos(h), b = c * sin(h)
        // OKLab → LMS (cube roots) → linear sRGB
        let l_ = l + 0.3963377774 * a + 0.2158037573 * b
        let m_ = l - 0.1055613458 * a - 0.0638541728 * b
        let s_ = l - 0.0894841775 * a - 1.2914855480 * b
        let L = l_ * l_ * l_, M = m_ * m_ * m_, S = s_ * s_ * s_
        let r =  4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S
        let g = -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S
        let bl = -0.0041960863 * L - 0.7034186147 * M + 1.7076147010 * S
        func gamma(_ x: Double) -> Double {
            let v = x <= 0.0031308 ? 12.92 * x : 1.055 * pow(x, 1 / 2.4) - 0.055
            return min(1, max(0, v))
        }
        return Color(red: gamma(r), green: gamma(g), blue: gamma(bl))
    }
}

// MARK: - Color / NSColor hex

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

extension NSColor {
    convenience init(hex: UInt32, alpha: Double = 1) {
        self.init(
            srgbRed: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: CGFloat(alpha)
        )
    }
}

extension NSAppearance {
    /// True when the effective appearance is one of the dark variants.
    var isDark: Bool {
        bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
    }
}
