// The handful of controls the window is built from.
//
// WinForms draws none of these the way the design system does, so each one is
// a bare Control that paints itself. They share three habits: double
// buffering (or the amber fills flicker on hover), a hand cursor on anything
// clickable, and a Changed() that only invalidates -- no control here reaches
// out and repaints a neighbour.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
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
}

// The one filled button: "Войти".
class PrimaryButton : Hot
{
    public string Label = "";

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        RectangleF r = new RectangleF(0, 0, z.Width, z.Height);

        // Disabled here always means working, never means forbidden, so the
        // button dims rather than greys out and keeps its dark label.
        Color fill = Theme.Brand;
        if (!Enabled) fill = Color.FromArgb(0x8e, 0x72, 0x33);
        else if (down) fill = Theme.Brand;
        else if (hover) fill = Theme.BrandHover;

        Theme.Fill(g, r, 3, fill);

        Color ink = Enabled ? Theme.OnBrand : Color.FromArgb(0x38, 0x2e, 0x1d);
        Font f = Theme.Body(15, true);
        float w = Theme.Width(g, Label, f);
        float h = f.GetHeight(g);
        Theme.Text(g, Label, f, ink, (z.Width - w) / 2f, (z.Height - h) / 2f);
    }
}

// Amber text that behaves like a link. Used for "Создать", "Забыли пароль?".
class LinkText : Hot
{
    public string Label = "";
    public double FontSize = 13;
    public bool Bold;
    public ContentAlignment Align = ContentAlignment.MiddleLeft;

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        Font f = Theme.Body(FontSize, Bold);
        Color c = hover ? Theme.BrandHover : Theme.Brand;
        if (!Enabled) c = Theme.InkFaint;
        float w = Theme.Width(g, Label, f);
        float h = f.GetHeight(g);
        float x = Align == ContentAlignment.MiddleRight ? z.Width - w : 0;
        Theme.Text(g, Label, f, c, x, (z.Height - h) / 2f);
    }
}

// "Запомнить меня": the box and its label are one click target.
class CheckLine : Hot
{
    public string Label = "";
    bool @checked;

    public bool Checked
    {
        get { return @checked; }
        set { @checked = value; Invalidate(); }
    }

