// The three regions of the window: the artwork, the account column and the
// resource panel. Each is a Control that paints its static parts and hosts
// the few real controls (fields, buttons, links) it needs; none of them
// decides anything -- Launcher tells them what to show and listens for what
// the player clicks.
//
// Measurements are the concept's, in logical pixels: the artwork is
// 778 x 448, the column 340 x 448 with a 28 px side padding, the panel
// 1118 x 102 with its icon, bar and button on one axis.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Windows.Forms;

// --- the photograph ---------------------------------------------------------

class HeroPanel : Control
{
    readonly Image image, logo;

    public HeroPanel(Image photo, Image mark)
    {
        image = photo;
        logo = mark;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgHero;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        float W = z.Width, H = z.Height;

        // object-fit: cover, centred.
        if (image != null)
        {
            float s = Math.Max(W / image.Width, H / image.Height);
            float w = image.Width * s, h = image.Height * s;
            g.DrawImage(image, (W - w) / 2f, (H - h) / 2f, w, h);
        }

        // Two gradients settle the picture: one up from the bottom edge, one
        // in from the left, both the colour of the window.
        Color dark = Theme.C(0x111317);
        using (LinearGradientBrush b = new LinearGradientBrush(
                   new RectangleF(0, -1, W, H + 2), Color.Transparent, Color.Transparent, 90f))
        {
            ColorBlend cb = new ColorBlend();
            cb.Positions = new[] { 0f, 0.43f, 0.75f, 1f };
            cb.Colors = new[] { Color.FromArgb(0, dark), Color.FromArgb(0, dark),
                                Color.FromArgb(0x30, dark), Color.FromArgb(0xeb, dark) };
            b.InterpolationColors = cb;
            g.FillRectangle(b, 0, 0, W, H);
        }
        using (LinearGradientBrush b = new LinearGradientBrush(
                   new RectangleF(-1, 0, W + 2, H), Color.Transparent, Color.Transparent, 0f))
        {
            ColorBlend cb = new ColorBlend();
            cb.Positions = new[] { 0f, 0.40f, 0.68f, 1f };
            cb.Colors = new[] { Color.FromArgb(0x9c, dark), Color.FromArgb(0x45, dark),
                                Color.FromArgb(0, dark), Color.FromArgb(0, dark) };
            b.InterpolationColors = cb;
            g.FillRectangle(b, 0, 0, W, H);
        }

        // Everything written on the picture is set without colour fringes.
        Theme.OverImage = true;

        // The line at the top: a small rotated square and tracked capitals.
        // The square is 8 x 8 to its outer edge (border-box), so the
        // one-pixel pen runs half a pixel inside it.
        using (Pen p = new Pen(Theme.AccentDiamond, 1))
        {
            GraphicsState st = g.Save();
            g.TranslateTransform(36, 28);
            g.RotateTransform(45);
            g.DrawRectangle(p, -3.5f, -3.5f, 7, 7);
            g.Restore(st);
        }
        Theme.TrackedLine(g, "СЕВЕРНАЯ АФРИКА / НОВЫЙ ПУТЬ", Theme.Display(9), Theme.C(0xe4e3e4), 49, 22, 12, 2);

        // The logo, 338 x 121 (the file's own proportions), with the 12 px of
        // transparent margin the file carries hanging left of the text column.
        if (logo != null)
        {
            // A soft shadow under the mark, as the concept's drop-shadow.
            using (ImageAttributes ia = Shadow())
                g.DrawImage(logo, new Rectangle(20, 68, 338, 121), 0, 0, logo.Width, logo.Height,
                            GraphicsUnit.Pixel, ia);
            g.DrawImage(logo, 20, 65, 338, 121);
        }
        Theme.TrackedLine(g, "ПОШАГОВАЯ MMORPG", Theme.Display(9), Theme.C(0xd5d4d9), 32, 212, 11, 2);

        // The caption, pinned to the bottom.
        Theme.TrackedLine(g, "ЗДЕСЬ НАЧИНАЕТСЯ НОВАЯ ЖИЗНЬ", Theme.DisplaySemi(12), Theme.C(0xf0eeec), 32, H - 27 - 16 - 6 - 16, 16, 2);
        Theme.Line(g, "Найди своё место в мире LAVA", Theme.Body(12), Theme.C(0xbdbcc5), 32, H - 27 - 16, 16);
        Theme.OverImage = false;
    }

