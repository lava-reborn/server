// The window that says something went wrong before there is a window.
//
// A MessageBox would do the job, and would look like it came from a different
// program. There are only a few of these -- no projector, no trust file, an
// unhandled fault -- and each one is the last thing the player sees, so it
// may as well be the same window as everything else.
using System;
using System.Drawing;
using System.Windows.Forms;

class Notice : Form
{
    const int W = 460, BAR = 54, PAD = 28;

    readonly string head, body;
    readonly DialogButton ok;
    readonly IconButton close = new IconButton();
    readonly Image logo;
    int bodyHeight;

    Notice(string title, string text)
    {
        head = title;
        body = text;
        logo = LoadLogo();

        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Theme.Bg;
        Text = "Lava Reborn";
        KeyPreview = true;
        Icon = Brand.AppIcon();
        ShowInTaskbar = true;

        // The message is the only thing that varies, so the window is measured
        // around it rather than given a size and hoping.
        using (Graphics g = CreateGraphics())
            bodyHeight = Lines(g).Count * LINE;

        int h = BAR + 26 + 30 + bodyHeight + 28 + 42 + 28;
        ClientSize = new Size(Theme.S(W), Theme.S(h));

        ok = new DialogButton("Понятно");
        ok.BackColor = Theme.Bg;
        ok.Bounds = Theme.R(W - PAD - 130, h - 28 - 42, 130, 42);
        ok.Click += delegate { Close(); };
        Controls.Add(ok);

        close.Icon = "window-close";
        close.IsClose = true;
        close.BackColor = Theme.Bg;
        close.Bounds = Theme.R(W - 10 - 34, (BAR - 34) / 2, 34, 34);
        close.Click += delegate { Close(); };
        Controls.Add(close);
    }

    // The message as lines: paragraphs split on blank lines, each wrapped
    // to the window, with an empty line between them.
    const int LINE = 20;

    System.Collections.Generic.List<string> Lines(Graphics g)
    {
        System.Collections.Generic.List<string> lines = new System.Collections.Generic.List<string>();
        foreach (string para in body.Replace("\r\n", "\n").Split('\n'))
        {
            if (para.Length == 0) { lines.Add(""); continue; }
            lines.AddRange(Theme.Wrap(g, para, Theme.Body(13), W - PAD * 2));
        }
        return lines;
    }

    static Image LoadLogo()
    {
        try
        {
            using (System.IO.Stream s = System.Reflection.Assembly
                       .GetExecutingAssembly().GetManifestResourceStream("logo.png"))
                return s == null ? null : Image.FromStream(s);
        }
        catch { return null; }
    }

    public static void Show(string title, string text)
    {
        try
        {
            Theme.Init();
            using (Notice n = new Notice(title, text)) n.ShowDialog();
        }
        catch
        {
            // Even the apology is allowed to fail on a machine this broken.
            MessageBox.Show(text, title, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape || e.KeyCode == Keys.Enter) Close();
        base.OnKeyDown(e);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Left && e.Y < Theme.S(BAR))
        {
            Native.ReleaseCapture();
            Native.SendMessage(Handle, 0xA1, 2, 0);
        }
        base.OnMouseDown(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        g.ScaleTransform(Theme.Scale, Theme.Scale);
        int w = (int)(ClientSize.Width / Theme.Scale);
        int h = (int)(ClientSize.Height / Theme.Scale);

        if (logo != null) g.DrawImage(logo, 25, (BAR - 34) / 2f, 94, 34);
        Theme.HLine(g, 0, BAR - 1, w, Theme.Hairline);

        Theme.Line(g, head, Theme.DisplayTitle(23), Theme.Ink, PAD, BAR + 26, 30);

        float y = BAR + 26 + 30;
        foreach (string line in Lines(g))
        {
            Theme.Line(g, line, Theme.Body(13), Theme.InkDialog, PAD, y, LINE);
            y += LINE;
        }

        using (Pen p = new Pen(Theme.WindowEdge, 1))
            g.DrawRectangle(p, 0, 0, w - 1, h - 1);
    }
}

static class Native
{
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern bool ReleaseCapture();

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr h, int msg, int wp, int lp);
}
