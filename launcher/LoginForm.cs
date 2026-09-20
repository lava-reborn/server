// The window the player sees.
//
// Laid out in logical pixels on a 920x576 design and scaled by Theme.S, so
// every number below is the number from the layout, not a device pixel.
// The form owns no logic beyond its own appearance: it raises Submit and is
// told what to say back. Everything it reports -- server up, wrong password,
// loading the world -- is set from Launcher.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Windows.Forms;

class LoginForm : Form
{
    // --- layout -----------------------------------------------------------
    const int W = 920, H = 576;
    const int BAR = 40;           // title bar
    const int PANEL = 340;        // left column
    const int PAD = 32;           // its side margin
    const int FIELD = PANEL - PAD * 2;

    // --- parts ------------------------------------------------------------
    readonly Field login = new Field(false);
    readonly Field pass = new Field(true);
    readonly CheckLine remember = new CheckLine();
    readonly LinkText lostPass = new LinkText();
    readonly LinkText register = new LinkText();
    readonly PrimaryButton enter = new PrimaryButton();
    readonly WinButton min = new WinButton();
    readonly WinButton close = new WinButton();
    readonly HeroPanel hero;

    string message = "";
    Color messageColor = Theme.Danger;
    string statusText = "Проверяем сервер";
    Color statusDot = Theme.InkFaint;
    readonly string version;

    public event Action<string, string, bool> Submit;
    public event Action Register;
    public event Action LostPassword;

    public LoginForm(Image heroImage, string versionLabel)
    {
        version = versionLabel;
        hero = new HeroPanel(heroImage);

        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(Theme.S(W), Theme.S(H));
        BackColor = Theme.BgBase;
        Text = "Lava Reborn";
        KeyPreview = true;
        Icon = Brand.AppIcon();

        hero.Bounds = Theme.R(PANEL, BAR, W - PANEL, H - BAR);
        Controls.Add(hero);

        login.Bounds = Theme.R(PAD, 158, FIELD, 38);
        pass.Bounds = Theme.R(PAD, 224, FIELD, 38);
        Controls.Add(login);
        Controls.Add(pass);

        remember.Label = "Запомнить меня";
        remember.Bounds = Theme.R(PAD, 274, 150, 20);
        Controls.Add(remember);

        lostPass.Label = "Забыли пароль?";
        lostPass.Align = ContentAlignment.MiddleRight;
        lostPass.Bounds = Theme.R(PANEL - PAD - 130, 274, 130, 20);
        lostPass.Click += delegate { if (LostPassword != null) LostPassword(); };
        Controls.Add(lostPass);

        enter.Label = "Войти";
        enter.Bounds = Theme.R(PAD, 310, FIELD, 42);
        enter.Click += delegate { Go(); };
        Controls.Add(enter);

        register.Label = "Создать";
        register.Bold = true;
        register.Click += delegate { if (Register != null) Register(); };
        Controls.Add(register);   // placed in OnPaint's measure pass below

        min.Bounds = Theme.R(W - 92, 0, 46, BAR);
        min.Click += delegate { WindowState = FormWindowState.Minimized; };
        Controls.Add(min);

        close.IsClose = true;
        close.Bounds = Theme.R(W - 46, 0, 46, BAR);
        close.Click += delegate { Quit(); };
        Controls.Add(close);

        login.Box.KeyDown += Key;
        pass.Box.KeyDown += Key;
        login.Box.TextChanged += delegate { Clear(); };
        pass.Box.TextChanged += delegate { Clear(); };

        Shown += delegate { login.Box.Focus(); };
    }

    // "Создать" sits right after a run of muted text, so its x depends on how
    // wide that text measures in whatever font this machine ended up with.
    bool placed;

    void PlaceRegister(Graphics g)
    {
        if (placed) return;
        placed = true;
        // Measured in logical units -- MeasureString is not affected by the
        // paint transform -- and turned into device pixels for the bounds.
        // The trailing space is measured away by GenericTypographic, so the
        // gap between the sentence and the link is added here.
        Font f = Theme.Body(13, false);
        float w = Theme.Width(g, "Ещё нет учётной записи?", f) + 6;
        register.Bounds = new Rectangle(Theme.S(PAD + w), Theme.S(390),
                                        Theme.S(90), Theme.S(20));
    }

