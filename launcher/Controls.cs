// The handful of controls the window is built from.
//
// WinForms draws none of these the way the concept does, so each one is a
// bare Control that paints itself. They share three habits: double buffering
// (or the orange fills flicker on hover), a hand cursor on anything
// clickable, and a Changed() that only invalidates -- no control here reaches
// out and repaints a neighbour. Every size in them is a logical pixel from
// the concept's stylesheet; Theme.Logical puts the scale on.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Windows.Forms;

// Common base: hover and press tracking, and nothing else.
class Hot : Control
{
    protected bool hover, down;

    public Hot()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        Cursor = Cursors.Hand;
    }

    protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnMouseDown(MouseEventArgs e) { down = true; Invalidate(); base.OnMouseDown(e); }
    protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }

    protected override void OnEnabledChanged(EventArgs e)
    {
        Cursor = Enabled ? Cursors.Hand : Cursors.Default;
        hover = false; down = false;
        Invalidate();
        base.OnEnabledChanged(e);
    }

    // The parent paints under us, so a control that does not fill its whole
    // rectangle shows the parent's colour through -- which is what the
    // text-only controls want. BackColor is set to that colour by whoever
    // places the control; this keeps WinForms from painting its own grey.
    protected override void OnPaintBackground(PaintEventArgs e)
    {
        using (SolidBrush b = new SolidBrush(BackColor))
            e.Graphics.FillRectangle(b, ClientRectangle);
    }
}

// The 34 px square buttons on the title bar. Boxed ones (settings, forum)
// have a fill and a border at rest; the window buttons (minimise, close)
// show nothing until the pointer is over them.
class IconButton : Hot
{
    public string Icon = "";
    public bool Boxed;
    public bool IsClose;
    public float IconSize = 19;
    public float Stroke = 1.7f;

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);

        Color fill = Color.Transparent, line = Color.Transparent, ink = Theme.ToolInk;
        if (Boxed)
        {
            fill = Theme.ToolBg; line = Theme.ToolLine;
            if (down) fill = Theme.ToolDown;
            else if (hover) { fill = Theme.ToolBgHover; line = Theme.ToolLineHover; ink = Theme.ToolInkHover; }
        }
        else if (IsClose)
        {
            if (down) { fill = Theme.CloseDown; line = Theme.CloseLine; ink = Theme.CloseInk; }
            else if (hover) { fill = Theme.CloseBg; line = Theme.CloseLine; ink = Theme.CloseInk; }
        }
        else
        {
            if (down) fill = Theme.ToolDown;
            else if (hover) { fill = Theme.A(0xffffff, 0x0d); line = Theme.A(0xffffff, 0x15); ink = Theme.ToolInkHover; }
        }
        if (fill.A > 0) Theme.Fill(g, r, 5, fill);
        if (line.A > 0) Theme.Stroke(g, r, 5, line, 1);
        Icons.Draw(g, Icon, (z.Width - IconSize) / 2f, (z.Height - IconSize) / 2f, IconSize, ink, Stroke);
    }
}

// The filled orange button of the login form: "ВОЙТИ", 44 px, tracked
// semibold capitals. Disabled here means forbidden -- the server is down,
// the launcher is stale -- so it goes grey rather than dim.
class PrimaryButton : Hot
{
    public string Label = "";

    // While the password is checked: a turning arc beside the label.
    readonly Spinner spin;

    public PrimaryButton() { spin = new Spinner(this); }

    public bool Spinning
    {
        get { return spin.On; }
        set { spin.On = value; }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);

        Color fill = Theme.Accent, line = Theme.Accent, ink = Theme.OnAccent;
        if (!Enabled) { fill = Theme.BtnOffBg; line = Theme.BtnOffLine; ink = Theme.BtnOffInk; }
        else if (down) { fill = Theme.AccentDown; line = fill; }
        else if (hover) { fill = Theme.AccentHover; line = fill; }
        Theme.Box(g, r, 4, fill, line);

