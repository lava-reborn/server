// The small windows that open over the main one: a note with a heading and
// a paragraph or two ("Забыли пароль?"), and the settings.
//
// Each is a borderless form shown modally over a dimming sheet laid across
// the main window, the way the concept's dialogs sit on a darkened backdrop.
// The sheet is a second form rather than a repaint of the main one, so the
// controls underneath are covered and cannot take a click.
using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

class Modal : Form
{
    protected readonly IconButton close = new IconButton();

    protected Modal(int width)
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = false;
        BackColor = Theme.BgDialog;
        KeyPreview = true;
        Width = Theme.S(width);
        // Invisible until it has painted once: Windows shows a new window
        // with its class background, white, before the first WM_PAINT, and
        // that frame is the white blink the owner saw on opening a dialog.
        Opacity = 0;

        close.Icon = "close";
        close.IconSize = 17;
        close.Stroke = 1.5f;
        close.BackColor = Theme.BgDialog;
        close.Click += delegate { Close(); };
        Controls.Add(close);
    }

    protected int LogicalWidth { get { return (int)Math.Round(Width / Theme.Scale); } }
    protected int LogicalHeight { get { return (int)Math.Round(Height / Theme.Scale); } }

    protected void PlaceClose(int top, int right, int size)
    {
        close.Bounds = Theme.R(LogicalWidth - right - size, top, size, size);
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape) Close();
        base.OnKeyDown(e);
    }

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        // Shown arrives as a posted message, ahead of the first WM_PAINT:
        // revealed here as it is, the window would show its unpainted,
        // white surface for a frame. Painted first, then revealed.
        PaintNow(this);
        Opacity = 1;
    }

    // Every window of the tree painted now, not when the queue gets to it.
    public static void PaintNow(Control c)
    {
        c.Update();
        foreach (Control child in c.Controls) PaintNow(child);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        g.ScaleTransform(Theme.Scale, Theme.Scale);
        Draw(g, LogicalWidth, LogicalHeight);
        using (Pen p = new Pen(Theme.LineDialog, 1))
            g.DrawRectangle(p, 0, 0, LogicalWidth - 1, LogicalHeight - 1);
    }

    protected virtual void Draw(Graphics g, int w, int h) { }

    // Centred over the owner, behind a sheet that dims it.
    public void Open(Form owner)
    {
        using (Sheet sheet = new Sheet())
        {
            sheet.Bounds = owner.Bounds;
            sheet.Show(owner);
            // Dimmed only once it is on screen and painted: a layered window
            // shown at its final opacity paints one opaque frame first, and
            // one made visible before its first WM_PAINT shows a white one.
            PaintNow(sheet);
            sheet.Opacity = 0xc7 / 255.0;
            Location = new Point(owner.Left + (owner.Width - Width) / 2,
                                 owner.Top + (owner.Height - Height) / 2);
            try { ShowDialog(owner); }
            finally { sheet.Close(); }
        }
    }
}

// The dimming sheet laid over the main window while a dialog is open. It
// never takes the focus: activation moving to it and back is a second
// blink, on the title bar of whatever else is open.
class Sheet : Form
{
    public Sheet()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        BackColor = Theme.Backdrop;
        Opacity = 0;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
    }

    protected override bool ShowWithoutActivation { get { return true; } }

    protected override void OnPaint(PaintEventArgs e)
    {
        using (SolidBrush b = new SolidBrush(Theme.Backdrop))
            e.Graphics.FillRectangle(b, ClientRectangle);
    }
}

// A heading, some paragraphs, and perhaps one orange button.
class TextDialog : Modal
{
    const int PAD = 28, WIDTH = 430;
    readonly string head;
    readonly string[] paras;
    readonly Hot action;
    readonly int bodyHeight;
    static readonly Font bodyFont = Theme.Body(12);
    const float LINE = 12 * 1.7f;

    public TextDialog(string title, string[] paragraphs, string buttonLabel, Action onButton)
        : base(WIDTH)
    {
        head = title;
        paras = paragraphs;

        using (Graphics g = CreateGraphics())
        {
            float h = 0;
            foreach (string p in paras) h += Measure(g, p) + 10;   // 1em margins collapse to ~10
            bodyHeight = (int)Math.Ceiling(h) - 10;
        }

        int y = PAD + 30 + 17 + bodyHeight;
        if (buttonLabel != null)
        {
            // The concept's dialog-action: text 12 px, 11 px above and below.
            action = new DialogButton(buttonLabel);
            action.Click += delegate { Close(); if (onButton != null) onButton(); };
            using (Graphics g = CreateGraphics())
                action.Bounds = Theme.R(PAD, y + 17, (int)Math.Ceiling(Theme.Width(g, buttonLabel, Theme.Body(12))) + 36, 42);
            Controls.Add(action);
            y += 17 + 42;
        }
        Height = Theme.S(y + PAD);
        PlaceClose(12, 12, 28);
    }