    protected override void OnClick(EventArgs e)
    {
        Checked = !Checked;
        base.OnClick(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        float side = 15;
        float y = (z.Height - side) / 2f;
        RectangleF box = new RectangleF(0, y, side, side);

        Theme.Fill(g, box, 2, Checked ? Theme.Brand : Theme.BgInset);
        Theme.Stroke(g, box, 2,
                     Checked ? Theme.Brand : (hover ? Theme.LineStrong : Theme.Line), 1);

        if (Checked)
        {
            // A tick drawn by hand: a glyph font would be one more thing that
            // has to be installed on the player's machine.
            using (Pen p = new Pen(Theme.OnBrand, 1.7f))
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

        Font f = Theme.Body(13, false);
        float fh = f.GetHeight(g);
        Theme.Text(g, Label, f, hover ? Theme.Ink : Theme.InkMuted,
                   side + 10, (z.Height - fh) / 2f);
    }
}

// A text input: the frame is painted here, the caret belongs to a real
// TextBox sitting inside it. Nothing else gives working selection, clipboard
// and IME, and none of that is worth reimplementing for a login box.
class Field : Control
{
    public readonly TextBox Box = new TextBox();
    bool focused;
    readonly bool isPassword;

    // "Пароль сохранён" standing in an empty password box, the way the game's
    // own login screen wrote it: what is remembered is the digest, and there
    // is no password to put back. Typing in the box clears it.
    public bool Hint { get; private set; }

    public Field(bool password)
    {
        isPassword = password;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgBase;

        Box.BorderStyle = BorderStyle.None;
        Box.BackColor = Theme.BgInset;
        Box.ForeColor = Theme.Ink;
        Box.Font = Theme.DeviceBody(14.5, false);
        Box.MaxLength = 64;
        if (password) Box.UseSystemPasswordChar = true;
        Box.GotFocus += delegate { focused = true; ClearHint(); Invalidate(); };
        Box.LostFocus += delegate { focused = false; Invalidate(); };
        Controls.Add(Box);
    }

    public string Value
    {
        get { return Hint ? "" : Box.Text; }
        set { ClearHint(); Box.Text = value; }
    }

    public void ShowHint(string text)
    {
        Hint = true;
        Box.UseSystemPasswordChar = false;
        Box.ForeColor = Theme.InkFaint;
        Box.Text = text;
    }

    void ClearHint()
    {
        if (!Hint) return;
        Hint = false;
        Box.Text = "";
        Box.ForeColor = Theme.Ink;
        if (isPassword) Box.UseSystemPasswordChar = true;
    }

    protected override void OnSizeChanged(EventArgs e)
    {
        int pad = Theme.S(11);
        int h = Box.PreferredHeight;
        Box.SetBounds(pad, (Height - h) / 2, Width - pad * 2, h);
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
        Theme.Fill(g, r, 3, Theme.BgInset);
        Theme.Stroke(g, r, 3, focused ? Theme.Focus : Theme.Line, focused ? 2 : 1);
    }
}

// Minimise and close. The close button turns danger-red under the pointer,
// which is the one place in the window that colour is allowed.
class WinButton : Hot
{
    public bool IsClose;

    public WinButton()
    {
        // These two sit on the title bar, which the form paints in bg-panel.
        // A control that paints only on hover lets the form's own bg-base
        // through the rest of the time, and that reads as a darker block
        // around the buttons.
        BackColor = Theme.BgPanel;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        SizeF z = Theme.Logical(g, this);
        using (SolidBrush b = new SolidBrush(
                   hover ? (IsClose ? Theme.Danger : Theme.BgRaised) : Theme.BgPanel))
            g.FillRectangle(b, 0, 0, z.Width, z.Height);

        Color ink = hover && IsClose ? Theme.OnBrand : Theme.InkMuted;
        float cx = z.Width / 2f, cy = z.Height / 2f, s = 5;
        using (Pen p = new Pen(ink, 1.2f))
        {
            p.StartCap = LineCap.Round;
            p.EndCap = LineCap.Round;
            if (IsClose)
            {
                g.DrawLine(p, cx - s, cy - s, cx + s, cy + s);
                g.DrawLine(p, cx + s, cy - s, cx - s, cy + s);
            }
            else
            {
                g.DrawLine(p, cx - s, cy + 1, cx + s, cy + 1);
            }
        }
    }
}

// The photograph. Drawn to cover the panel rather than fit it, so the frame is
// always full; a thin brass line down the left edge separates it from the
// form without a hard seam.
class HeroPanel : Control
{
    readonly Image image;

    public HeroPanel(Image img)
    {
        image = img;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        BackColor = Theme.BgVoid;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        if (image != null)
        {
            float sx = (float)Width / image.Width;
            float sy = (float)Height / image.Height;
            float s = Math.Max(sx, sy);
            float w = image.Width * s, h = image.Height * s;
            g.DrawImage(image, (Width - w) / 2f, (Height - h) / 2f, w, h);
        }
        else
        {
            using (LinearGradientBrush b = new LinearGradientBrush(
                       new Rectangle(0, 0, Width, Height),
                       Theme.BgBase, Theme.BgVoid, 60f))
                g.FillRectangle(b, 0, 0, Width, Height);
        }

        // A darkened band along the bottom: it settles the picture and keeps
        // the window from ending on a bright edge.
        using (LinearGradientBrush b = new LinearGradientBrush(
                   new Rectangle(0, Height - Theme.S(140), Width, Theme.S(140)),
                   Color.FromArgb(0, 10, 9, 8), Color.FromArgb(150, 10, 9, 8), 90f))
            g.FillRectangle(b, 0, Height - Theme.S(140), Width, Theme.S(140));

        using (SolidBrush b = new SolidBrush(Theme.Line))
            g.FillRectangle(b, 0, 0, Math.Max(1, Theme.S(1)), Height);
    }
}