        Font f = Theme.BodySemi(14);
        float w = Theme.TrackedWidth(g, Label, f, 1);
        float icon = Spinning ? 14 : 0, gap = Spinning ? 10 : 0;
        float x = (z.Width - (icon + gap + w)) / 2f;
        if (Spinning)
        {
            Spinner.Draw(g, x, (z.Height - icon) / 2f, icon, ink);
            x += icon + gap;
        }
        Theme.TrackedLine(g, Label, f, ink, x, 0, z.Height, 1);
    }
}

// The action in the resource panel: 200 x 44, an icon and a label. Plain
// (grey) for pause and retry, Primary (orange) for the one thing the player
// should do next, and in the Play form the label is the tracked "ИГРАТЬ".
class ActionButton : Hot
{
    public string Label = "";
    public string Icon;         // null: label only
    public bool Primary;
    public bool Play;
    readonly Spinner spin;

    public ActionButton() { spin = new Spinner(this); }

    // The game is starting: a turning arc beside the label.
    public bool Spinning
    {
        get { return spin.On; }
        set { spin.On = value; }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);

        Color fill = Theme.BtnBg, line = Theme.BtnLine, ink = Theme.BtnInk;
        if (!Enabled) { fill = Theme.BtnOffBg; line = Theme.BtnOffLine; ink = Theme.BtnOffInk; }
        else if (Primary)
        {
            fill = hover || down ? Theme.AccentHover : Theme.Accent;
            line = fill; ink = Theme.OnAccent;
        }
        else if (hover || down) { fill = Theme.BtnBgHover; line = Theme.BtnLineHover; }
        Theme.Box(g, r, 4, fill, line);

        Font f = Play ? Theme.BodySemi(14) : (Primary ? Theme.BodySemi(12) : Theme.Body(12));
        float tracking = Play ? 1 : 0;
        float tw = tracking > 0 ? Theme.TrackedWidth(g, Label, f, tracking) : Theme.Width(g, Label, f);
        bool mark = Icon != null || Spinning;
        float icon = mark ? 14 : 0, gap = mark ? 8 : 0;
        float x = (z.Width - (icon + gap + tw)) / 2f;
        if (Icon != null) Icons.Draw(g, Icon, x, (z.Height - icon) / 2f, icon, ink);
        else if (Spinning) Spinner.Draw(g, x, (z.Height - icon) / 2f, icon, ink);
        x += icon + gap;
        if (tracking > 0) Theme.TrackedLine(g, Label, f, ink, x, 0, z.Height, tracking);
        else Theme.Line(g, Label, f, ink, x, 0, z.Height);
    }
}

// Text that behaves like a link, with an optional small icon after it.
// Colours are per instance because the concept has four kinds: the muted
// links of the login form, the orange-tinted "Что нового", the footer links
// with their grey arrow, and the monospaced version tag.
class TextLink : Hot
{
    public string Label = "";
    public string Icon;             // a small icon, or null
    public bool IconFirst;          // before the words rather than after
    public float IconSize = 14;
    public float Gap = 8;
    public Color Ink = Theme.InkLink;
    public Color HoverInk = Theme.Accent;
    public Color IconInk = Color.Empty;        // Empty: same as the text
    public Font Face = Theme.Body(11);
    public bool AlignRight;

    // The width the control needs for its content, in logical pixels, so
    // the parent can place it after a measured run of text.
    public float Measure(Graphics g)
    {
        return Theme.Width(g, Label, Face) + (Icon == null ? 0 : Gap + IconSize);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        Color c = hover && Enabled ? HoverInk : Ink;
        if (!Enabled) c = Theme.BtnOffInk;
        float w = Measure(g);
        float x = AlignRight ? z.Width - w : 0;
        Color ic = IconInk.IsEmpty ? c : IconInk;
        if (Icon != null && IconFirst)
        {
            Icons.Draw(g, Icon, x, (z.Height - IconSize) / 2f, IconSize, ic);
            x += IconSize + Gap;
        }
        Theme.Line(g, Label, Face, c, x, 0, z.Height);
        if (Icon != null && !IconFirst)
            Icons.Draw(g, Icon, x + Theme.Width(g, Label, Face) + Gap,
                       (z.Height - IconSize) / 2f, IconSize, ic);
    }
}

