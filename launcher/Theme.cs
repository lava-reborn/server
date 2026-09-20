// The design system of the site, restated for GDI+.
//
// Colours and type are the "wasteland" theme of lava-site/design/tokens.json,
// name for name. Nothing here invents a shade: a launcher that is one hair off
// the site reads as a different product, and the site is the reference.
//
// Everything is laid out in logical pixels against a 920x576 window, and the
// whole drawing is scaled by Theme.S at paint time. That is why no number in
// the layout code is ever multiplied by hand -- the form paints through a
// ScaleTransform, and child controls get their bounds through Theme.R().
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;
using System.Windows.Forms;

static class Theme
{
    // --- tokens -----------------------------------------------------------
    public static readonly Color BgVoid = C(0x0a, 0x09, 0x08);
    public static readonly Color BgBase = C(0x14, 0x11, 0x0e);
    public static readonly Color BgPanel = C(0x1c, 0x18, 0x15);
    public static readonly Color BgRaised = C(0x26, 0x21, 0x1c);
    public static readonly Color BgInset = C(0x0f, 0x0d, 0x0b);
    public static readonly Color Line = C(0x33, 0x2c, 0x25);
    public static readonly Color LineStrong = C(0x7d, 0x71, 0x60);
    public static readonly Color Ink = C(0xef, 0xe8, 0xd9);
    public static readonly Color InkMuted = C(0xb3, 0xa8, 0x94);
    public static readonly Color InkFaint = C(0x8a, 0x80, 0x71);
    public static readonly Color Brand = C(0xd9, 0xa4, 0x41);
    public static readonly Color BrandHover = C(0xe8, 0xb7, 0x5b);
    public static readonly Color OnBrand = C(0x14, 0x11, 0x0e);
    public static readonly Color Danger = C(0xe2, 0x54, 0x3a);
    public static readonly Color Success = C(0x8b, 0xb7, 0x5a);
    public static readonly Color Focus = C(0xf0, 0xc4, 0x6a);

    static Color C(int r, int g, int b) { return Color.FromArgb(r, g, b); }

    // --- scale ------------------------------------------------------------
    // The window is designed at 96 dpi and scaled from there. Without this the
    // whole thing is either blurry (Windows stretches an unaware window) or
    // postage-stamp small on the screens people actually have.
    public static float Scale = 1f;

    public static int S(double logical) { return (int)Math.Round(logical * Scale); }

    public static Rectangle R(int x, int y, int w, int h)
    {
        return new Rectangle(S(x), S(y), S(w), S(h));
    }

    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    [DllImport("gdi32.dll")]
    static extern int GetDeviceCaps(IntPtr hdc, int index);

    public static void Init()
    {
        try { SetProcessDPIAware(); }
        catch { /* pre-Vista only; the layout just stays at 1x */ }
        try
        {
            using (Graphics g = Graphics.FromHwnd(IntPtr.Zero))
                Scale = g.DpiX / 96f;
        }
        catch { Scale = 1f; }
        if (Scale < 1f) Scale = 1f;
        if (Scale > 3f) Scale = 3f;
    }

    // --- type -------------------------------------------------------------
    // The site sets Oswald for display and Golos Text for body. Neither ships
    // with Windows, so each name is a list: the first family actually
    // installed wins. Arial Narrow carries the condensed, tracked capitals the
    // display style is really about, and it is on every Windows there is.
    static readonly string[] DisplayFamilies =
        { "Oswald", "Arial Narrow", "Segoe UI Semibold", "Segoe UI" };
    static readonly string[] BodyFamilies =
        { "Golos Text", "Onest", "Segoe UI", "Tahoma" };
    static readonly string[] MonoFamilies =
        { "JetBrains Mono", "Cascadia Mono", "Consolas", "Courier New" };

    static string displayName, bodyName, monoName;
    static readonly Dictionary<string, Font> cache = new Dictionary<string, Font>();