    static ImageAttributes Shadow()
    {
        // Everything opaque becomes a translucent black.
        ImageAttributes ia = new ImageAttributes();
        ColorMatrix m = new ColorMatrix(new float[][] {
            new float[] { 0, 0, 0, 0, 0 },
            new float[] { 0, 0, 0, 0, 0 },
            new float[] { 0, 0, 0, 0, 0 },
            new float[] { 0, 0, 0, 0.33f, 0 },
            new float[] { 0, 0, 0, 0, 1 } });
        ia.SetColorMatrix(m);
        return ia;
    }
}

// --- the account column -----------------------------------------------------

class AuthPanel : Control
{
    const int PAD = 28, W = 340, H = 448, FIELD = W - PAD * 2;

    // The login form.
    public readonly Field Login = new Field(false);
    public readonly Field Pass = new Field(true);
    readonly CheckLine remember = new CheckLine();
    readonly TextLink lost = new TextLink();
    readonly PrimaryButton enter = new PrimaryButton();
    readonly TextLink register = new TextLink();

    // The account view.
    readonly TextLink logout = new TextLink();
    readonly TextLink about = new TextLink();
    readonly TextLink wiki = new TextLink();
    readonly TextLink cabinet = new TextLink();

    public event Action<string, string, bool> Submit;
    public event Action LostPassword, Register, Logout, About, Wiki, Cabinet;

    bool signedIn;
    string name = "", level = "", place = "";
    string hint = "";

    // The place, when it is longer than the card: cut with an ellipsis at
    // rest, and under the pointer scrolled slowly to its end and back, again
    // and again, so the whole name can be read. Where it is drawn and how
    // wide it is are learned in OnPaint.
    readonly Timer marquee = new Timer();
    RectangleF placeBox;
    float placeWidth, scroll;
    bool overPlace;
    int dir = 1, holdUntil, lastTick;
    const float SCROLL = 24, RETURN = 120;     // logical px a second
    const int HOLD_START = 500, HOLD_END = 1200, HOLD_BACK = 900;
    bool hintBad;
    bool? serverUp;
    string serverText = "Проверяем сервер";

    public AuthPanel()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgAuth;
        pulse.Interval = 40;
        pulse.Tick += delegate { PaintDot(); };
        marquee.Interval = 16;
        marquee.Tick += delegate { Scroll(); };

        Login.Placeholder = "Введи логин";
        Pass.Placeholder = "Введи пароль";
        Login.Bounds = Theme.R(PAD, 102, FIELD, 44);
        Pass.Bounds = Theme.R(PAD, 184, FIELD, 44);
        Controls.Add(Login);
        Controls.Add(Pass);

        remember.Label = "Запомнить меня";
        remember.Checked = true;
        remember.BackColor = BackColor;
        remember.Bounds = Theme.R(PAD, 244, 140, 16);
        Controls.Add(remember);

        lost.Label = "Забыли пароль?";
        lost.AlignRight = true;
        lost.BackColor = BackColor;
        lost.Bounds = Theme.R(W - PAD - 110, 244, 110, 16);
        lost.Click += delegate { if (LostPassword != null) LostPassword(); };
        Controls.Add(lost);

        enter.Label = "ВОЙТИ";
        enter.Bounds = Theme.R(PAD, 282, FIELD, 44);
        enter.Click += delegate { Go(); };
        Controls.Add(enter);

        register.Label = "Создать аккаунт";
        register.Icon = "arrow";
        register.Ink = Theme.InkRegister;
        register.IconInk = Theme.Accent;
        register.AlignRight = true;
        register.BackColor = BackColor;
        register.Bounds = Theme.R(W - PAD - 160, 392 + 20, 160, 16);
        register.Click += delegate { if (Register != null) Register(); };
        Controls.Add(register);

        logout.Label = "Выйти";
        logout.Ink = Theme.InkLinkStatus;
        logout.AlignRight = true;
        logout.BackColor = BackColor;
        logout.Bounds = Theme.R(W - PAD - 80, 164 + 12, 80, 16);
        logout.Click += delegate { if (Logout != null) Logout(); };
        Controls.Add(logout);

        Foot(about, "Об игре", delegate { if (About != null) About(); });
        Foot(wiki, "Энциклопедия", delegate { if (Wiki != null) Wiki(); });
        Foot(cabinet, "Личный кабинет", delegate { if (Cabinet != null) Cabinet(); });

