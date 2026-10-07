// The design system of the launcher, restated for GDI+.
//
// Colours and type follow the launcher concept (graphite and orange, the
// sixth iteration of the mock-up the owner approved), value for value: the
// hex codes below are the ones in its stylesheet. Nothing here invents a
// shade.
//
// Everything is laid out in logical pixels against a 1120x606 window, and the
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
    // Surfaces.
    public static readonly Color Bg = C(0x191a1e);          // window, title bar
    public static readonly Color BgAuth = C(0x1e1f24);      // right column
    public static readonly Color BgPanel = C(0x1b1c21);     // resource panel
    public static readonly Color BgHero = C(0x2a2827);      // under the photograph
    public static readonly Color BgField = C(0x131418);
    public static readonly Color BgDialog = C(0x22232a);
    public static readonly Color BgDialogFoot = C(0x1d1e24);
    public static readonly Color BgPath = C(0x15161b);
    public static readonly Color Backdrop = C(0x08090c);

    // Lines.
    public static readonly Color WindowEdge = C(0x414149);
    public static readonly Color Hairline = A(0xffffff, 0x12);
    public static readonly Color LineAuth = A(0xffffff, 0x0d);
    public static readonly Color LinePanel = C(0x3a3433);
    public static readonly Color LineTitle = A(0xffffff, 0x19);
    public static readonly Color LineField = C(0x36373f);
    public static readonly Color LineCard = C(0x3c3d46);
    public static readonly Color LineDialog = C(0x51515e);
    public static readonly Color LinePath = C(0x444452);

    // Ink.
    public static readonly Color Ink = C(0xf5f5f6);
    public static readonly Color InkField = C(0xf1f1f5);
    public static readonly Color InkMuted = C(0xa9a9b0);
    public static readonly Color InkLabel = C(0xbcbcc5);
    public static readonly Color InkStats = C(0xa6a6b2);
    public static readonly Color InkEta = C(0xe0dfe6);
    public static readonly Color InkHint = C(0xa2a2ae);
    public static readonly Color InkFoot = C(0xa5a5b0);
    public static readonly Color InkPlaceholder = C(0x85858f);
    public static readonly Color InkServer = C(0xc9c9d3);
    public static readonly Color InkServerBad = C(0xffb3ae);
    public static readonly Color InkLink = C(0xc7c7cf);
    public static readonly Color InkLinkFoot = C(0xc3c3cf);
    public static readonly Color InkLinkStatus = C(0xbcbcc8);
    public static readonly Color InkRegister = C(0xe6e6ec);
    public static readonly Color InkRemember = C(0xbcbcc6);
    public static readonly Color InkMeta = C(0xb3b3be);
    public static readonly Color InkMetaIcon = C(0x8f8f9b);
    public static readonly Color InkVersion = C(0xc9c9d3);
    public static readonly Color InkPath = C(0xd6d6de);
    public static readonly Color InkDialog = C(0xb9b9c5);
    public static readonly Color InkDialogLabel = C(0xe6e6ec);
    public static readonly Color InkDialogPath = C(0xdad9e5);
    public static readonly Color InkDialogStrong = C(0xd2d2dd);
    public static readonly Color InkDialogClose = C(0xb1b1bf);

    // Accent and tones.
    public static readonly Color Accent = C(0xfa7148);
    public static readonly Color AccentHover = C(0xff8865);
    public static readonly Color AccentDown = C(0xe9643e);
    public static readonly Color OnAccent = C(0x191a1e);
    public static readonly Color AccentSoft = C(0xffb398);     // "Что нового", footer links
    public static readonly Color AccentSoftHover = C(0xffd2c2);
    public static readonly Color AccentIcon = C(0xf9916e);     // avatar
    public static readonly Color AccentDiamond = C(0xff946c);
    public static readonly Color Green = C(0x92c9b1);
    public static readonly Color Online = C(0x3ee07f);   // the server dot when it answers: greener than Green, and alive
    public static readonly Color Red = C(0xff8a85);
    public static readonly Color RedTitle = C(0xffb3ae);
    public static readonly Color Paused = C(0xb5b5c1);
    public static readonly Color PausedFill = C(0x8c8c9b);

    // Buttons.
    public static readonly Color BtnBg = C(0x23242a);
    public static readonly Color BtnLine = C(0x464650);
    public static readonly Color BtnInk = C(0xdddde4);
    public static readonly Color BtnBgHover = C(0x303139);
    public static readonly Color BtnLineHover = C(0x646473);
    public static readonly Color BtnOffBg = C(0x2b2c33);
    public static readonly Color BtnOffLine = C(0x3e3f48);
    public static readonly Color BtnOffInk = C(0x9999a5);
    public static readonly Color SetBtnBg = C(0x2a2b31);
    public static readonly Color SetBtnBgHover = C(0x34353c);
    public static readonly Color ToolBg = C(0x25262d);
    public static readonly Color ToolLine = C(0x3b3d46);
    public static readonly Color ToolInk = C(0xbfc2ce);
    public static readonly Color ToolBgHover = C(0x30323b);
    public static readonly Color ToolLineHover = C(0x70727f);
    public static readonly Color ToolInkHover = C(0xf1f2f6);
    public static readonly Color ToolDown = C(0x383a45);
    public static readonly Color CloseBg = C(0xa14236);
    public static readonly Color CloseLine = C(0xb85445);
    public static readonly Color CloseInk = C(0xfff4f0);
    public static readonly Color CloseDown = C(0x87372d);
    public static readonly Color Track = C(0x36363e);

    public static Color C(int rgb)
    {
        return Color.FromArgb((rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff);
    }

    public static Color A(int rgb, int alpha)
    {
        return Color.FromArgb(alpha, (rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff);
    }

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
    // The concept sets Bahnschrift for display and Segoe UI for body, both of
    // which ship with Windows 10 and later; Consolas for the monospaced bits.
    // Each name is still a list, so a stripped-down Windows gets the nearest
    // thing rather than a fallback chosen by GDI+. Weights above regular are
    // separate families on Windows (Bahnschrift SemiBold, Segoe UI Semibold),
    // so the semibold variants have lists of their own.
    static readonly string[] DisplayFamilies =
        { "Bahnschrift", "Arial Narrow", "Segoe UI" };
    static readonly string[] DisplaySemiFamilies =
        { "Bahnschrift SemiBold", "Bahnschrift", "Arial Narrow", "Segoe UI Semibold", "Segoe UI" };
    static readonly string[] BodyFamilies =
        { "Segoe UI", "Tahoma" };
    static readonly string[] BodySemiFamilies =
        { "Segoe UI Semibold", "Segoe UI", "Tahoma" };
    static readonly string[] MonoFamilies =
        { "Consolas", "Cascadia Mono", "Courier New" };

    static string displayName, displaySemiName, bodyName, bodySemiName, monoName;
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

    // A family list that names a semibold face falls back to the regular
    // family in bold when the face is missing, so the weight is still there.
    static Font Weighted(ref string chosen, string[] families, string[] regular, double px)
    {
        if (chosen == null) chosen = Pick(families);
        bool synthetic = string.Equals(chosen, regular[0], StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(chosen, regular[regular.Length - 1], StringComparison.OrdinalIgnoreCase);
        return Get(chosen, px, synthetic ? FontStyle.Bold : FontStyle.Regular, false);
    }

    public static Font Display(double px)
    {
        if (displayName == null) displayName = Pick(DisplayFamilies);
        return Get(displayName, px, FontStyle.Regular, false);
    }

    // The concept's titles are weight 500, which Bahnschrift has no named
    // face for; against the mock-up SemiBold is the match and Regular reads
    // thin, so the titles take the semibold face.
    public static Font DisplayTitle(double px) { return DisplaySemi(px); }

    public static Font DisplaySemi(double px)
    {
        return Weighted(ref displaySemiName, DisplaySemiFamilies, DisplayFamilies, px);
    }

    public static Font Body(double px)
    {
        if (bodyName == null) bodyName = Pick(BodyFamilies);
        return Get(bodyName, px, FontStyle.Regular, false);
    }

    public static Font BodySemi(double px)
    {
        return Weighted(ref bodySemiName, BodySemiFamilies, BodyFamilies, px);
    }

    public static Font Mono(double px)
    {
        if (monoName == null) monoName = Pick(MonoFamilies);
        return Get(monoName, px, FontStyle.Regular, false);
    }

    // The one exception: a real WinForms control draws its own text with no
    // transform of ours, so its font has to carry the scale itself.
    public static Font DeviceBody(double px)
    {
        if (bodyName == null) bodyName = Pick(BodyFamilies);
        return Get(bodyName, px, FontStyle.Regular, true);
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
        // Text is not drawn by GDI+ at all (see Text below); this is for
        // the one place that still asks GDI+ to measure.
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
    }

    // --- text -------------------------------------------------------------
    //
    // Text goes through GDI (TextRenderer), not GDI+. GDI+ sets type softly
    // whatever the hint -- grey antialiasing smears it, its ClearType comes
    // out thin with fringes -- while GDI is what every native window uses:
    // hinted, pixel-snapped, with the system's own ClearType. GDI knows no
    // world transform, so each call maps the logical point to the device
    // pixel itself and draws with a font of the device size.
    const TextFormatFlags FLAGS = TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix |
                                  TextFormatFlags.SingleLine | TextFormatFlags.NoClipping |
                                  TextFormatFlags.PreserveGraphicsClipping;

    static readonly Dictionary<Font, Font> deviceOf = new Dictionary<Font, Font>();

    // The device-sized twin of a logical font.
    static Font Device(Font f)
    {
        Font d;
        if (deviceOf.TryGetValue(f, out d)) return d;
        d = Scale == 1f ? f : Get(f.FontFamily.Name, f.Size, f.Style, true);
        deviceOf[f] = d;
        return d;
    }

    public static void Text(Graphics g, string s, Font f, Color c, float x, float y)
    {
        if (string.IsNullOrEmpty(s)) return;
        GraphicsState st = g.Save();
        g.ResetTransform();
        Glyphs(g, s, Device(f), (int)Math.Round(x * Scale), (int)Math.Round(y * Scale), c);
        g.Restore(st);
    }

    // Text over the photograph is set without ClearType's colour fringes,
    // which a busy picture turns into noise (a browser does the same over an
    // image). OverImage is raised by the panel that paints on the picture
    // and lowered when it is done.
    public static bool OverImage;

    // One run of glyphs at a device point, through GDI; over an image, GDI
    // draws it white on black off screen and the coverage of each pixel
    // becomes the text colour's alpha, so the shapes are GDI's hinted shapes
    // and the colour is one colour.
    static void Glyphs(Graphics g, string s, Font d, int dx, int dy, Color c)
    {
        if (!OverImage)
        {
            TextRenderer.DrawText(g, s, d, new Point(dx, dy), c, FLAGS);
            return;
        }
        Size sz = TextRenderer.MeasureText(g, s, d, new Size(int.MaxValue, int.MaxValue), FLAGS);
        int w = sz.Width + 2, h = sz.Height + 2;
        if (w <= 2 || h <= 2) return;
        using (Bitmap bm = new Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
        {
            using (Graphics bg = Graphics.FromImage(bm))
            {
                bg.Clear(Color.Black);
                TextRenderer.DrawText(bg, s, d, new Point(1, 1), Color.White, FLAGS);
            }
            System.Drawing.Imaging.BitmapData data = bm.LockBits(
                new Rectangle(0, 0, w, h), System.Drawing.Imaging.ImageLockMode.ReadWrite,
                System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            try
            {
                int n = w * h;
                int[] px = new int[n];
                System.Runtime.InteropServices.Marshal.Copy(data.Scan0, px, 0, n);
                int cr = c.R, cg = c.G, cb = c.B;
                for (int i = 0; i < n; i++)
                {
                    int v = px[i];
                    int r = (v >> 16) & 0xff, gg = (v >> 8) & 0xff, b = v & 0xff;
                    int cover = Math.Max(r, Math.Max(gg, b));
                    int a = cover * c.A / 255;
                    // Premultiplied is not asked for (Format32bppArgb), so the
                    // colour stays as it is and only the alpha varies.
                    px[i] = (a << 24) | (cr << 16) | (cg << 8) | cb;
                }
                System.Runtime.InteropServices.Marshal.Copy(px, 0, data.Scan0, n);
            }
            finally { bm.UnlockBits(data); }
            InterpolationMode old = g.InterpolationMode;
            PixelOffsetMode oldPo = g.PixelOffsetMode;
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = PixelOffsetMode.Half;
            g.DrawImage(bm, new Rectangle(dx - 1, dy - 1, w, h), 0, 0, w, h, GraphicsUnit.Pixel);
            g.InterpolationMode = old;
            g.PixelOffsetMode = oldPo;
        }
    }

    // The height of a line of this font, in logical pixels.
    public static float Height(Graphics g, Font f)
    {
        return Device(f).GetHeight(g) / Scale;
    }

    // Text set on a CSS-style line box: the glyphs are centred in a box of
    // the given height, which is how every line in the concept is measured.
    public static void Line(Graphics g, string s, Font f, Color c, float x, float top, float height)
    {
        Text(g, s, f, c, x, top + (height - Height(g, f)) / 2f);
    }

    public static void LineRight(Graphics g, string s, Font f, Color c, float right, float top, float height)
    {
        Line(g, s, f, c, right - Width(g, s, f), top, height);
    }

    public static float Width(Graphics g, string s, Font f)
    {
        if (string.IsNullOrEmpty(s)) return 0;
        return TextRenderer.MeasureText(g, s, Device(f), new Size(int.MaxValue, int.MaxValue), FLAGS).Width / Scale;
    }

    // The widest prefix of s that fits, with an ellipsis where it was cut.
    public static string Clip(Graphics g, string s, Font f, float room)
    {
        if (Width(g, s, f) <= room) return s;
        while (s.Length > 1 && Width(g, s + "…", f) > room)
            s = s.Substring(0, s.Length - 1);
        return s + "…";
    }

    // GDI has no letter-spacing, and the display styles are nothing without
    // it. So the run is drawn a character at a time with the extra advance
    // added by hand. Each step is the growth of the prefix's width, so
    // kerning holds and a space is a space; GDI measures in whole device
    // pixels, so the steps are exactly the advances it draws with, and the
    // gaps come out even. Returns the x after the last character.
    public static float Tracked(Graphics g, string s, Font f, Color c,
                                float x, float y, float tracking)
    {
        if (string.IsNullOrEmpty(s)) return x;
        Font d = Device(f);
        GraphicsState st = g.Save();
        g.ResetTransform();
        int dx = (int)Math.Round(x * Scale), dy = (int)Math.Round(y * Scale);
        float step = tracking * Scale, carry = 0;
        int prev = 0;
        for (int i = 0; i < s.Length; i++)
        {
            Glyphs(g, s[i].ToString(), d, dx, dy, c);
            int w = TextRenderer.MeasureText(g, s.Substring(0, i + 1), d,
                                             new Size(int.MaxValue, int.MaxValue), FLAGS).Width;
            // The tracking may be fractional at this scale: carried, so it is
            // not lost to rounding and not doubled either.
            carry += step;
            int add = (int)Math.Round(carry);
            carry -= add;
            dx += (w - prev) + add;
            prev = w;
        }
        g.Restore(st);
        return dx / Scale;
    }

    public static void TrackedLine(Graphics g, string s, Font f, Color c,
                                   float x, float top, float height, float tracking)
    {
        Tracked(g, s, f, c, x, top + (height - Height(g, f)) / 2f, tracking);
    }

    public static float TrackedWidth(Graphics g, string s, Font f, float tracking)
    {
        if (string.IsNullOrEmpty(s)) return 0;
        return Width(g, s, f) + tracking * (s.Length - 1);
    }

    // Words wrapped to a width, for the few paragraphs the dialogs have.
    public static List<string> Wrap(Graphics g, string text, Font f, float width)
    {
        List<string> lines = new List<string>();
        string cur = "";
        foreach (string word in text.Split(' '))
        {
            string next = cur.Length == 0 ? word : cur + " " + word;
            if (cur.Length > 0 && Width(g, next, f) > width) { lines.Add(cur); cur = word; }
            else cur = next;
        }
        if (cur.Length > 0) lines.Add(cur);
        return lines;
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

    // A filled, bordered box in one call: every button, field and card here
    // is one of these.
    public static void Box(Graphics g, RectangleF r, float radius, Color fill, Color line)
    {
        Fill(g, r, radius, fill);
        if (line.A > 0) Stroke(g, r, radius, line, 1);
    }

    public static void HLine(Graphics g, float x, float y, float w, Color c)
    {
        using (SolidBrush b = new SolidBrush(c))
            g.FillRectangle(b, x, y, w, 1);
    }

    public static void VLine(Graphics g, float x, float y, float h, Color c)
    {
        using (SolidBrush b = new SolidBrush(c))
            g.FillRectangle(b, x, y, 1, h);
    }

    public static void Dot(Graphics g, float cx, float cy, float d, Color c)
    {
        using (SolidBrush b = new SolidBrush(c))
            g.FillEllipse(b, cx - d / 2f, cy - d / 2f, d, d);
    }

    // --- numbers for the player -------------------------------------------
    // Sizes the way the concept writes them: a decimal comma, one digit after
    // it for gigabytes and megabytes, whole kilobytes.
    public static string Size(long bytes)
    {
        const double K = 1024;
        if (bytes >= K * K * K) return (bytes / (K * K * K)).ToString("0.0").Replace('.', ',') + " ГБ";
        if (bytes >= K * K) return (bytes / (K * K)).ToString("0.0").Replace('.', ',') + " МБ";
        return Math.Max(1, Math.Round(bytes / K)).ToString("0") + " КБ";
    }

    // Russian plural: one/few/many.
    public static string Plural(long n, string one, string few, string many)
    {
        long m10 = n % 10, m100 = n % 100;
        if (m10 == 1 && m100 != 11) return one;
        if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
        return many;
    }
}