    void Key(object sender, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; Go(); }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape) Quit();
        base.OnKeyDown(e);
    }

    // Once the game is up this window is only a curtain in front of it, and
    // the process behind it is serving the game its own res/ folder. Closing
    // it then means stepping aside, not quitting.
    public bool GameStarted;

    public void Front()
    {
        GameStarted = true;
        TopMost = true;
        BringToFront();
    }

    void Quit()
    {
        if (GameStarted) { Hide(); return; }
        Environment.Exit(0);
    }

    void Clear()
    {
        if (message.Length == 0) return;
        message = "";
        Invalidate();
    }

    void Go()
    {
        if (!enter.Enabled) return;
        string l = login.Value.Trim();
        string p = pass.Value;
        if (l.Length == 0) { Error("Введите логин"); login.Box.Focus(); return; }
        if (p.Length == 0 && !pass.Hint) { Error("Введите пароль"); pass.Box.Focus(); return; }
        if (Submit != null) Submit(l, p, remember.Checked);
    }

    // --- what Launcher tells it -------------------------------------------
    // A remembered account comes back as a digest, not a password, so the
    // password box shows that it is remembered instead of pretending to hold
    // something. PasswordRemembered is how Launcher knows to use the digest.
    public void Fill(string savedLogin, bool rememberMe)
    {
        login.Value = savedLogin == null ? "" : savedLogin;
        remember.Checked = rememberMe;
        if (savedLogin != null && savedLogin.Length > 0) pass.ShowHint("Пароль сохранён");
    }

    public bool PasswordRemembered { get { return pass.Hint; } }

    public void Error(string text)
    {
        message = text;
        messageColor = Theme.Danger;
        Busy(false, "Войти");
        Invalidate();
    }

    public void Note(string text)
    {
        message = text;
        messageColor = Theme.InkMuted;
        Invalidate();
    }

    public void Busy(bool on, string label)
    {
        enter.Label = label;
        enter.Enabled = !on;
        login.Box.ReadOnly = on;
        pass.Box.ReadOnly = on;
        register.Enabled = !on;
        lostPass.Enabled = !on;
        remember.Enabled = !on;
        enter.Invalidate();
    }

    public void Status(bool? up, string text)
    {
        statusText = text;
        statusDot = up == null ? Theme.InkFaint : (up.Value ? Theme.Success : Theme.Danger);
        Invalidate();
    }

    // --- chrome -----------------------------------------------------------
    protected override void OnMouseDown(MouseEventArgs e)
    {
        // Dragging by the title bar, which a borderless window does not get.
        if (e.Button == MouseButtons.Left && e.Y < Theme.S(BAR))
        {
            Native.ReleaseCapture();
            Native.SendMessage(Handle, 0xA1 /* WM_NCLBUTTONDOWN */, 2 /* HTCAPTION */, 0);
        }
        base.OnMouseDown(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        PlaceRegister(g);
        g.ScaleTransform(Theme.Scale, Theme.Scale);

        // title bar
        using (SolidBrush b = new SolidBrush(Theme.BgPanel))
            g.FillRectangle(b, 0, 0, W, BAR);
        using (SolidBrush b = new SolidBrush(Theme.Line))
            g.FillRectangle(b, 0, BAR - 1, W, 1);

        Brand.Draw(g, 16, (BAR - 20) / 2f, 20);

        Font mark = Theme.Display(14, true);
        float x = 16 + 20 + 10;
        float my = (BAR - mark.GetHeight(g)) / 2f;
        // The gap is drawn, not typed: GenericTypographic trims a leading
        // space and the two words would run together.
        x = Theme.Tracked(g, "LAVA", mark, Theme.Ink, x, my, 1.1f);
        Theme.Tracked(g, "REBORN", Theme.Display(14, false), Theme.InkMuted, x + 5, my, 1.1f);

        // left column
        using (SolidBrush b = new SolidBrush(Theme.BgBase))
            g.FillRectangle(b, 0, BAR, PANEL, H - BAR);

        Theme.Tracked(g, "УБЕЖИЩЕ ЖДЁТ", Theme.Display(11, false), Theme.Brand,
                      PAD, 76, 1.8f);
        Theme.Text(g, "Вход в игру", Theme.Body(24, true), Theme.Ink, PAD, 92);

        Font label = Theme.Body(12.5, false);
        Theme.Text(g, "Логин", label, Theme.InkFaint, PAD, 138);
        Theme.Text(g, "Пароль", label, Theme.InkFaint, PAD, 204);

        if (message.Length > 0)
            Theme.Text(g, message, Theme.Body(13, false), messageColor, PAD, 362);

        Theme.Text(g, "Ещё нет учётной записи?", Theme.Body(13, false),
                   Theme.InkMuted, PAD, 390);

        // footer: server state on the left, build on the right. The build has
        // the right of way -- it is what a bug report needs -- so the status
        // gives up characters rather than run into it.
        float dot = 8;
        float fy = 536;
        using (SolidBrush b = new SolidBrush(statusDot))
            g.FillEllipse(b, PAD, fy + 5, dot, dot);

        Font vf = Theme.Mono(11.5);
        float vw = Theme.Width(g, version, vf);
        Theme.Text(g, version, vf, Theme.InkFaint, PANEL - PAD - vw, fy + 1);

        Font sf = Theme.Body(12.5, false);
        float sx = PAD + dot + 9;
        float room = PANEL - PAD - vw - 10 - sx;
        string s = statusText;
        while (s.Length > 1 && Theme.Width(g, s, sf) > room)
            s = s.Substring(0, s.Length - 2) + "…";
        Theme.Text(g, s, sf, Theme.InkMuted, sx, fy);

        // one hairline around the whole window
        using (Pen p = new Pen(Theme.Line, 1))
            g.DrawRectangle(p, 0, 0, W - 1, H - 1);
    }
}