// "Запомнить меня": the 14 px box and its label are one click target.
class CheckLine : Hot
{
    public string Label = "";
    bool @checked;

    public bool Checked
    {
        get { return @checked; }
        set { @checked = value; Invalidate(); }
    }

    // On the press, not on Click: two quick presses on the label are a
    // double-click to WinForms, which swallows the second Click, and the
    // box then answered every other time.
    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (Enabled && e.Button == MouseButtons.Left) Checked = !Checked;
        base.OnMouseDown(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        float side = 14;
        float y = (z.Height - side) / 2f;
        RectangleF box = new RectangleF(0, y, side, side);

        // accent-color on a native checkbox: orange when ticked, a grey frame
        // otherwise.
        if (Checked) Theme.Fill(g, box, 2, Theme.Accent);
        else Theme.Box(g, box, 2, Theme.BgField, hover ? Theme.BtnLineHover : Theme.BtnLine);

        if (Checked)
        {
            using (Pen p = new Pen(Theme.OnAccent, 1.6f))
            {
                p.StartCap = LineCap.Round;
                p.EndCap = LineCap.Round;
                p.LineJoin = LineJoin.Round;
                float l = box.Left, t = box.Top, s = side;
                g.DrawLines(p, new PointF[] {
                    new PointF(l + s * 0.24f, t + s * 0.52f),
                    new PointF(l + s * 0.43f, t + s * 0.71f),
                    new PointF(l + s * 0.77f, t + s * 0.30f) });
            }
        }

        Theme.Line(g, Label, Theme.Body(11), hover ? Theme.Ink : Theme.InkRemember, side + 8, 0, z.Height);
    }
}

// A text input: the frame is painted here, the caret belongs to a real
// TextBox sitting inside it. Nothing else gives working selection, clipboard
// and IME, and none of that is worth reimplementing for a login box. The
// password field has the eye that shows what was typed.
class Field : Control
{
    public readonly TextBox Box = new TextBox();
    readonly IconButton eye;
    bool focused;
    bool shown;
    readonly bool isPassword;
    string placeholder = "";

    // "Пароль сохранён" standing in an empty password box, the way the game's
    // own login screen wrote it: what is remembered is the digest, and there
    // is no password to put back. Typing in the box clears it.
    public bool Hint { get; private set; }

    public Field(bool password)
    {
        isPassword = password;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgAuth;

        Box.BorderStyle = BorderStyle.None;
        Box.BackColor = Theme.BgField;
        Box.ForeColor = Theme.InkField;
        Box.Font = Theme.DeviceBody(13);
        Box.MaxLength = password ? 128 : 64;
        if (password) Box.UseSystemPasswordChar = true;
        Box.GotFocus += delegate { focused = true; Invalidate(); };
        Box.LostFocus += delegate { focused = false; Invalidate(); };
        Box.TextChanged += delegate { if (Hint && Box.Text.Length > 0) ClearHint(); };
        Controls.Add(Box);

        if (password)
        {
            eye = new IconButton();
            eye.Icon = "eye";
            eye.IconSize = 16;
            eye.Stroke = 1.5f;
            eye.BackColor = Theme.BgField;
            eye.Click += delegate
            {
                shown = !shown;
                Box.UseSystemPasswordChar = !shown;
                Box.Focus();
            };
            Controls.Add(eye);
        }
    }

    public string Placeholder
    {
        get { return placeholder; }
        set { placeholder = value ?? ""; Cue(); }
    }

    public string Value
    {
        get { return Hint ? "" : Box.Text; }
        set { ClearHint(); Box.Text = value; }
    }

    public void ShowHint(string text)
    {
        Hint = true;
        Box.Text = "";
        Cue(text);
    }

    void ClearHint()
    {
        if (!Hint) return;
        Hint = false;
        Cue();
    }