    static string Pick(string[] wanted)
    {
        HashSet<string> have = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            foreach (FontFamily f in FontFamily.Families) have.Add(f.Name);
        }
        catch { }
        foreach (string name in wanted)
            if (have.Contains(name)) return name;
        return wanted[wanted.Length - 1];
    }

    // Every font here is in LOGICAL pixels, because everything this program
    // paints is painted through a ScaleTransform(Scale). Scaling the font as
    // well would scale the text twice, and at 125% that shows up as text
    // spilling out of a layout that is otherwise correct.
    static Font Get(string family, double px, FontStyle style, bool device)
    {
        string key = family + "/" + px.ToString("0.##") + "/" + (int)style + (device ? "d" : "l");
        Font f;
        if (cache.TryGetValue(key, out f)) return f;
        f = new Font(family, (float)(device ? px * Scale : px), style, GraphicsUnit.Pixel);
        cache[key] = f;
        return f;
    }

    public static Font Display(double px, bool bold)
    {
        if (displayName == null) displayName = Pick(DisplayFamilies);
        return Get(displayName, px, bold ? FontStyle.Bold : FontStyle.Regular, false);
    }

    public static Font Body(double px, bool bold)
    {
        if (bodyName == null) bodyName = Pick(BodyFamilies);
        return Get(bodyName, px, bold ? FontStyle.Bold : FontStyle.Regular, false);
    }

    public static Font Mono(double px)
    {
        if (monoName == null) monoName = Pick(MonoFamilies);
        return Get(monoName, px, FontStyle.Regular, false);
    }

    // The one exception: a real WinForms control draws its own text with no
    // transform of ours, so its font has to carry the scale itself.
    public static Font DeviceBody(double px, bool bold)
    {
        if (bodyName == null) bodyName = Pick(BodyFamilies);
        return Get(bodyName, px, bold ? FontStyle.Bold : FontStyle.Regular, true);
    }

    // Opens a paint in logical units: the transform goes on, and the caller
    // gets the control's size in the units the layout is written in.
    public static SizeF Logical(Graphics g, Control c)
    {
        g.ScaleTransform(Scale, Scale);
        return new SizeF(c.Width / Scale, c.Height / Scale);
    }

    // --- drawing ----------------------------------------------------------
    public static readonly StringFormat Typo = MakeTypo();

    static StringFormat MakeTypo()
    {
        StringFormat sf = (StringFormat)StringFormat.GenericTypographic.Clone();
        sf.FormatFlags |= StringFormatFlags.NoWrap | StringFormatFlags.NoClip;
        return sf;
    }

    public static void Smooth(Graphics g)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
    }

    public static void Text(Graphics g, string s, Font f, Color c, float x, float y)
    {
        using (SolidBrush b = new SolidBrush(c))
            g.DrawString(s, f, b, x, y, Typo);
    }

    public static float Width(Graphics g, string s, Font f)
    {
        return g.MeasureString(s, f, PointF.Empty, Typo).Width;
    }

    // GDI+ has no letter-spacing, and the display styles are nothing without
    // it: eyebrow is 0.16em, the wordmark 0.08em. So the run is drawn a
    // character at a time with the extra advance added by hand.
    public static float Tracked(Graphics g, string s, Font f, Color c,
                                float x, float y, float tracking)
    {
        using (SolidBrush b = new SolidBrush(c))
        {
            foreach (char ch in s)
            {
                string one = ch.ToString();
                g.DrawString(one, f, b, x, y, Typo);
                x += g.MeasureString(one, f, PointF.Empty, Typo).Width + tracking;
            }
        }
        return x;
    }

    public static float TrackedWidth(Graphics g, string s, Font f, float tracking)
    {
        float w = 0;
        foreach (char ch in s)
            w += g.MeasureString(ch.ToString(), f, PointF.Empty, Typo).Width + tracking;
        return w - (s.Length > 0 ? tracking : 0);
    }

    public static GraphicsPath Round(RectangleF r, float radius)
    {
        GraphicsPath p = new GraphicsPath();
        if (radius <= 0) { p.AddRectangle(r); return p; }
        float d = radius * 2;
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    public static void Fill(Graphics g, RectangleF r, float radius, Color c)
    {
        using (GraphicsPath p = Round(r, radius))
        using (SolidBrush b = new SolidBrush(c))
            g.FillPath(b, p);
    }

    public static void Stroke(Graphics g, RectangleF r, float radius, Color c, float w)
    {
        // Half a pixel in, so a one-pixel line lands on the pixel instead of
        // straddling two of them and coming out grey.
        RectangleF rr = new RectangleF(r.X + w / 2f, r.Y + w / 2f,
                                       r.Width - w, r.Height - w);
        using (GraphicsPath p = Round(rr, Math.Max(0, radius - w / 2f)))
        using (Pen pen = new Pen(c, w))
            g.DrawPath(pen, p);
    }
}