        Login.Box.KeyDown += Key;
        Pass.Box.KeyDown += Key;
        Login.Box.TextChanged += delegate { ClearBadHint(); };
        Pass.Box.TextChanged += delegate { ClearBadHint(); };

        ShowLogin();
    }

    void Foot(TextLink l, string label, EventHandler click)
    {
        l.Label = label;
        l.Icon = "external";
        l.IconSize = 12;
        l.Gap = 6;
        l.Ink = Theme.InkLinkFoot;
        l.IconInk = Theme.InkMetaIcon;
        l.BackColor = BackColor;
        l.Click += click;
        Controls.Add(l);
    }

    // The footer links are spread edge to edge (space-between), so their x
    // depends on how wide each label measures in this machine's font.
    bool footPlaced;

    void PlaceFooter(Graphics g)
    {
        if (footPlaced) return;
        footPlaced = true;
        float wa = about.Measure(g), ww = wiki.Measure(g), wc = cabinet.Measure(g);
        float gap = (FIELD - wa - ww - wc) / 2f;
        int y = 392 + 20;
        about.Bounds = new Rectangle(Theme.S(PAD), Theme.S(y), Theme.S(wa + 1), Theme.S(16));
        wiki.Bounds = new Rectangle(Theme.S(PAD + wa + gap), Theme.S(y), Theme.S(ww + 1), Theme.S(16));
        cabinet.Bounds = new Rectangle(Theme.S(W - PAD - wc), Theme.S(y), Theme.S(wc + 1), Theme.S(16));
    }

    void Key(object sender, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; Go(); }
    }

    void Go()
    {
        if (!enter.Enabled || signedIn) return;
        string l = Login.Value.Trim();
        string p = Pass.Value;
        if (l.Length == 0) { Hint("Введи логин", true); Login.Box.Focus(); return; }
        if (p.Length == 0 && !Pass.Hint) { Hint("Введи пароль", true); Pass.Box.Focus(); return; }
        if (Submit != null) Submit(l, p, remember.Checked);
    }

    void ClearBadHint()
    {
        if (hintBad) Hint("", false);
    }

    // --- what Launcher tells it -------------------------------------------

    public bool SignedIn { get { return signedIn; } }

    public void ShowLogin()
    {
        signedIn = false;
        foreach (Control c in new Control[] { Login, Pass, remember, lost, enter, register }) c.Visible = true;
        foreach (Control c in new Control[] { logout, about, wiki, cabinet }) c.Visible = false;
        Invalidate();
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        bool over = signedIn && placeWidth > placeBox.Width &&
                    placeBox.Contains(e.X / Theme.Scale, e.Y / Theme.Scale);
        if (over == overPlace) return;
        overPlace = over;
        lastTick = Environment.TickCount;
        if (over)
        {
            dir = 1;
            holdUntil = lastTick + HOLD_START;
            PaintPlace();
        }
        marquee.Start();
    }

    protected override void OnMouseLeave(EventArgs e)
    {
        base.OnMouseLeave(e);
        if (!overPlace) return;
        overPlace = false;
        lastTick = Environment.TickCount;
        marquee.Start();
    }

    // One step: on to the end, a pause, back to the start, a pause, while
    // the pointer stays; once it has gone, back to the start, quicker, and
    // the ellipsis again.
    void Scroll()
    {
        int now = Environment.TickCount;
        float dt = (now - lastTick) / 1000f;
        lastTick = now;
        float end = Math.Max(0, placeWidth - placeBox.Width);
        if (!overPlace)
        {
            scroll = Math.Max(0, scroll - RETURN * dt);
            if (scroll <= 0) marquee.Stop();
            PaintPlace();
            return;
        }
        if (now - holdUntil < 0) return;
        scroll += dir * SCROLL * dt;
        if (dir > 0 && scroll >= end) { scroll = end; dir = -1; holdUntil = now + HOLD_END; }
        else if (dir < 0 && scroll <= 0) { scroll = 0; dir = 1; holdUntil = now + HOLD_BACK; }
        PaintPlace();
    }

    void PaintPlace()
    {
        Invalidate(new Rectangle((int)(placeBox.X * Theme.Scale) - 2, (int)(placeBox.Y * Theme.Scale) - 2,
                                 (int)(placeBox.Width * Theme.Scale) + 4, (int)(placeBox.Height * Theme.Scale) + 4));
    }
    // The character card: name, and the level and place when they are known.
    // The launcher learns all three from the server at login (persInfo); an
    // empty string, from an older server, leaves the item out.
    public void ShowAccount(string who, string lvl, string where)
    {
        signedIn = true;
        name = who ?? "";
        level = lvl ?? "";
        place = where ?? "";
        scroll = 0;
        foreach (Control c in new Control[] { Login, Pass, remember, lost, enter, register }) c.Visible = false;
        foreach (Control c in new Control[] { logout, about, wiki, cabinet }) c.Visible = true;
        Hint("", false);
        Invalidate();
    }

    // A remembered account comes back as a digest, not a password, so the
    // password box shows that it is remembered instead of pretending to hold
    // something. PasswordRemembered is how Launcher knows to use the digest.
    public void Fill(string savedLogin, bool rememberMe)
    {
        Login.Value = savedLogin == null ? "" : savedLogin;
        remember.Checked = rememberMe;
        if (!string.IsNullOrEmpty(savedLogin)) Pass.ShowHint("Пароль сохранён");
    }

    public bool PasswordRemembered { get { return Pass.Hint; } }

    // Whether the line under the button is a refusal rather than a remark:
    // Launcher leaves a refusal standing until the player types again.
    public bool HintIsBad { get { return hintBad; } }

    // The line under the button: a remark, or in red the reason the form
    // did not go through.
    public void Hint(string text, bool bad)
    {
        hint = text ?? "";
        hintBad = bad && hint.Length > 0;
        Invalidate();
    }

    // Whether "ВОЙТИ" can be pressed, and whether the fields take input.
    public void Gate(bool open, bool busy)
    {
        enter.Enabled = open && !busy;
        Login.Box.ReadOnly = busy;
        Pass.Box.ReadOnly = busy;
        remember.Enabled = !busy;
        lost.Enabled = !busy;
        register.Enabled = !busy;
        enter.Label = busy ? "Входим" : "ВОЙТИ";
        enter.Spinning = busy;
        enter.Invalidate();
    }

    public void Server(bool? up, string text)
    {
        serverUp = up;
        serverText = text;
        if (up == true) pulse.Start(); else pulse.Stop();
        Invalidate();
    }

    // The server dot's breathing: only its own square is painted again.
    readonly Timer pulse = new Timer();
    float dotX;
    const int PULSE = 2400;
    // The server line sits a little lower than the title's box, nearer its
    // baseline, the dot with it.
    const int SERVER_DROP = 2, DOT_Y = 24 + 16 + SERVER_DROP;

    void PaintDot()
    {
        Invalidate(new Rectangle((int)((dotX - 11) * Theme.Scale), (int)((DOT_Y - 11) * Theme.Scale),
                                 (int)(22 * Theme.Scale) + 1, (int)(22 * Theme.Scale) + 1));
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        PlaceFooter(g);
        SizeF z = Theme.Logical(g, this);

        Theme.VLine(g, 0, 0, z.Height, Theme.LineAuth);

        // Head: the title and, on the same line, the server.
        Theme.Line(g, signedIn ? "Твой персонаж" : "Вход в игру", Theme.DisplayTitle(24), Theme.Ink, PAD, 24, 32);
        Font sf = Theme.Body(11);
        bool bad = serverUp == false;
        Color sc = bad ? Theme.InkServerBad : Theme.InkServer;
        float sw = Theme.Width(g, serverText, sf);
        float sx = W - PAD - sw;
        Theme.Line(g, serverText, sf, sc, sx, 24 + SERVER_DROP, 32);
        dotX = sx - 7 - 3;
        if (serverUp == true)
        {
            // Up: a live green that breathes, brighter and dimmer with a
            // swelling glow, once every PULSE ms; quietly, it is a status,
            // not an alarm.
            double k = 0.5 - 0.5 * Math.Cos(2 * Math.PI * (Environment.TickCount % PULSE) / PULSE);
            Theme.Dot(g, dotX, DOT_Y, (float)(10 + 3 * k), Color.FromArgb((int)(0x12 + 0x1c * k), Theme.Online));
            Theme.Dot(g, dotX, DOT_Y, 6, Color.FromArgb((int)(0xd0 + 0x2f * k), Theme.Online));
        }
        else
        {
            Color dot = serverUp == null ? Theme.InkMetaIcon : Theme.Red;
            if (bad) Theme.Dot(g, dotX, DOT_Y, 12, Color.FromArgb(0x33, dot));   // the glow
            Theme.Dot(g, dotX, DOT_Y, 6, dot);
        }

        if (!signedIn)
        {
            Font lf = Theme.Body(12);
            Theme.Line(g, "Логин", lf, Theme.InkLabel, PAD, 80, 16);
            Theme.Line(g, "Пароль", lf, Theme.InkLabel, PAD, 162, 16);

            if (hint.Length > 0)
            {
                Font hf = Theme.Body(11);
                string h = Theme.Clip(g, hint, hf, FIELD);
                float hw = Theme.Width(g, h, hf);
                Theme.Line(g, h, hf, hintBad ? Theme.Red : Theme.InkHint, PAD + (FIELD - hw) / 2f, 334, 16);
            }

            Theme.HLine(g, PAD, 392, FIELD, Theme.Hairline);
            Theme.Line(g, "Впервые здесь?", Theme.Body(11), Theme.InkFoot, PAD, 392 + 20, 16);
        }
        else
        {
            // The card.
            RectangleF card = new RectangleF(PAD, 80, FIELD, 76);
            Theme.Box(g, card, 6, Theme.A(0xffffff, 0x04), Theme.LineCard);
            RectangleF av = new RectangleF(PAD + 14, 80 + 14, 48, 48);
            Theme.Box(g, av, 4, Theme.A(0xfa7148, 0x0c), Theme.A(0xfa7148, 0x2a));
            Icons.Draw(g, "avatar", av.X + 7, av.Y + 7, 34, Theme.AccentIcon, 1.4f);

            float tx = PAD + 14 + 48 + 14;
            bool meta = level.Length > 0 || place.Length > 0;
            float top = meta ? 97 : 105;
            Font nf = Theme.DisplayTitle(22);
            Theme.Line(g, Theme.Clip(g, name, nf, 180), nf, Theme.Ink, tx, top, 26);
            if (meta)
            {
                Font mf = Theme.Body(11);
                float mx = tx;
                if (level.Length > 0)
                {
                    Icons.Draw(g, "level", mx, top + 26 + 1, 14, Theme.InkMetaIcon);
                    Theme.Line(g, level, mf, Theme.InkMeta, mx + 14 + 6, top + 26, 16);
                    mx += 14 + 6 + Theme.Width(g, level, mf) + 14;
                }
                if (place.Length > 0)
                {
                    Icons.Draw(g, "pin", mx, top + 26 + 1, 14, Theme.InkMetaIcon);
                    float px = mx + 14 + 6;
                    placeBox = new RectangleF(px, top + 26, card.Right - 14 - px, 16);
                    placeWidth = Theme.Width(g, place, mf);
                    if (placeWidth <= placeBox.Width)
                        Theme.Line(g, place, mf, Theme.InkMeta, px, top + 26, 16);
                    else if (!overPlace && scroll <= 0)
                        Theme.Line(g, Theme.Clip(g, place, mf, placeBox.Width), mf, Theme.InkMeta, px, top + 26, 16);
                    else
                    {
                        GraphicsState st = g.Save();
                        g.SetClip(placeBox);
                        Theme.Line(g, place, mf, Theme.InkMeta, px - scroll, top + 26, 16);
                        g.Restore(st);
                    }
                }
            }

            // The status row under the card.
            Theme.Line(g, "Вход в аккаунт сохранён", Theme.Body(11), Theme.InkFoot, PAD, 164 + 12, 16);
            Theme.HLine(g, PAD, 164 + 40 - 1, FIELD, Theme.Hairline);

            Theme.HLine(g, PAD, 392, FIELD, Theme.Hairline);
        }
    }
}

