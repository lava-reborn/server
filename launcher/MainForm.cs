// The window the player sees.
//
// Laid out in logical pixels on the concept's 1120x606 design and scaled by
// Theme.S, so every number below is the number from the layout, not a device
// pixel. The form owns no logic beyond its own appearance: it hosts the
// three panels and the title bar, raises events for what is clicked, and is
// told what to say back. Everything it reports -- server up, wrong password,
// what the resources are doing -- is set from Launcher.
using System;
using System.Drawing;
using System.Windows.Forms;

class MainForm : Form
{
    // --- layout -----------------------------------------------------------
    public const int W = 1120, H = 606;
    const int EDGE = 1;            // the hairline around the window
    const int BAR = 54;            // title bar, its bottom line included
    const int MAIN = 448;          // artwork and column
    const int AUTH = 340;          // the column
    const int PANEL = 102;         // the resource panel, its top line included
    const int HERO = W - 2 * EDGE - AUTH;

    public readonly HeroPanel Hero;
    public readonly AuthPanel Auth = new AuthPanel();
    public readonly ResourcePanel Panel = new ResourcePanel();

    readonly IconButton settings = new IconButton();
    readonly IconButton forum = new IconButton();
    readonly IconButton min = new IconButton();
    readonly IconButton close = new IconButton();
    readonly Image logo;

    public event Action Settings, Forum;

    public MainForm(Image heroImage, Image logoImage)
    {
        logo = logoImage;
        Hero = new HeroPanel(heroImage, logoImage);

        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(Theme.S(W), Theme.S(H));
        BackColor = Theme.Bg;
        Text = "Lava Reborn";
        KeyPreview = true;
        Icon = Brand.AppIcon();

        Hero.Bounds = Theme.R(EDGE, EDGE + BAR, HERO, MAIN);
        Controls.Add(Hero);
        Auth.Bounds = Theme.R(EDGE + HERO, EDGE + BAR, AUTH, MAIN);
        Controls.Add(Auth);
        Panel.Bounds = Theme.R(EDGE, EDGE + BAR + MAIN, W - 2 * EDGE, PANEL);
        Controls.Add(Panel);

        // Title bar buttons, right to left: close, minimise, a separator,
        // the forum, the settings.
        int by = EDGE + (BAR - 34) / 2;
        close.Icon = "window-close";
        close.IsClose = true;
        close.BackColor = Theme.Bg;
        close.Bounds = Theme.R(W - EDGE - 10 - 34, by, 34, 34);
        close.Click += delegate { Quit(); };
        Controls.Add(close);

        min.Icon = "minimize";
        min.BackColor = Theme.Bg;
        min.Bounds = Theme.R(W - EDGE - 10 - 34 - 4 - 34, by, 34, 34);
        min.Click += delegate { WindowState = FormWindowState.Minimized; };
        Controls.Add(min);

        int ux = W - EDGE - 10 - 34 - 4 - 34 - 14 - 14 - 34;
        forum.Icon = "help";
        forum.Boxed = true;
        forum.BackColor = Theme.Bg;
        forum.Bounds = Theme.R(ux, by, 34, 34);
        forum.Click += delegate { if (Forum != null) Forum(); };
        Controls.Add(forum);

        settings.Icon = "settings";
        settings.Boxed = true;
        settings.BackColor = Theme.Bg;
        settings.Bounds = Theme.R(ux - 6 - 34, by, 34, 34);
        settings.Click += delegate { if (Settings != null) Settings(); };
        Controls.Add(settings);

        Shown += delegate { if (!Auth.SignedIn) Auth.Login.Box.Focus(); };
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

    // The game has closed: this window is the launcher again.
    public void Back()
    {
        GameStarted = false;
        TopMost = false;
        Show();
        Activate();
    }

    // Opened from the tray: in front, restored, an ordinary window again.
    public void Reveal()
    {
        TopMost = false;
        Show();
        if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
        Activate();
    }

    void Quit()
    {
        if (GameStarted) { Hide(); return; }
        Environment.Exit(0);
    }

    // --- chrome -----------------------------------------------------------
    protected override void OnMouseDown(MouseEventArgs e)
    {
        // Dragging by the title bar, which a borderless window does not get.
        if (e.Button == MouseButtons.Left && e.Y < Theme.S(EDGE + BAR))
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
        g.ScaleTransform(Theme.Scale, Theme.Scale);

        // Title bar: the logo on the left, a line underneath, the separator
        // between the two groups of buttons.
        if (logo != null)
            g.DrawImage(logo, EDGE + 25, EDGE + (BAR - 34) / 2f, 94, 34);
        Theme.HLine(g, EDGE, EDGE + BAR - 1, W - 2 * EDGE, Theme.Hairline);
        int sep = W - EDGE - 10 - 34 - 4 - 34 - 14;
        Theme.VLine(g, sep, EDGE + (BAR - 34) / 2f, 34, Theme.LineTitle);

        // One hairline around the whole window.
        using (Pen p = new Pen(Theme.WindowEdge, 1))
            g.DrawRectangle(p, 0, 0, W - 1, H - 1);
    }
}

// The window's icon is the same file Explorer shows on the exe, so the two
// cannot drift apart.
static class Brand
{
    public static Icon AppIcon()
    {
        try
        {
            using (System.IO.Stream s = System.Reflection.Assembly
                       .GetExecutingAssembly().GetManifestResourceStream("icon.ico"))
                if (s != null) return new Icon(s);
        }
        catch { }
        return null;
    }
}