    // The placeholder is Windows' own cue banner on the TextBox: it is the
    // one thing a TextBox will paint for us, and the alternative is painting
    // text under a control that covers it.
    const int EM_SETCUEBANNER = 0x1501;

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr wp, string lp);

    void Cue() { Cue(placeholder); }

    void Cue(string text)
    {
        if (!Box.IsHandleCreated) { Box.HandleCreated += delegate { Cue(text); }; return; }
        try { SendMessage(Box.Handle, EM_SETCUEBANNER, (IntPtr)1, text ?? ""); }
        catch { }
    }

    protected override void OnSizeChanged(EventArgs e)
    {
        int pad = Theme.S(14);
        int h = Box.PreferredHeight;
        // The text stops short of the eye by the same padding it starts with.
        int right = eye == null ? pad : Theme.S(40) + pad;
        Box.SetBounds(pad, (Height - h) / 2, Width - pad - right, h);
        if (eye != null) eye.SetBounds(Width - Theme.S(40) - Theme.S(1), Theme.S(1), Theme.S(40), Height - Theme.S(2));
        base.OnSizeChanged(e);
    }

    protected override void OnGotFocus(EventArgs e)
    {
        Box.Focus();
        base.OnGotFocus(e);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        Box.Focus();
        base.OnMouseDown(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);
        Theme.Box(g, r, 4, Theme.BgField, focused ? Theme.Accent : Theme.LineField);
    }
}

// A thin horizontal progress track, 4 px, the colour of the panel's tone.
class ProgressTrack : Control
{
    double value;
    public Color Fill = Theme.Accent;

    // No amount to show, only that something is under way: a short run of
    // the fill crossing the track, left to right, once every RUN ms.
    readonly Timer runner = new Timer();
    const int RUN = 1400;
    const float SEGMENT = 0.28f;          // of the track's width

    public ProgressTrack()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgPanel;
        runner.Interval = 16;
        runner.Tick += delegate { Invalidate(); };
    }

    public bool Running
    {
        get { return runner.Enabled; }
        set
        {
            if (value == runner.Enabled) return;
            if (value) runner.Start(); else runner.Stop();
            Invalidate();
        }
    }

    public double Value
    {
        get { return value; }
        set { this.value = Math.Max(0, Math.Min(1, value)); Invalidate(); }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        Theme.Fill(g, new RectangleF(0, 0, z.Width, z.Height), z.Height / 2f, Theme.Track);
        if (Running)
        {
            // Eased, so the run slows at the ends instead of snapping round.
            double p = (Environment.TickCount % RUN) / (double)RUN;
            p = 0.5 - 0.5 * Math.Cos(Math.PI * p);
            float seg = z.Width * SEGMENT;
            float x = (float)(-seg + (z.Width + seg) * p);
            float l = Math.Max(0, x), r = Math.Min(z.Width, x + seg);
            if (r > l) Theme.Fill(g, new RectangleF(l, 0, r - l, z.Height), z.Height / 2f, Fill);
            return;
        }
        float w = (float)(z.Width * value);
        if (w > 0) Theme.Fill(g, new RectangleF(0, 0, w, z.Height), z.Height / 2f, Fill);
    }
}

// A turning arc for a button that is waiting on something: a faint ring and
// a bright quarter going round it, in the label's ink, one turn every TURN
// ms. The owner control is repainted while it is on.
class Spinner
{
    const int TURN = 900;
    readonly Control owner;
    readonly Timer timer = new Timer();

    public Spinner(Control owner)
    {
        this.owner = owner;
        timer.Interval = 16;
        timer.Tick += delegate { owner.Invalidate(); };
    }

    public bool On
    {
        get { return timer.Enabled; }
        set
        {
            if (value == timer.Enabled) return;
            if (value) timer.Start(); else timer.Stop();
            owner.Invalidate();
        }
    }

    public static void Draw(Graphics g, float x, float y, float size, Color ink)
    {
        float a = (Environment.TickCount % TURN) * 360f / TURN;
        RectangleF arc = new RectangleF(x + 1, y + 1, size - 2, size - 2);
        using (Pen p = new Pen(Color.FromArgb(0x40, ink), 1.8f))
            g.DrawEllipse(p, arc);
        using (Pen p = new Pen(ink, 1.8f))
        {
            p.StartCap = p.EndCap = LineCap.Round;
            g.DrawArc(p, arc, a, 100);
        }
    }
}