// --- the resource panel -----------------------------------------------------

enum Tone { Normal, Bad, Paused, Good }

// Everything the panel shows, in one object, so a state is built in one
// place (Launcher) and rendered in another (here) without the two drifting.
class PanelState
{
    public string Title = "";
    public string Line = "";         // the left part of the line under the title
    public string Right = "";        // its right part: percent, time, space
    public string Icon = "check";
    public Tone Tone = Tone.Normal;
    public bool Track;               // whether the bar is shown
    public double Progress;          // 0..1
    public string Action;            // the button's label, or null for "ИГРАТЬ"
    public string ActionIcon;
    public bool ActionPrimary;
    public bool Version;             // the version tag stands in the line
    public bool Busy;                // the track runs: under way, amount unknown
    public string PathText;          // a monospaced path in the line (missing-folder state)
    public string FolderLink;        // a link after the path, or null

    public PanelState Copy() { return (PanelState)MemberwiseClone(); }
}

class ResourcePanel : Control
{
    const int W = 1118, H = 102, PAD = 28, ICON = 44, GAP = 20, BTN = 200;
    const int BODY_X = PAD + ICON + GAP;
    const int BODY_W = W - PAD * 2 - ICON - GAP - BTN - GAP;
    const int BTN_X = W - PAD - BTN;