    float Measure(Graphics g, string text)
    {
        // Lines wrap at the content width; each takes the 1.7 line height.
        return Math.Max(1, Theme.Wrap(g, text, bodyFont, WIDTH - PAD * 2).Count) * LINE;
    }

    protected override void Draw(Graphics g, int w, int h)
    {
        Theme.Line(g, head, Theme.DisplayTitle(23), Theme.Ink, PAD, PAD, 30);
        float y = PAD + 30 + 17;
        using (SolidBrush b = new SolidBrush(Theme.InkDialog))
        {
            StringFormat sf = new StringFormat(StringFormat.GenericTypographic);
            sf.FormatFlags |= StringFormatFlags.LineLimit;
            sf.Trimming = StringTrimming.Word;
            foreach (string p in paras)
            {
                float ph = Measure(g, p);
                // GDI+ cannot set a line height, so the paragraph is drawn
                // line by line at the concept's leading.
                foreach (string line in Theme.Wrap(g, p, bodyFont, w - PAD * 2))
                {
                    Theme.Line(g, line, bodyFont, Theme.InkDialog, PAD, y, LINE);
                    y += LINE;
                }
                y += 10;
            }
        }
    }
}

// The orange button inside a dialog.
class DialogButton : Hot
{
    readonly string label;

    public DialogButton(string text)
    {
        label = text;
        BackColor = Theme.BgDialog;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        Theme.Fill(g, new RectangleF(0, 0, z.Width, z.Height), 3, hover || down ? Theme.AccentHover : Theme.Accent);
        Font f = Theme.Body(12);
        Theme.Line(g, label, f, Theme.C(0x18191d), (z.Width - Theme.Width(g, label, f)) / 2f, 0, z.Height);
    }
}

// The grey, bordered button of the settings dialog: an icon and a label.
class SetButton : Hot
{
    public string Label = "";
    public string Icon;

    public SetButton() { BackColor = Theme.BgDialog; }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);
        Color fill = Theme.SetBtnBg, line = Theme.BtnLine, ink = Theme.BtnInk;
        if (!Enabled) { fill = Theme.BtnOffBg; line = Theme.BtnOffLine; ink = Theme.BtnOffInk; }
        else if (hover || down) { fill = Theme.SetBtnBgHover; line = Theme.BtnLineHover; }
        Theme.Box(g, r, 4, fill, line);
        Font f = Theme.Body(12);
        float tw = Theme.Width(g, Label, f);
        float icon = Icon == null ? 0 : 14, gap = Icon == null ? 0 : 8;
        float x = (z.Width - icon - gap - tw) / 2f;
        if (Icon != null) { Icons.Draw(g, Icon, x, (z.Height - icon) / 2f, icon, ink); x += icon + gap; }
        Theme.Line(g, Label, f, ink, x, 0, z.Height);
    }
}

// Settings: the game folder, the file check, and below them the launcher's
// version with a link to what changed.
class SettingsDialog : Modal
{
    const int PAD = 28, WIDTH = 480;
    const int HEAD = 28 + 32 + 20;            // title block, before its line
    const int FOLDER = 24 + 16 + 8 + 40 + 8 + 16;   // the first section
    const int CHECK = 24 + 1 + 24 + 16 + 8 + 54;    // its line, then the second: label and up to three lines
    const int UPDATE = CHECK;                       // the third, the same shape
    const int BODY = FOLDER + CHECK + UPDATE + 25;
    const int BTN = 188;                            // every button, so they line up
    const int FOOT = 53;

    readonly SetButton change = new SetButton();
    readonly SetButton verify = new SetButton();
    readonly SetButton update = new SetButton();
    readonly TextLink news = new TextLink();
    string folder, note;
    readonly string version;

    public event Action ChangeFolder, Verify, CheckUpdates, News;

    // The same mark as beside "Что нового" under the panel, until the news
    // has been opened.
    bool newsPending;
    public bool NewsPending
    {
        get { return newsPending; }
        set { newsPending = value; Invalidate(); }
    }