// The brand mark from the site's logo, three polygons on a 48-unit grid.
static class Brand
{
    static readonly float[][] Diamond = { new float[] { 24, 3 }, new float[] { 26.5f, 8 },
                                          new float[] { 24, 13 }, new float[] { 21.5f, 8 } };
    static readonly float[][] Upper = { new float[] { 24, 15 }, new float[] { 38, 30 },
                                        new float[] { 30.5f, 30 }, new float[] { 24, 23 },
                                        new float[] { 17.5f, 30 }, new float[] { 10, 30 } };
    static readonly float[][] Lower = { new float[] { 24, 29 }, new float[] { 38, 44 },
                                        new float[] { 30.5f, 44 }, new float[] { 24, 37 },
                                        new float[] { 17.5f, 44 }, new float[] { 10, 44 } };

    static PointF[] Scale(float[][] pts, float x, float y, float size)
    {
        // The artwork spans y 3..44 of a 48 box; size is the height it should
        // occupy, so everything is mapped through that span.
        float k = size / 41f;
        PointF[] p = new PointF[pts.Length];
        for (int i = 0; i < pts.Length; i++)
            p[i] = new PointF(x + (pts[i][0] - 10) * k, y + (pts[i][1] - 3) * k);
        return p;
    }

    public static void Draw(Graphics g, float x, float y, float size)
    {
        SmoothingMode old = g.SmoothingMode;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        using (SolidBrush brand = new SolidBrush(Theme.Brand))
        using (SolidBrush muted = new SolidBrush(Theme.InkMuted))
        {
            g.FillPolygon(brand, Scale(Diamond, x, y, size));
            g.FillPolygon(brand, Scale(Upper, x, y, size));
            g.FillPolygon(muted, Scale(Lower, x, y, size));
        }
        g.SmoothingMode = old;
    }

    // The window's icon is the same file Explorer shows on the exe, so the
    // two cannot drift apart. Drawing one is kept as the fallback for a build
    // that somehow went out without it.
    public static Icon AppIcon()
    {
        try
        {
            using (System.IO.Stream s = System.Reflection.Assembly
                       .GetExecutingAssembly().GetManifestResourceStream("icon.ico"))
                if (s != null) return new Icon(s);
        }
        catch { }
        return MakeIcon();
    }

    public static Icon MakeIcon()
    {
        try
        {
            using (Bitmap bmp = new Bitmap(64, 64))
            {
                using (Graphics g = Graphics.FromImage(bmp))
                {
                    g.Clear(Color.Transparent);
                    using (SolidBrush b = new SolidBrush(Theme.BgBase))
                    using (System.Drawing.Drawing2D.GraphicsPath p =
                               Theme.Round(new RectangleF(0, 0, 64, 64), 6))
                        g.FillPath(b, p);
                    Draw(g, 14, 10, 44);
                }
                IntPtr h = bmp.GetHicon();
                return (Icon)Icon.FromHandle(h).Clone();
            }
        }
        catch { return null; }
    }
}