    readonly ActionButton action = new ActionButton();
    readonly ProgressTrack track = new ProgressTrack();
    readonly TextLink version = new TextLink();
    readonly TextLink news = new TextLink();
    readonly TextLink folder = new TextLink();
    readonly ToolTip tip = new ToolTip();

    PanelState state = new PanelState();
    bool canPlay;
    bool showNews;

    public event Action Action, Play, VersionClick, NewsClick, FolderClick;

    public ResourcePanel()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgPanel;

        action.Bounds = Theme.R(BTN_X, 28, BTN, 44);
        action.Click += delegate
        {
            if (!action.Enabled) return;
            if (state.Action == null) { if (Play != null) Play(); }
            else if (Action != null) Action();
        };
        Controls.Add(action);

        track.Bounds = Theme.R(BODY_X, 48, BODY_W, 4);
        Controls.Add(track);

        version.Face = Theme.Mono(12);
        version.Ink = Theme.InkVersion;
        version.HoverInk = Theme.Ink;
        version.BackColor = BackColor;
        version.Click += delegate { if (VersionClick != null) VersionClick(); };
        Controls.Add(version);

        news.Label = "Что нового";
        news.Ink = Theme.AccentSoft;
        news.HoverInk = Theme.AccentSoftHover;
        news.BackColor = BackColor;
        news.Click += delegate { if (NewsClick != null) NewsClick(); };
        Controls.Add(news);