    public SettingsDialog(string gameFolder, string versionLabel, bool canVerify) : base(WIDTH)
    {
        version = versionLabel;
        SetFolder(gameFolder);
        Height = Theme.S(HEAD + 1 + BODY + 1 + FOOT);
        PlaceClose(30, 22, 28);

        change.Label = "Сменить папку";
        change.Icon = "folder";
        change.Bounds = Theme.R(WIDTH - PAD - BTN, HEAD + 1 + 24 + 16 + 8, BTN, 40);
        change.Click += delegate { if (ChangeFolder != null) ChangeFolder(); };
        Controls.Add(change);

        // Centred on the section's text block (label and two lines).
        verify.Label = "Проверить файлы";
        verify.Icon = "retry";
        verify.Enabled = canVerify;
        verify.Bounds = Theme.R(WIDTH - PAD - BTN, HEAD + 1 + FOLDER + 24 + 1 + 24 + (16 + 8 + 54 - 40) / 2, BTN, 40);
        verify.Click += delegate { Close(); if (Verify != null) Verify(); };
        Controls.Add(verify);

        update.Label = "Проверить обновления";
        update.Icon = "download";
        update.Enabled = canVerify;
        update.Bounds = Theme.R(WIDTH - PAD - BTN, HEAD + 1 + FOLDER + CHECK + 24 + 1 + 24 + (16 + 8 + 54 - 40) / 2, BTN, 40);
        update.Click += delegate { Close(); if (CheckUpdates != null) CheckUpdates(); };
        Controls.Add(update);

        news.Label = "Что нового";
        news.Ink = Theme.AccentSoft;
        news.HoverInk = Theme.AccentSoftHover;
        news.AlignRight = true;
        news.BackColor = Theme.BgDialogFoot;
        // As wide as its text, so the mark beside it is not under it.
        int nw;
        using (Graphics g = CreateGraphics()) nw = (int)Math.Ceiling(news.Measure(g)) + 1;
        news.Bounds = Theme.R(WIDTH - PAD - nw, HEAD + 1 + BODY + 1 + (FOOT - 16) / 2, nw, 16);
        news.Click += delegate
        {
            if (News != null) News();
            NewsPending = false;
        };
        Controls.Add(news);
    }

    // The folder on show, and the free space on its drive under it.
    public void SetFolder(string path)
    {
        folder = path ?? "";
        note = "";
        try
        {
            if (folder.Length > 0)
            {
                DriveInfo d = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(folder)));
                note = "Свободно " + Theme.Size(d.AvailableFreeSpace);
            }
        }
        catch { }
        Invalidate();
    }

    // A section under a hairline: its label and up to three lines of text,
    // the button to the right of them placed by the constructor.
    static void Section(Graphics g, int w, int top, string label, string text)
    {
        int y = top + 24;
        Theme.HLine(g, PAD, y, w - PAD * 2, Theme.Hairline);
        y += 1 + 24;
        Theme.Line(g, label, Theme.BodySemi(12), Theme.InkDialogLabel, PAD, y, 16);
        y += 16 + 8;
        Font pf = Theme.Body(12);
        float room = w - PAD * 2 - BTN - 24;
        System.Collections.Generic.List<string> lines = Theme.Wrap(g, text, pf, room);
        for (int i = 0; i < lines.Count && i < 3; i++)
            Theme.Line(g, lines[i], pf, Theme.InkDialog, PAD, y + i * 18, 18);
    }

    protected override void Draw(Graphics g, int w, int h)
    {
        Theme.Line(g, "Настройки", Theme.DisplayTitle(24), Theme.Ink, PAD, 28, 32);
        Theme.HLine(g, 0, HEAD, w, Theme.Hairline);

        int y = HEAD + 1 + 24;
        Theme.Line(g, "Папка игры", Theme.BodySemi(12), Theme.InkDialogLabel, PAD, y, 16);
        y += 16 + 8;
        RectangleF box = new RectangleF(PAD, y, w - PAD * 2 - 8 - BTN, 40);
        Theme.Box(g, box, 4, Theme.BgPath, Theme.LinePath);
        Font mf = Theme.Mono(12);
        Theme.Line(g, Theme.Clip(g, folder, mf, box.Width - 24), mf, Theme.InkDialogPath, PAD + 12, y, 40);
        y += 40 + 8;
        if (note.Length > 0) Theme.Line(g, note, Theme.Body(11), Theme.InkStats, PAD, y, 16);

        Section(g, w, HEAD + 1 + FOLDER, "Проверка файлов",
                "Проверка найдёт недостающие или повреждённые ресурсы и загрузит их заново.");
        Section(g, w, HEAD + 1 + FOLDER + CHECK, "Проверка обновлений",
                "Проверка найдёт новые версии игры и лаунчера и скачает только изменившиеся файлы.");

        int fy = HEAD + 1 + BODY;
        Theme.HLine(g, 0, fy, w, Theme.Hairline);
        using (SolidBrush b = new SolidBrush(Theme.BgDialogFoot))
            g.FillRectangle(b, 1, fy + 1, w - 2, FOOT - 1);
        Font ff = Theme.Body(11);
        float x = PAD;
        Theme.Line(g, "Версия лаунчера", ff, Theme.InkStats, x, fy + 1 + (FOOT - 16) / 2f, 16);
        x += Theme.Width(g, "Версия лаунчера", ff) + 8;
        Theme.Line(g, version, Theme.Mono(12), Theme.InkDialogStrong, x, fy + 1 + (FOOT - 16) / 2f, 16);
        if (newsPending)
            Theme.Dot(g, w - PAD - news.Measure(g) - 6 - 3, fy + 1 + FOOT / 2f, 6, Theme.Accent);
    }
}