        folder.Icon = null;
        folder.IconFirst = true;
        folder.Ink = Theme.AccentSoft;
        folder.HoverInk = Theme.AccentSoftHover;
        folder.BackColor = BackColor;
        folder.Click += delegate { if (FolderClick != null) FolderClick(); };
        Controls.Add(folder);
    }

    public string VersionLabel = "";
    public string VersionTip = "";

    public void Show(PanelState s)
    {
        state = s ?? new PanelState();
        Apply();
    }

    // "ИГРАТЬ" was pressed and the game is on its way: the button says so,
    // with the spinner, until the launcher steps aside.
    bool starting;
    public bool Starting
    {
        get { return starting; }
        set { if (value == starting) return; starting = value; Apply(); }
    }

    // The launcher opened from the tray while the game runs.
    bool inGame;
    public bool InGame
    {
        get { return inGame; }
        set { if (value == inGame) return; inGame = value; Apply(); }
    }

    public bool CanPlay
    {
        get { return canPlay; }
        set { canPlay = value; Apply(); }
    }

    public bool News
    {
        get { return showNews; }
        set { showNews = value; Apply(); }
    }

    void Apply()
    {
        PanelState s = state;
        if (s.Action == null)
        {
            action.Label = inGame ? "ИГРА ЗАПУЩЕНА" : (starting ? "ЗАПУСКАЕМ" : "ИГРАТЬ");
            action.Icon = null;
            action.Play = true;
            action.Primary = canPlay;
            action.Enabled = canPlay;
            action.Spinning = starting;
        }
        else
        {
            action.Label = s.Action;
            action.Icon = s.ActionIcon;
            action.Play = false;
            action.Primary = s.ActionPrimary;
            action.Enabled = true;
            action.Spinning = false;
        }
        action.Invalidate();

        track.Visible = s.Track;
        track.Value = s.Progress;
        track.Running = s.Busy;
        track.Fill = s.Tone == Tone.Bad ? Theme.Red : (s.Tone == Tone.Paused ? Theme.PausedFill : Theme.Accent);
        track.Invalidate();

        version.Visible = s.Version;
        version.Label = VersionLabel;
        tip.SetToolTip(version, VersionTip);
        news.Visible = s.Version && showNews;
        folder.Visible = s.FolderLink != null;
        folder.Label = s.FolderLink ?? "";
        folder.Icon = s.FolderLink != null ? "folder" : null;
        folder.IconSize = 14;
        folder.Gap = 6;
        placed = false;
        Invalidate();
    }

    bool placed;

    // The line under the title runs left to right: version tag, "Что
    // нового", the path and its link, the text; each sits after the one
    // before it, so their x comes from measuring.
    void Place(Graphics g)
    {
        if (placed) return;
        placed = true;
        int y = state.Track ? 60 : 55;
        float x = BODY_X;
        if (version.Visible)
        {
            float vw = version.Measure(g);
            version.Bounds = new Rectangle(Theme.S(x), Theme.S(y), Theme.S(vw + 1), Theme.S(16));
            x += vw + 14;
            if (news.Visible)
            {
                // The pill: a 6 px dot, a gap, the words. The dot is painted
                // in OnPaint; the link starts after it.
                float nw = news.Measure(g);
                news.Bounds = new Rectangle(Theme.S(x + 6 + 6), Theme.S(y), Theme.S(nw + 1), Theme.S(16));
                x += 6 + 6 + nw + 20;
            }
            else x += 20 - 14;
        }
        if (state.PathText != null)
        {
            x += Theme.Width(g, state.PathText, Theme.Mono(11)) + 14;
            if (folder.Visible)
            {
                float fw = folder.Measure(g);
                folder.Bounds = new Rectangle(Theme.S(x), Theme.S(y), Theme.S(fw + 1), Theme.S(16));
            }
        }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        Place(g);
        PanelState s = state;

        Theme.HLine(g, 0, 0, W, Theme.LinePanel);

        // The icon in its box.
        Color ic, il, ib;
        switch (s.Tone)
        {
            case Tone.Bad: ic = Theme.Red; il = Theme.A(0xff8a85, 0x30); ib = Theme.A(0xff8a85, 0x0d); break;
            case Tone.Paused: ic = Theme.Paused; il = Theme.A(0xffffff, 0x18); ib = Theme.A(0xffffff, 0x05); break;
            case Tone.Good: ic = Theme.Online; il = Theme.A(0x3ee07f, 0x40); ib = Theme.A(0x3ee07f, 0x14); break;
            default: ic = Theme.Accent; il = Theme.A(0xfa7148, 0x29); ib = Theme.A(0xfa7148, 0x0d); break;
        }
        RectangleF box = new RectangleF(PAD, 28, ICON, ICON);
        Theme.Box(g, box, 8, ib, il);
        Icons.Draw(g, s.Icon, box.X + 12, box.Y + 12, 20, ic);

        // Title, then the line under it: with a bar at 18 and 60, without one
        // at 29 and 55, so the pair stays centred on the button's axis.
        int ty = s.Track ? 18 : 29;
        int ly = s.Track ? 60 : 55;
        Font tf = Theme.BodySemi(13);
        Theme.Line(g, Theme.Clip(g, s.Title, tf, BODY_W), tf, s.Tone == Tone.Bad ? Theme.RedTitle : Theme.Ink, BODY_X, ty, 22);

        Font lf = Theme.Body(11);
        float x = BODY_X;
        if (version.Visible)
        {
            x += version.Measure(g) + 14;
            if (news.Visible)
            {
                Theme.Dot(g, x + 3, ly + 8, 6, Theme.Accent);
                x += 6 + 6 + news.Measure(g) + 20;
            }
            else x += 20 - 14;
        }
        if (s.PathText != null)
        {
            Theme.Line(g, s.PathText, Theme.Mono(11), Theme.InkPath, x, ly, 16);
            x += Theme.Width(g, s.PathText, Theme.Mono(11)) + 14;
            if (folder.Visible) x += folder.Measure(g) + 20;
        }
        float rightW = s.Right.Length > 0 ? Theme.Width(g, s.Right, lf) : 0;
        float room = BODY_X + BODY_W - x - (rightW > 0 ? rightW + 20 : 0);
        if (s.Line.Length > 0 && room > 20)
            Theme.Line(g, Theme.Clip(g, s.Line, lf, room), lf, Theme.InkStats, x, ly, 16);
        if (rightW > 0)
            Theme.LineRight(g, s.Right, lf, Theme.InkEta, BODY_X + BODY_W, ly, 16);
    }
}
